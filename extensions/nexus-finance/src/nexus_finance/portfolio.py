from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Holding:
    symbol: str
    name: str
    asset_class: str
    quantity: float
    avg_price: float
    current_price: float | None = None
    current_value: float | None = None
    pnl: float | None = None
    pnl_pct: float | None = None
    source: str = "manual"
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class PortfolioSnapshot:
    total_value: float
    equity_value: float
    mf_value: float
    etf_value: float
    gold_value: float
    debt_value: float
    day_change: float
    day_change_pct: float
    asset_allocation: dict[str, float]


def calculate_allocation(holdings: list[Holding]) -> dict[str, float]:
    total = sum(h.current_value or 0 for h in holdings)
    if total == 0:
        return {}
    allocation: dict[str, float] = {}
    for h in holdings:
        val = h.current_value or 0
        allocation[h.asset_class] = allocation.get(h.asset_class, 0) + val
    return {k: round(v / total * 100, 2) for k, v in allocation.items()}


def calculate_xirr(
    cashflows: list[tuple[str, float]],
) -> float | None:
    if len(cashflows) < 2:
        return None
    # TODO: implement Newton-Raphson XIRR
    return None
