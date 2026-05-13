from __future__ import annotations

from unittest.mock import MagicMock

from nexus_finance.extension import FinanceExtension


class TestFinanceExtension:
    def test_name(self) -> None:
        ext = FinanceExtension()
        assert ext.name == "nexus-finance"

    def test_version(self) -> None:
        ext = FinanceExtension()
        assert ext.version == "0.1.0"

    async def test_on_load_registers_commands(self) -> None:
        ext = FinanceExtension()
        ctx = MagicMock()
        ctx.register_command = MagicMock()
        ctx.register_schema = MagicMock()
        ctx.register_skill_dir = MagicMock()
        ctx.register_signal_handler = MagicMock()

        await ext.on_load(ctx)

        assert ctx.register_schema.call_count == 1
        assert ctx.register_skill_dir.call_count == 1

        registered_commands = [call.args[0] for call in ctx.register_command.call_args_list]
        assert "portfolio" in registered_commands
        assert "fire" in registered_commands
        assert "rebalance" in registered_commands
        assert "research" in registered_commands
        assert "gold" in registered_commands
        assert "holdings" in registered_commands

        signal_calls = [call.args[0] for call in ctx.register_signal_handler.call_args_list]
        assert "scheduled_sync" in signal_calls

    async def test_on_unload(self) -> None:
        ext = FinanceExtension()
        await ext.on_unload()
        assert ext._ctx is None

    async def test_stores_context_on_load(self) -> None:
        ext = FinanceExtension()
        ctx = MagicMock()
        ctx.register_command = MagicMock()
        ctx.register_schema = MagicMock()
        ctx.register_skill_dir = MagicMock()
        ctx.register_signal_handler = MagicMock()

        await ext.on_load(ctx)
        assert ext._ctx is ctx
