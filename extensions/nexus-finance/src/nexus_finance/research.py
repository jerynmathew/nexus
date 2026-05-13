from __future__ import annotations


def fire_years_to_target(
    current_corpus: float,
    monthly_sip: float,
    target_corpus: float,
    annual_return: float = 0.12,
) -> float | None:
    if monthly_sip <= 0 or annual_return <= 0:
        return None
    monthly_rate = annual_return / 12
    if current_corpus >= target_corpus:
        return 0.0

    months = 0
    corpus = current_corpus
    while corpus < target_corpus and months < 1200:
        corpus = corpus * (1 + monthly_rate) + monthly_sip
        months += 1

    if months >= 1200:
        return None
    return round(months / 12, 1)


def fire_target_corpus(
    monthly_expenses: float,
    withdrawal_rate: float = 0.04,
    inflation_rate: float = 0.06,
    years_to_fire: int = 10,
) -> float:
    future_monthly = monthly_expenses * ((1 + inflation_rate) ** years_to_fire)
    annual_expenses = future_monthly * 12
    return round(annual_expenses / withdrawal_rate)


def required_monthly_sip(
    current_corpus: float,
    target_corpus: float,
    years: int,
    annual_return: float = 0.12,
) -> float:
    if years <= 0:
        return 0.0
    monthly_rate = annual_return / 12
    months = years * 12
    future_corpus_from_current = current_corpus * ((1 + monthly_rate) ** months)
    remaining = target_corpus - future_corpus_from_current
    if remaining <= 0:
        return 0.0
    sip = remaining * monthly_rate / (((1 + monthly_rate) ** months) - 1)
    return round(sip)


def sip_future_value(
    monthly_sip: float,
    years: int,
    annual_return: float = 0.12,
) -> float:
    monthly_rate = annual_return / 12
    months = years * 12
    fv = monthly_sip * (((1 + monthly_rate) ** months - 1) / monthly_rate) * (1 + monthly_rate)
    return round(fv)
