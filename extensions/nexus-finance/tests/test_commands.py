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


class TestHandlePortfolio:
    async def test_summary(self) -> None:
        reply = AsyncMock()
        await handle_portfolio(
            command="portfolio", args="", tenant_id="t1", channel_id="c1", send_reply=reply
        )
        reply.assert_called_once()

    async def test_detail(self) -> None:
        reply = AsyncMock()
        await handle_portfolio(
            command="portfolio", args="detail", tenant_id="t1", channel_id="c1", send_reply=reply
        )
        reply.assert_called_once()


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

    async def test_add(self) -> None:
        reply = AsyncMock()
        await handle_holdings(
            command="holdings", args="add FD", tenant_id="t1", channel_id="c1", send_reply=reply
        )
        reply.assert_called_once()

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
