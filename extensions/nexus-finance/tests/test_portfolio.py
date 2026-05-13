from __future__ import annotations

from unittest.mock import AsyncMock

from nexus_finance.portfolio import (
    Holding,
    calculate_allocation,
    calculate_xirr,
    format_portfolio_detail,
    format_portfolio_summary,
    load_holdings_from_db,
    parse_zerodha_holdings,
    save_snapshot,
    sync_holdings_to_db,
)


class TestCalculateAllocation:
    def test_basic(self) -> None:
        holdings = [
            Holding("RELIANCE", "Reliance", "equity", 10, 2500, current_value=30000),
            Holding("PPFAS", "Parag Parikh", "mf", 100, 50, current_value=70000),
        ]
        alloc = calculate_allocation(holdings)
        assert alloc["equity"] == 30.0
        assert alloc["mf"] == 70.0

    def test_empty(self) -> None:
        assert calculate_allocation([]) == {}

    def test_zero_value(self) -> None:
        holdings = [Holding("X", "X", "equity", 0, 0, current_value=0)]
        assert calculate_allocation(holdings) == {}


class TestCalculateXirr:
    def test_insufficient_data(self) -> None:
        assert calculate_xirr([("2026-01-01", -10000)]) is None

    def test_basic_positive_return(self) -> None:
        flows = [("2025-01-01", -10000), ("2026-01-01", 12000)]
        result = calculate_xirr(flows)
        assert result is not None
        assert result > 0.15
        assert result < 0.25

    def test_negative_return(self) -> None:
        flows = [("2025-01-01", -10000), ("2026-01-01", 8000)]
        result = calculate_xirr(flows)
        assert result is not None
        assert result < 0

    def test_all_same_sign_returns_none(self) -> None:
        flows = [("2025-01-01", 10000), ("2026-01-01", 12000)]
        assert calculate_xirr(flows) is None

    def test_invalid_date_returns_none(self) -> None:
        flows = [("not-a-date", -10000), ("2026-01-01", 12000)]
        assert calculate_xirr(flows) is None

    def test_multiple_cashflows(self) -> None:
        flows = [
            ("2024-01-01", -10000),
            ("2024-07-01", -5000),
            ("2025-01-01", -5000),
            ("2026-01-01", 25000),
        ]
        result = calculate_xirr(flows)
        assert result is not None
        assert result > 0


class TestParseZerodhaHoldings:
    def test_basic_equity(self) -> None:
        raw = [
            {
                "tradingsymbol": "RELIANCE",
                "exchange": "EQ",
                "quantity": 10,
                "average_price": 2500,
                "last_price": 2700,
                "isin": "INE002A01018",
            }
        ]
        result = parse_zerodha_holdings(raw)
        assert len(result) == 1
        h = result[0]
        assert h.symbol == "RELIANCE"
        assert h.asset_class == "equity"
        assert h.quantity == 10
        assert h.avg_price == 2500
        assert h.current_price == 2700
        assert h.current_value == 27000.0
        assert h.pnl == 2000.0
        assert h.source == "zerodha"

    def test_mf_holding(self) -> None:
        raw = [
            {
                "tradingsymbol": "PPFAS-GR",
                "exchange": "MF",
                "quantity": 100,
                "average_price": 50,
                "last_price": 65,
            }
        ]
        result = parse_zerodha_holdings(raw)
        assert result[0].asset_class == "mf"

    def test_zero_quantity_skipped(self) -> None:
        raw = [
            {
                "tradingsymbol": "SOLD",
                "exchange": "EQ",
                "quantity": 0,
                "average_price": 100,
                "last_price": 110,
            }
        ]
        assert parse_zerodha_holdings(raw) == []

    def test_empty_input(self) -> None:
        assert parse_zerodha_holdings([]) == []


class TestSyncHoldingsToDb:
    async def test_sync_calls_memory(self) -> None:
        ctx = AsyncMock()
        ctx.send_to_memory = AsyncMock(return_value={"status": "ok"})

        holdings = [
            Holding("RELIANCE", "Reliance", "equity", 10, 2500, 2700, 27000, 2000, 8.0, "zerodha"),
        ]
        count = await sync_holdings_to_db(ctx, "t1", holdings)
        assert count == 1
        assert ctx.send_to_memory.call_count == 1
        call_args = ctx.send_to_memory.call_args
        assert call_args[0][0] == "ext_execute"
        assert "INSERT INTO finance_holdings" in call_args[0][1]["sql"]

    async def test_sync_counts_failures(self) -> None:
        ctx = AsyncMock()
        ctx.send_to_memory = AsyncMock(return_value={"error": "boom"})

        holdings = [Holding("X", "X", "equity", 1, 100)]
        count = await sync_holdings_to_db(ctx, "t1", holdings)
        assert count == 0


class TestLoadHoldingsFromDb:
    async def test_loads_rows(self) -> None:
        ctx = AsyncMock()
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
                "rows": [
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
                ],
            }
        )

        holdings = await load_holdings_from_db(ctx, "t1")
        assert len(holdings) == 1
        assert holdings[0].symbol == "RELIANCE"
        assert holdings[0].current_value == 27000.0

    async def test_handles_error(self) -> None:
        ctx = AsyncMock()
        ctx.send_to_memory = AsyncMock(return_value={"error": "db down"})

        holdings = await load_holdings_from_db(ctx, "t1")
        assert holdings == []


class TestSaveSnapshot:
    async def test_saves_snapshot(self) -> None:
        ctx = AsyncMock()
        ctx.send_to_memory = AsyncMock(return_value={"status": "ok"})

        holdings = [
            Holding("RELIANCE", "Reliance", "equity", 10, 2500, 2700, 27000, 2000, 8.0),
            Holding("PPFAS", "Parag Parikh", "mf", 100, 50, 65, 6500, 1500, 30.0),
        ]
        result = await save_snapshot(ctx, "t1", holdings)
        assert result.get("status") == "ok"
        call_args = ctx.send_to_memory.call_args
        assert "INSERT INTO finance_snapshots" in call_args[0][1]["sql"]


class TestFormatPortfolioSummary:
    def test_with_holdings(self) -> None:
        holdings = [
            Holding("RELIANCE", "Reliance", "equity", 10, 2500, 2700, 27000, 2000, 8.0),
            Holding("PPFAS", "Parag Parikh", "mf", 100, 50, 65, 6500, 1500, 30.0),
        ]
        text = format_portfolio_summary(holdings)
        assert "Portfolio Summary" in text
        assert "₹33,500.00" in text
        assert "EQUITY" in text
        assert "MF" in text

    def test_empty_holdings(self) -> None:
        text = format_portfolio_summary([])
        assert "/holdings add" in text


class TestFormatPortfolioDetail:
    def test_with_holdings(self) -> None:
        holdings = [
            Holding("RELIANCE", "Reliance", "equity", 10, 2500, 2700, 27000, 2000, 8.0),
        ]
        text = format_portfolio_detail(holdings)
        assert "Holdings Detail" in text
        assert "RELIANCE" in text

    def test_empty_holdings(self) -> None:
        text = format_portfolio_detail([])
        assert "/holdings add" in text
