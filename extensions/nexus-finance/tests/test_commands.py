from __future__ import annotations

from unittest.mock import AsyncMock

from nexus_finance.commands import (
    handle_fire,
    handle_gold,
    handle_holdings,
    handle_portfolio,
    handle_rebalance,
    handle_research,
)


def _mock_ctx(holdings_rows=None):
    ctx = AsyncMock()
    if holdings_rows is None:
        holdings_rows = []
    ctx.send_to_memory = AsyncMock(
        return_value={
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
    )
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
        ctx = _mock_ctx(
            holdings_rows=[
                [
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
                ],
            ]
        )
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
        ctx = _mock_ctx(
            holdings_rows=[
                [
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
                ],
            ]
        )
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
    async def test_progress(self) -> None:
        reply = AsyncMock()
        await handle_fire(
            command="fire", args="", tenant_id="t1", channel_id="c1", send_reply=reply
        )
        reply.assert_called_once()

    async def test_config(self) -> None:
        reply = AsyncMock()
        await handle_fire(
            command="fire", args="config", tenant_id="t1", channel_id="c1", send_reply=reply
        )
        reply.assert_called_once()


class TestHandleRebalance:
    async def test_rebalance(self) -> None:
        reply = AsyncMock()
        await handle_rebalance(
            command="rebalance", args="", tenant_id="t1", channel_id="c1", send_reply=reply
        )
        reply.assert_called_once()


class TestHandleResearch:
    async def test_no_query(self) -> None:
        reply = AsyncMock()
        await handle_research(
            command="research", args="", tenant_id="t1", channel_id="c1", send_reply=reply
        )
        sent = reply.call_args[0][1]
        assert "Usage" in sent

    async def test_with_query(self) -> None:
        reply = AsyncMock()
        await handle_research(
            command="research",
            args="best flexi cap fund",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
        )
        reply.assert_called_once()


class TestHandleGold:
    async def test_gold(self) -> None:
        reply = AsyncMock()
        await handle_gold(
            command="gold", args="", tenant_id="t1", channel_id="c1", send_reply=reply
        )
        reply.assert_called_once()


class TestHandleHoldings:
    async def test_no_args(self) -> None:
        reply = AsyncMock()
        await handle_holdings(
            command="holdings", args="", tenant_id="t1", channel_id="c1", send_reply=reply
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

    async def test_upload(self) -> None:
        reply = AsyncMock()
        await handle_holdings(
            command="holdings", args="upload", tenant_id="t1", channel_id="c1", send_reply=reply
        )
        reply.assert_called_once()

    async def test_banks(self) -> None:
        reply = AsyncMock()
        await handle_holdings(
            command="holdings", args="banks", tenant_id="t1", channel_id="c1", send_reply=reply
        )
        reply.assert_called_once()
