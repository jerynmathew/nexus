from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from civitas.messages import Message
from civitas.process import AgentProcess
from croniter import croniter

from nexus.skills.manager import SkillManager

logger = logging.getLogger(__name__)

_TICK_INTERVAL_MS = 60_000


class SchedulerAgent(AgentProcess):
    def __init__(
        self,
        name: str,
        skills_dir: str = "skills",
        active_hours_start: int = 7,
        active_hours_end: int = 22,
        **kwargs: Any,
    ) -> None:
        super().__init__(name, **kwargs)
        self._skills_dir = skills_dir
        self._active_start = active_hours_start
        self._active_end = active_hours_end
        self._state_loaded = False
        self._last_runs: dict[str, str] = {}

    async def on_start(self) -> None:
        self._state_loaded = False

    async def handle(self, message: Message) -> Message | None:
        if not self._state_loaded:
            await self._load_state()
            self._start_tick()
            self._state_loaded = True

        action = message.payload.get("action")

        if action == "tick":
            await self._on_tick()
            self._start_tick()
            return None

        if action == "status":
            return self.reply(
                {
                    "status": "running",
                    "state_loaded": self._state_loaded,
                    "tracked_skills": len(self._last_runs),
                }
            )

        return None

    def _start_tick(self) -> None:
        asyncio.get_running_loop().call_later(
            _TICK_INTERVAL_MS / 1000,
            lambda: asyncio.ensure_future(self._enqueue_tick()),
        )

    async def _enqueue_tick(self) -> None:
        await self.send(self.name, {"action": "tick"})

    async def _load_state(self) -> None:
        try:
            result = await self.ask(
                "memory",
                {
                    "action": "config_get_all",
                    "tenant_id": "_scheduler",
                },
            )
            configs = result.payload.get("configs", {})
            self._last_runs = configs.get("last_runs", {})
        except Exception:
            logger.debug("[%s] Failed to load scheduler state", self.name)
            self._last_runs = {}

    async def _on_tick(self) -> None:
        await self._check_mcp_health()

        manager = SkillManager(Path(self._skills_dir))
        scheduled_skills = manager.get_scheduled()

        if not scheduled_skills:
            return

        now = datetime.now(UTC)
        current_minute = now.strftime("%Y-%m-%d %H:%M")

        for skill in scheduled_skills:
            if not skill.schedule:
                continue
            if self._last_runs.get(skill.name) == current_minute:
                continue
            if not self._cron_matches(skill.schedule, now):
                continue
            if skill.active_hours_only and not self._in_active_hours(now):
                continue

            self._last_runs[skill.name] = current_minute
            await self._trigger_skill(skill.name)
            await self._persist_last_run(skill.name, current_minute)

    def _in_active_hours(self, now: datetime) -> bool:
        return self._active_start <= now.hour < self._active_end

    @staticmethod
    def _cron_matches(cron_expr: str, now: datetime) -> bool:
        try:
            if not croniter.is_valid(cron_expr):
                return False
            return bool(croniter.match(cron_expr, now))
        except (ValueError, KeyError):
            return False

    async def _check_mcp_health(self) -> None:
        with contextlib.suppress(Exception):
            await self.send("conversation_manager", {"action": "mcp_health_check"})

    async def _trigger_skill(self, skill_name: str) -> None:
        logger.info("[%s] Triggering skill '%s'", self.name, skill_name)
        await self.send(
            "conversation_manager",
            {
                "action": "execute_skill",
                "skill_name": skill_name,
                "tenant_id": "_all_admins",
            },
        )

    async def _persist_last_run(self, skill_name: str, run_time: str) -> None:
        try:
            await self.send(
                "memory",
                {
                    "action": "config_set",
                    "tenant_id": "_scheduler",
                    "namespace": "last_runs",
                    "key": skill_name,
                    "value": run_time,
                },
            )
        except Exception:
            logger.debug("[%s] Failed to persist last run for %s", self.name, skill_name)
