from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from civitas.messages import Message

from nexus.agents.scheduler import SchedulerAgent


def _msg(action: str, **extra) -> Message:
    return Message(
        sender="test",
        recipient="scheduler",
        payload={"action": action, **extra},
        reply_to="test",
    )


class TestSchedulerAgent:
    async def test_starts(self) -> None:
        agent = SchedulerAgent(name="scheduler")
        await agent.on_start()
        assert agent._state_loaded is False

    async def test_status_query(self) -> None:
        agent = SchedulerAgent(name="scheduler")
        await agent.on_start()

        msg = _msg("status")
        agent._current_message = msg
        try:
            result = await agent.handle(msg)
        finally:
            agent._current_message = None

        assert result is not None
        assert result.payload["status"] == "running"
        assert result.payload["state_loaded"] is True

    async def test_unknown_action(self) -> None:
        agent = SchedulerAgent(name="scheduler")
        agent._state_loaded = True
        msg = _msg("bogus")
        agent._current_message = msg
        try:
            result = await agent.handle(msg)
        finally:
            agent._current_message = None
        assert result is None

    async def test_in_active_hours(self) -> None:
        agent = SchedulerAgent(name="scheduler", active_hours_start=7, active_hours_end=22)
        noon = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        assert agent._in_active_hours(noon) is True

    async def test_outside_active_hours(self) -> None:
        agent = SchedulerAgent(name="scheduler", active_hours_start=7, active_hours_end=22)
        midnight = datetime(2026, 1, 1, 3, 0, tzinfo=UTC)
        assert agent._in_active_hours(midnight) is False

    def test_cron_matches_valid(self) -> None:
        now = datetime(2026, 1, 1, 7, 0, tzinfo=UTC)
        assert SchedulerAgent._cron_matches("0 7 * * *", now) is True

    def test_cron_matches_invalid(self) -> None:
        assert SchedulerAgent._cron_matches("invalid", datetime.now(UTC)) is False

    def test_cron_no_match(self) -> None:
        now = datetime(2026, 1, 1, 8, 0, tzinfo=UTC)
        assert SchedulerAgent._cron_matches("0 7 * * *", now) is False

    async def test_check_mcp_health(self) -> None:
        agent = SchedulerAgent(name="scheduler")
        agent.send = AsyncMock()
        await agent._check_mcp_health()
        agent.send.assert_called_once()

    async def test_trigger_skill(self) -> None:
        agent = SchedulerAgent(name="scheduler")
        agent.send = AsyncMock()
        await agent._trigger_skill("morning-briefing")
        payload = agent.send.call_args[0][1]
        assert payload["skill_name"] == "morning-briefing"

    async def test_persist_last_run_success(self) -> None:
        agent = SchedulerAgent(name="scheduler")
        agent.send = AsyncMock()
        await agent._persist_last_run("skill1", "2026-01-01 07:00")
        agent.send.assert_called_once()

    async def test_persist_last_run_failure(self) -> None:
        agent = SchedulerAgent(name="scheduler")
        agent.send = AsyncMock(side_effect=Exception("fail"))
        await agent._persist_last_run("skill1", "2026-01-01 07:00")
        agent.send.assert_called_once()

    async def test_load_state_success(self) -> None:
        agent = SchedulerAgent(name="scheduler")
        resp = Message(
            sender="memory",
            recipient="scheduler",
            payload={"configs": {"last_runs": {"s1": "2026-01-01 07:00"}}},
        )
        agent.ask = AsyncMock(return_value=resp)
        await agent._load_state()
        assert agent._last_runs == {"s1": "2026-01-01 07:00"}

    async def test_load_state_failure(self) -> None:
        agent = SchedulerAgent(name="scheduler")
        agent.ask = AsyncMock(side_effect=Exception("fail"))
        await agent._load_state()
        assert agent._last_runs == {}

    async def test_on_tick_no_skills(self) -> None:
        agent = SchedulerAgent(name="scheduler")
        agent.send = AsyncMock()
        with patch("nexus.agents.scheduler.SkillManager") as mock_sm:
            mock_sm.return_value.get_scheduled.return_value = []
            await agent._on_tick()
        assert agent.send.call_count == 1  # health check only

    async def test_on_tick_with_matching_skill(self) -> None:
        agent = SchedulerAgent(name="scheduler")
        agent.send = AsyncMock()

        skill = MagicMock()
        skill.name = "morning-briefing"
        skill.schedule = "* * * * *"
        skill.active_hours_only = False

        with patch("nexus.agents.scheduler.SkillManager") as mock_sm:
            mock_sm.return_value.get_scheduled.return_value = [skill]
            await agent._on_tick()

        assert agent.send.call_count >= 2

    async def test_active_hours_only_outside_skips(self) -> None:
        agent = SchedulerAgent(name="scheduler", active_hours_start=7, active_hours_end=8)
        assert agent._in_active_hours(datetime(2026, 1, 1, 15, 0, tzinfo=UTC)) is False

    async def test_on_tick_already_ran(self) -> None:
        agent = SchedulerAgent(name="scheduler")
        agent.send = AsyncMock()

        skill = MagicMock()
        skill.name = "test-skill"
        skill.schedule = "* * * * *"
        skill.active_hours_only = False

        now = datetime.now(UTC)
        current_minute = now.strftime("%Y-%m-%d %H:%M")
        agent._last_runs = {"test-skill": current_minute}

        with patch("nexus.agents.scheduler.SkillManager") as mock_sm:
            mock_sm.return_value.get_scheduled.return_value = [skill]
            await agent._on_tick()
        assert agent.send.call_count == 1  # health check only, skill skipped

    async def test_on_tick_no_schedule(self) -> None:
        agent = SchedulerAgent(name="scheduler")
        agent.send = AsyncMock()

        skill = MagicMock()
        skill.name = "no-schedule"
        skill.schedule = None

        with patch("nexus.agents.scheduler.SkillManager") as mock_sm:
            mock_sm.return_value.get_scheduled.return_value = [skill]
            await agent._on_tick()
        assert agent.send.call_count == 1  # health check only

    async def test_handle_tick_action(self) -> None:
        agent = SchedulerAgent(name="scheduler")
        agent._state_loaded = True
        agent.send = AsyncMock()
        msg = _msg("tick")
        agent._current_message = msg

        with patch("nexus.agents.scheduler.SkillManager") as mock_sm:
            mock_sm.return_value.get_scheduled.return_value = []
            try:
                await agent.handle(msg)
            finally:
                agent._current_message = None
        assert agent.send.call_count == 1  # health check only
