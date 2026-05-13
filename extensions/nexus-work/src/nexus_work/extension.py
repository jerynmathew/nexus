from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from nexus.extensions import NexusContext

from nexus_work.commands import handle_actions, handle_delegate, handle_meetings, handle_next
from nexus_work.schema import WORK_SCHEMA

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
