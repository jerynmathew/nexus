from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

from nexus_work.extension import WorkExtension


class TestWorkExtension:
    def test_name(self) -> None:
        ext = WorkExtension()
        assert ext.name == "nexus-work"

    def test_version(self) -> None:
        ext = WorkExtension()
        assert ext.version == "0.1.0"

    async def test_on_load_registers_commands(self) -> None:
        ext = WorkExtension()
        ctx = MagicMock()
        ctx.register_command = MagicMock()
        ctx.register_schema = MagicMock()
        ctx.register_skill_dir = MagicMock()
        ctx.register_signal_handler = MagicMock()

        await ext.on_load(ctx)

        assert ctx.register_schema.call_count == 1
        assert ctx.register_skill_dir.call_count == 1

        commands = [call.args[0] for call in ctx.register_command.call_args_list]
        assert "actions" in commands
        assert "delegate" in commands
        assert "meetings" in commands
        assert "next" in commands

        signals = [call.args[0] for call in ctx.register_signal_handler.call_args_list]
        assert "delegation_check" in signals
        assert "work_morning_briefing" in signals
        assert "work_evening_wrap" in signals
        assert "work_meeting_prep" in signals
        assert "work_action_extract" in signals
        assert "work_calendar_sync" in signals

    async def test_on_unload(self) -> None:
        ext = WorkExtension()
        await ext.on_unload()
        assert ext._ctx is None

    async def test_check_stale_delegations(self) -> None:
        ext = WorkExtension()
        ctx = AsyncMock()
        ctx.send_to_memory = AsyncMock(
            side_effect=[
                {"rows": [[1, "Raj", "Cache redesign", "2026-05-15"]]},
                {"status": "ok"},
            ]
        )
        ext._ctx = ctx

        await ext._check_stale_delegations({"tenant_id": "t1"})
        assert ctx.send_to_memory.call_count == 2

    async def test_check_stale_no_tenant(self) -> None:
        ext = WorkExtension()
        ext._ctx = AsyncMock()
        await ext._check_stale_delegations({})
        ext._ctx.send_to_memory.assert_not_called()

    async def test_morning_briefing_handler(self) -> None:
        ext = WorkExtension()
        ctx = AsyncMock()
        ctx.send_to_memory = AsyncMock(return_value={"rows": []})
        ext._ctx = ctx
        await ext._morning_briefing({"tenant_id": "t1"})

    async def test_evening_wrap_handler(self) -> None:
        ext = WorkExtension()
        ctx = AsyncMock()
        ctx.send_to_memory = AsyncMock(return_value={"rows": []})
        ext._ctx = ctx
        await ext._evening_wrap({"tenant_id": "t1"})

    async def test_meeting_prep_handler(self) -> None:
        ext = WorkExtension()
        ctx = AsyncMock()
        ctx.send_to_memory = AsyncMock(return_value={"rows": []})
        ext._ctx = ctx
        await ext._meeting_prep({"tenant_id": "t1", "meeting_id": 1})

    async def test_action_extract_handler(self) -> None:
        ext = WorkExtension()
        ctx = AsyncMock()
        ctx.send_to_memory = AsyncMock(return_value={"status": "ok"})
        ctx.llm = None
        ext._ctx = ctx
        await ext._action_extract(
            {
                "tenant_id": "t1",
                "text": "Please review PR #234 by tomorrow",
                "source": "email",
                "author": "Sarah",
            }
        )
        assert ctx.send_to_memory.call_count >= 1

    async def test_calendar_sync_handler(self) -> None:
        ext = WorkExtension()
        ctx = AsyncMock()
        events = [
            {"id": "evt1", "summary": "Standup", "start": {"date": "2026-05-14"}, "attendees": []},
        ]
        ctx.call_tool = AsyncMock(return_value=json.dumps(events))
        ctx.send_to_memory = AsyncMock(return_value={"status": "ok"})
        ext._ctx = ctx
        await ext._calendar_sync({"tenant_id": "t1"})
        assert ctx.send_to_memory.call_count >= 1

    async def test_calendar_sync_invalid_response(self) -> None:
        ext = WorkExtension()
        ctx = AsyncMock()
        ctx.call_tool = AsyncMock(return_value="not json")
        ext._ctx = ctx
        await ext._calendar_sync({"tenant_id": "t1"})
