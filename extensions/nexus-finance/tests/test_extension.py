from __future__ import annotations

import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

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
        assert "finance_alert_check" in signal_calls
        assert "gold_price_collect" in signal_calls
        assert "bank_statement_reminder" in signal_calls
        assert "maturity_alert" in signal_calls

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

    async def test_collect_gold_prices(self) -> None:
        ext = FinanceExtension()
        ctx = AsyncMock()
        ctx.call_tool = AsyncMock(return_value="<html>22 Karat ₹6,500 24 Karat ₹7,100</html>")
        ctx.send_to_memory = AsyncMock(return_value={"status": "ok"})
        ext._ctx = ctx

        await ext._collect_gold_prices({"city": "bangalore"})
        ctx.call_tool.assert_called_once()
        assert ctx.send_to_memory.call_count == 1

    async def test_collect_gold_prices_parse_failure(self) -> None:
        ext = FinanceExtension()
        ctx = AsyncMock()
        ctx.call_tool = AsyncMock(return_value="<html>no prices here</html>")
        ext._ctx = ctx

        await ext._collect_gold_prices({"city": "mumbai"})
        ctx.send_to_memory.assert_not_called()

    async def test_check_bank_reminders(self) -> None:
        ext = FinanceExtension()
        ctx = AsyncMock()
        ctx.send_to_memory = AsyncMock(
            return_value={
                "rows": [["hdfc", "2026-01-01"]],
            }
        )
        ext._ctx = ctx

        await ext._check_bank_reminders({"tenant_id": "t1"})
        ctx.send_to_memory.assert_called()

    async def test_check_bank_reminders_no_tenant(self) -> None:
        ext = FinanceExtension()
        ext._ctx = AsyncMock()
        await ext._check_bank_reminders({})
        ext._ctx.send_to_memory.assert_not_called()

    async def test_maturity_alerts(self) -> None:
        ext = FinanceExtension()
        ctx = AsyncMock()
        future_date = (datetime.now() + timedelta(days=10)).strftime("%Y-%m-%d")
        ctx.send_to_memory = AsyncMock(
            return_value={
                "rows": [
                    ["FD-HDFC", "HDFC FD", json.dumps({"maturity_date": future_date})],
                ],
            }
        )
        ext._ctx = ctx

        await ext._check_maturity_alerts({"tenant_id": "t1"})
        ctx.send_to_memory.assert_called()

    async def test_maturity_alerts_no_maturity_date(self) -> None:
        ext = FinanceExtension()
        ctx = AsyncMock()
        ctx.send_to_memory = AsyncMock(
            return_value={
                "rows": [["PPF", "PPF", "{}"]],
            }
        )
        ext._ctx = ctx

        await ext._check_maturity_alerts({"tenant_id": "t1"})
        ctx.send_to_memory.assert_called_once()
