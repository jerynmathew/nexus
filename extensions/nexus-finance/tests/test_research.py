from __future__ import annotations

from nexus_finance.research import (
    fire_target_corpus,
    fire_years_to_target,
    required_monthly_sip,
    sip_future_value,
)


class TestFireYearsToTarget:
    def test_already_reached(self) -> None:
        assert fire_years_to_target(1_00_00_000, 50_000, 50_00_000) == 0.0

    def test_basic_calculation(self) -> None:
        years = fire_years_to_target(10_00_000, 50_000, 3_00_00_000)
        assert years is not None
        assert 10 < years < 25

    def test_zero_sip(self) -> None:
        assert fire_years_to_target(10_00_000, 0, 3_00_00_000) is None

    def test_unreachable(self) -> None:
        assert fire_years_to_target(100, 1, 999_99_99_999) is None


class TestFireTargetCorpus:
    def test_basic(self) -> None:
        corpus = fire_target_corpus(
            1_00_000, withdrawal_rate=0.04, inflation_rate=0.06, years_to_fire=10
        )
        assert corpus > 1_00_000 * 12 / 0.04

    def test_no_inflation(self) -> None:
        corpus = fire_target_corpus(
            1_00_000, withdrawal_rate=0.04, inflation_rate=0.0, years_to_fire=10
        )
        assert corpus == 1_00_000 * 12 / 0.04


class TestRequiredMonthlySip:
    def test_basic(self) -> None:
        sip = required_monthly_sip(10_00_000, 3_00_00_000, 15)
        assert sip > 0

    def test_already_enough(self) -> None:
        sip = required_monthly_sip(5_00_00_000, 3_00_00_000, 10)
        assert sip == 0.0

    def test_zero_years(self) -> None:
        assert required_monthly_sip(10_00_000, 3_00_00_000, 0) == 0.0


class TestSipFutureValue:
    def test_basic(self) -> None:
        fv = sip_future_value(50_000, 20)
        assert fv > 50_000 * 12 * 20

    def test_one_year(self) -> None:
        fv = sip_future_value(10_000, 1, annual_return=0.12)
        assert fv > 10_000 * 12
