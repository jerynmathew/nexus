from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from nexus.extensions import NexusContext

from nexus_work.briefing import (
    assemble_evening_wrap,
    assemble_meeting_prep,
    assemble_morning_briefing,
)
from nexus_work.commands import handle_actions, handle_delegate, handle_meetings, handle_next
from nexus_work.schema import WORK_SCHEMA
from nexus_work.signals import extract_actions_from_signal, store_signal

logger = logging.getLogger(__name__)


class WorkExtension:
    def __init__(self) -> None:
        self._ctx: NexusContext | None = None

    @property
    def name(self) -> str:
        return "nexus-work"

    @property
    def version(self) -> str:
        from nexus_work import __version__

        return __version__

    async def on_load(self, nexus: NexusContext) -> None:
        self._ctx = nexus
        nexus.register_schema(WORK_SCHEMA)
        nexus.register_skill_dir(Path(__file__).parent / "skills")
        nexus.register_command("actions", handle_actions)
        nexus.register_command("delegate", handle_delegate)
        nexus.register_command("meetings", handle_meetings)
        nexus.register_command("next", handle_next)
        nexus.register_signal_handler("delegation_check", self._check_stale_delegations)
        nexus.register_signal_handler("work_morning_briefing", self._morning_briefing)
        nexus.register_signal_handler("work_evening_wrap", self._evening_wrap)
        nexus.register_signal_handler("work_meeting_prep", self._meeting_prep)
        nexus.register_signal_handler("work_action_extract", self._action_extract)
        nexus.register_signal_handler("work_calendar_sync", self._calendar_sync)

    async def on_unload(self) -> None:
        self._ctx = None

    async def _check_stale_delegations(self, payload: dict[str, Any]) -> None:
        if not self._ctx:
            return

        tenant_id = payload.get("tenant_id")
        if not tenant_id:
            return

        stale_days = int(payload.get("stale_days", 3))

        result = await self._ctx.send_to_memory(
            "ext_query",
            {
                "sql": (
                    "SELECT id, delegated_to, task, due_date FROM work_delegations"
                    " WHERE tenant_id = ? AND status NOT IN ('done')"
                    " AND (last_update IS NULL"
                    f"  OR julianday('now') - julianday(last_update) > {stale_days})"
                ),
                "params": [tenant_id],
            },
        )
        rows = result.get("rows", [])
        for row in rows:
            await self._ctx.send_to_memory(
                "ext_execute",
                {
                    "sql": "UPDATE work_delegations SET status='stale' WHERE id=?",
                    "params": [row[0]],
                },
            )
            logger.info(
                "Delegation #%d to %s marked stale: %s",
                row[0],
                row[1],
                row[2],
            )

    async def _morning_briefing(self, payload: dict[str, Any]) -> None:
        if not self._ctx:
            return
        tenant_id = payload.get("tenant_id")
        if not tenant_id:
            return

        text = await assemble_morning_briefing(self._ctx, tenant_id)
        logger.info("Morning briefing assembled for %s (%d chars)", tenant_id, len(text))

    async def _evening_wrap(self, payload: dict[str, Any]) -> None:
        if not self._ctx:
            return
        tenant_id = payload.get("tenant_id")
        if not tenant_id:
            return

        text = await assemble_evening_wrap(self._ctx, tenant_id)
        logger.info("Evening wrap assembled for %s (%d chars)", tenant_id, len(text))

    async def _meeting_prep(self, payload: dict[str, Any]) -> None:
        if not self._ctx:
            return
        tenant_id = payload.get("tenant_id")
        meeting_id = payload.get("meeting_id")
        if not tenant_id or not meeting_id:
            return

        text = await assemble_meeting_prep(self._ctx, tenant_id, int(meeting_id))
        if text:
            logger.info("Meeting prep assembled for %s meeting #%s", tenant_id, meeting_id)

    async def _action_extract(self, payload: dict[str, Any]) -> None:
        if not self._ctx:
            return
        tenant_id = payload.get("tenant_id")
        text = payload.get("text", "")
        source = payload.get("source", "manual")
        source_ref = payload.get("source_ref", "")
        author = payload.get("author", "")

        if not tenant_id or not text:
            return

        await store_signal(
            self._ctx,
            tenant_id=tenant_id,
            source=source,
            event_type="message",
            title=text[:100],
            body=text,
            author=author,
        )

        count = await extract_actions_from_signal(
            self._ctx, tenant_id, text, source, source_ref, author
        )
        if count > 0:
            logger.info("Extracted %d action(s) from %s signal for %s", count, source, tenant_id)

    async def _calendar_sync(self, payload: dict[str, Any]) -> None:
        if not self._ctx:
            return
        tenant_id = payload.get("tenant_id")
        if not tenant_id:
            return

        raw = await self._ctx.call_tool("google_calendar_list_events")

        try:
            events = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.debug("Failed to parse calendar response")
            return

        if not isinstance(events, list):
            return

        count = 0
        for event in events:
            event_id = event.get("id", "")
            title = event.get("summary", "Untitled")
            start = event.get("start", {})
            meeting_date = start.get("date") or start.get("dateTime", "")[:10]
            attendees_raw = event.get("attendees", [])
            attendees = [
                a.get("displayName") or a.get("email", "")
                for a in attendees_raw
                if not a.get("self")
            ]

            if not event_id:
                continue

            result = await self._ctx.send_to_memory(
                "ext_execute",
                {
                    "sql": (
                        "INSERT INTO work_meetings"
                        " (tenant_id, event_id, title, attendees, meeting_date)"
                        " VALUES (?, ?, ?, ?, ?)"
                        " ON CONFLICT(tenant_id, event_id) DO UPDATE SET"
                        "  title=excluded.title, attendees=excluded.attendees,"
                        "  meeting_date=excluded.meeting_date"
                    ),
                    "params": [
                        tenant_id,
                        event_id,
                        title,
                        json.dumps(attendees) if attendees else None,
                        meeting_date,
                    ],
                },
            )
            if result.get("status") == "ok":
                count += 1

        logger.info("Calendar sync: %d events for %s", count, tenant_id)
