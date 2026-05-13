from __future__ import annotations

from nexus_finance.portfolio import Holding, calculate_allocation, calculate_xirr


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

    def test_stub_returns_none(self) -> None:
        flows = [("2025-01-01", -10000), ("2026-01-01", 12000)]
        assert calculate_xirr(flows) is None
