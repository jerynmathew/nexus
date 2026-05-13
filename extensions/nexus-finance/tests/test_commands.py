from __future__ import annotations

import json
from unittest.mock import AsyncMock

from nexus_finance.commands import (
    handle_fire,
    handle_gold,
    handle_holdings,
    handle_portfolio,
    handle_rebalance,
    handle_research,
)

_HOLDING_ROW = [
    "RELIANCE",
    "Reliance",
    "equity",
    10,
    2500,
    2700,
    27000,
    2000,
    8.0,
    "zerodha",
    None,
]


def _mock_ctx(holdings_rows=None, query_results=None):
    ctx = AsyncMock()
    if holdings_rows is None:
        holdings_rows = []
    default_result = {
        "columns": [
            "symbol",
            "name",
            "asset_class",
            "quantity",
            "avg_price",
            "current_price",
            "current_value",
            "pnl",
            "pnl_pct",
            "source",
            "metadata",
        ],
        "rows": holdings_rows,
    }

    if query_results:
        ctx.send_to_memory = AsyncMock(side_effect=query_results)
    else:
        ctx.send_to_memory = AsyncMock(return_value=default_result)

    ctx.call_tool = AsyncMock(return_value="[]")
    return ctx


class TestHandlePortfolio:
    async def test_summary_empty(self) -> None:
        reply = AsyncMock()
        ctx = _mock_ctx()
        await handle_portfolio(
            command="portfolio",
            args="",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        sent = reply.call_args[0][1]
        assert "/holdings add" in sent

    async def test_summary_with_data(self) -> None:
        reply = AsyncMock()
        ctx = _mock_ctx(holdings_rows=[_HOLDING_ROW])
        await handle_portfolio(
            command="portfolio",
            args="",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        sent = reply.call_args[0][1]
        assert "Portfolio Summary" in sent
        assert "SEBI" in sent

    async def test_detail(self) -> None:
        reply = AsyncMock()
        ctx = _mock_ctx(holdings_rows=[_HOLDING_ROW])
        await handle_portfolio(
            command="portfolio",
            args="detail",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        sent = reply.call_args[0][1]
        assert "Holdings Detail" in sent

    async def test_no_context(self) -> None:
        reply = AsyncMock()
        await handle_portfolio(
            command="portfolio",
            args="",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
        )
        sent = reply.call_args[0][1]
        assert "unavailable" in sent


class TestHandleFire:
    async def test_no_context(self) -> None:
        reply = AsyncMock()
        await handle_fire(
            command="fire",
            args="",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
        )
        sent = reply.call_args[0][1]
        assert "unavailable" in sent

    async def test_progress_no_config(self) -> None:
        reply = AsyncMock()
        ctx = _mock_ctx()
        ctx.send_to_memory = AsyncMock(return_value={"rows": []})
        await handle_fire(
            command="fire",
            args="",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        sent = reply.call_args[0][1]
        assert "config not set" in sent

    async def test_progress_with_config(self) -> None:
        reply = AsyncMock()
        fire_config_result = {
            "rows": [[3_00_00_000, 100000, 0.04, 0.06, 0.12, None]],
        }
        holdings_result = {
            "columns": [
                "symbol",
                "name",
                "asset_class",
                "quantity",
                "avg_price",
                "current_price",
                "current_value",
                "pnl",
                "pnl_pct",
                "source",
                "metadata",
            ],
            "rows": [_HOLDING_ROW],
        }
        ctx = _mock_ctx(query_results=[fire_config_result, holdings_result])
        await handle_fire(
            command="fire",
            args="",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        sent = reply.call_args[0][1]
        assert "FIRE Progress" in sent
        assert "SEBI" in sent

    async def test_config_show_empty(self) -> None:
        reply = AsyncMock()
        ctx = _mock_ctx()
        ctx.send_to_memory = AsyncMock(return_value={"rows": []})
        await handle_fire(
            command="fire",
            args="config",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        sent = reply.call_args[0][1]
        assert "No FIRE config" in sent

    async def test_config_show_existing(self) -> None:
        reply = AsyncMock()
        ctx = _mock_ctx()
        ctx.send_to_memory = AsyncMock(
            return_value={
                "rows": [[3_00_00_000, 100000, 0.04, 0.06, 0.12, None]],
            }
        )
        await handle_fire(
            command="fire",
            args="config",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        sent = reply.call_args[0][1]
        assert "FIRE Configuration" in sent

    async def test_config_set(self) -> None:
        reply = AsyncMock()
        ctx = AsyncMock()
        ctx.send_to_memory = AsyncMock(return_value={"status": "ok"})
        await handle_fire(
            command="fire",
            args="config monthly_expenses=100000 target_years=15",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        sent = reply.call_args[0][1]
        assert "FIRE config saved" in sent
        assert "₹" in sent


class TestHandleRebalance:
    async def test_no_context(self) -> None:
        reply = AsyncMock()
        await handle_rebalance(
            command="rebalance",
            args="",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
        )
        sent = reply.call_args[0][1]
        assert "unavailable" in sent

    async def test_no_holdings(self) -> None:
        reply = AsyncMock()
        fire_result = {"rows": []}
        holdings_result = {"rows": []}
        ctx = _mock_ctx(query_results=[fire_result, holdings_result])
        await handle_rebalance(
            command="rebalance",
            args="",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        sent = reply.call_args[0][1]
        assert "No holdings" in sent

    async def test_with_holdings(self) -> None:
        reply = AsyncMock()
        fire_result = {"rows": []}
        holdings_result = {
            "columns": [
                "symbol",
                "name",
                "asset_class",
                "quantity",
                "avg_price",
                "current_price",
                "current_value",
                "pnl",
                "pnl_pct",
                "source",
                "metadata",
            ],
            "rows": [_HOLDING_ROW],
        }
        ctx = _mock_ctx(query_results=[fire_result, holdings_result])
        await handle_rebalance(
            command="rebalance",
            args="",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        sent = reply.call_args[0][1]
        assert "Rebalance Analysis" in sent
        assert "EQUITY" in sent


class TestHandleResearch:
    async def test_no_query(self) -> None:
        reply = AsyncMock()
        await handle_research(
            command="research",
            args="",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
        )
        sent = reply.call_args[0][1]
        assert "Usage" in sent

    async def test_no_context(self) -> None:
        reply = AsyncMock()
        await handle_research(
            command="research",
            args="flexi cap",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
        )
        sent = reply.call_args[0][1]
        assert "unavailable" in sent

    async def test_with_results(self) -> None:
        reply = AsyncMock()
        ctx = AsyncMock()
        ctx.call_tool = AsyncMock(
            return_value=json.dumps(
                [
                    {"schemeCode": "119551", "schemeName": "Parag Parikh Flexi Cap"},
                    {"schemeCode": "100345", "schemeName": "UTI Flexi Cap"},
                ]
            )
        )
        await handle_research(
            command="research",
            args="flexi cap",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        sent = reply.call_args[0][1]
        assert "Parag Parikh" in sent
        assert "SEBI" in sent

    async def test_no_results(self) -> None:
        reply = AsyncMock()
        ctx = AsyncMock()
        ctx.call_tool = AsyncMock(return_value="[]")
        await handle_research(
            command="research",
            args="nonexistent fund xyz",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        sent = reply.call_args[0][1]
        assert "No matching" in sent


class TestHandleGold:
    async def test_no_context(self) -> None:
        reply = AsyncMock()
        await handle_gold(
            command="gold",
            args="",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
        )
        sent = reply.call_args[0][1]
        assert "unavailable" in sent

    async def test_no_data(self) -> None:
        reply = AsyncMock()
        ctx = _mock_ctx()
        ctx.send_to_memory = AsyncMock(return_value={"rows": []})
        await handle_gold(
            command="gold",
            args="",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        sent = reply.call_args[0][1]
        assert "No gold price data" in sent

    async def test_with_data(self) -> None:
        reply = AsyncMock()
        ctx = _mock_ctx()
        ctx.send_to_memory = AsyncMock(
            return_value={
                "rows": [
                    ["2026-05-13", "bangalore", 6500.0, 7100.0],
                    ["2026-05-12", "bangalore", 6480.0, 7080.0],
                    ["2026-05-11", "bangalore", 6450.0, 7050.0],
                ],
            }
        )
        await handle_gold(
            command="gold",
            args="",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        sent = reply.call_args[0][1]
        assert "Gold Prices" in sent
        assert "22K" in sent
        assert "30-day trend" in sent


class TestHandleHoldings:
    async def test_no_args(self) -> None:
        reply = AsyncMock()
        await handle_holdings(
            command="holdings",
            args="",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
        )
        sent = reply.call_args[0][1]
        assert "Usage" in sent

    async def test_add_no_type(self) -> None:
        reply = AsyncMock()
        ctx = _mock_ctx()
        await handle_holdings(
            command="holdings",
            args="add",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        sent = reply.call_args[0][1]
        assert "Specify holding type" in sent

    async def test_add_invalid_type(self) -> None:
        reply = AsyncMock()
        ctx = _mock_ctx()
        await handle_holdings(
            command="holdings",
            args="add STOCKS",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        sent = reply.call_args[0][1]
        assert "Unknown type" in sent

    async def test_add_fd_success(self) -> None:
        reply = AsyncMock()
        ctx = AsyncMock()
        ctx.send_to_memory = AsyncMock(return_value={"status": "ok"})
        await handle_holdings(
            command="holdings",
            args="add FD principal=500000 rate=7.1 bank=HDFC",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        sent = reply.call_args[0][1]
        assert "Added FD" in sent
        assert "₹500,000.00" in sent

    async def test_add_ppf(self) -> None:
        reply = AsyncMock()
        ctx = AsyncMock()
        ctx.send_to_memory = AsyncMock(return_value={"status": "ok"})
        await handle_holdings(
            command="holdings",
            args="add PPF balance=1500000",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        sent = reply.call_args[0][1]
        assert "Added PPF" in sent

    async def test_add_sgb(self) -> None:
        reply = AsyncMock()
        ctx = AsyncMock()
        ctx.send_to_memory = AsyncMock(return_value={"status": "ok"})
        await handle_holdings(
            command="holdings",
            args="add SGB units=10 purchase_price=4800",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        sent = reply.call_args[0][1]
        assert "Added SGB" in sent

    async def test_add_rd(self) -> None:
        reply = AsyncMock()
        ctx = AsyncMock()
        ctx.send_to_memory = AsyncMock(return_value={"status": "ok"})
        await handle_holdings(
            command="holdings",
            args="add RD monthly=10000 rate=6.5 tenure_months=24 bank=SBI",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        sent = reply.call_args[0][1]
        assert "Added RD" in sent

    async def test_add_gold(self) -> None:
        reply = AsyncMock()
        ctx = AsyncMock()
        ctx.send_to_memory = AsyncMock(return_value={"status": "ok"})
        await handle_holdings(
            command="holdings",
            args="add gold grams=50 purchase_price=5500",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        sent = reply.call_args[0][1]
        assert "Added GOLD" in sent

    async def test_add_loan(self) -> None:
        reply = AsyncMock()
        ctx = AsyncMock()
        ctx.send_to_memory = AsyncMock(return_value={"status": "ok"})
        await handle_holdings(
            command="holdings",
            args="add loan outstanding=5000000 bank=HDFC rate=8.5",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        sent = reply.call_args[0][1]
        assert "Added LOAN" in sent

    async def test_add_fd_missing_principal(self) -> None:
        reply = AsyncMock()
        ctx = _mock_ctx()
        await handle_holdings(
            command="holdings",
            args="add FD rate=7.1",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        sent = reply.call_args[0][1]
        assert "principal" in sent.lower()

    async def test_add_no_context(self) -> None:
        reply = AsyncMock()
        await handle_holdings(
            command="holdings",
            args="add FD principal=100000",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
        )
        sent = reply.call_args[0][1]
        assert "unavailable" in sent

    async def test_banks_no_data(self) -> None:
        reply = AsyncMock()
        ctx = _mock_ctx()
        ctx.send_to_memory = AsyncMock(return_value={"rows": []})
        await handle_holdings(
            command="holdings",
            args="banks",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        sent = reply.call_args[0][1]
        assert "No bank statements" in sent

    async def test_banks_with_data(self) -> None:
        reply = AsyncMock()
        ctx = _mock_ctx()
        ctx.send_to_memory = AsyncMock(
            return_value={
                "rows": [["hdfc", "2026-05-01"], ["sbi", "2026-04-15"]],
            }
        )
        await handle_holdings(
            command="holdings",
            args="banks",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        sent = reply.call_args[0][1]
        assert "HDFC" in sent
        assert "SBI" in sent

    async def test_banks_no_context(self) -> None:
        reply = AsyncMock()
        await handle_holdings(
            command="holdings",
            args="banks",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
        )
        sent = reply.call_args[0][1]
        assert "unavailable" in sent

    async def test_upload_no_bank(self) -> None:
        reply = AsyncMock()
        ctx = _mock_ctx()
        await handle_holdings(
            command="holdings",
            args="upload",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        sent = reply.call_args[0][1]
        assert "bank=HDFC" in sent

    async def test_upload_invalid_bank(self) -> None:
        reply = AsyncMock()
        ctx = _mock_ctx()
        await handle_holdings(
            command="holdings",
            args="upload bank=ICICI",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        sent = reply.call_args[0][1]
        assert "bank=HDFC" in sent

    async def test_upload_no_csv(self) -> None:
        reply = AsyncMock()
        ctx = _mock_ctx()
        await handle_holdings(
            command="holdings",
            args="upload bank=HDFC",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        sent = reply.call_args[0][1]
        assert "Ready to receive" in sent

    async def test_upload_no_context(self) -> None:
        reply = AsyncMock()
        await handle_holdings(
            command="holdings",
            args="upload bank=HDFC",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
        )
        sent = reply.call_args[0][1]
        assert "unavailable" in sent
