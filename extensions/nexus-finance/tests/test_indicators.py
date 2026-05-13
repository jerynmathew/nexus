from __future__ import annotations

from nexus_finance.indicators import ema, rsi, sma


class TestSMA:
    def test_basic(self) -> None:
        result = sma([1, 2, 3, 4, 5], 3)
        assert result[0] is None
        assert result[1] is None
        assert result[2] == 2.0
        assert result[3] == 3.0
        assert result[4] == 4.0

    def test_period_larger_than_data(self) -> None:
        result = sma([1, 2], 5)
        assert all(v is None for v in result)

    def test_single_period(self) -> None:
        result = sma([10, 20, 30], 1)
        assert result == [10, 20, 30]


class TestEMA:
    def test_basic(self) -> None:
        result = ema([1, 2, 3, 4, 5], 3)
        assert len(result) == 5
        assert result[0] is None
        assert result[1] is None
        assert result[2] == 2.0

    def test_empty(self) -> None:
        assert ema([], 3) == []

    def test_zero_period(self) -> None:
        assert ema([1, 2, 3], 0) == []


class TestRSI:
    def test_insufficient_data(self) -> None:
        result = rsi([1, 2, 3], 14)
        assert all(v is None for v in result)

    def test_all_gains(self) -> None:
        prices = list(range(1, 20))
        result = rsi(prices, 14)
        assert result[-1] == 100.0

    def test_mixed(self) -> None:
        prices = [
            44,
            44.34,
            44.09,
            43.61,
            44.33,
            44.83,
            45.10,
            45.42,
            45.84,
            46.08,
            45.89,
            46.03,
            45.61,
            46.28,
            46.28,
            46.00,
        ]
        result = rsi(prices, 14)
        assert result[-1] is not None
        assert 0 <= result[-1] <= 100
