from __future__ import annotations

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
