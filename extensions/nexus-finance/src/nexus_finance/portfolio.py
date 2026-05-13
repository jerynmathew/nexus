from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from nexus.extensions import NexusContext

logger = logging.getLogger(__name__)

_ASSET_CLASS_MAP: dict[str, str] = {
    "EQ": "equity",
    "BE": "equity",
    "MF": "mf",
    "ETF": "etf",
    "SGD": "gold",
    "SGB": "gold",
}


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


def _classify_asset(exchange: str, tradingsymbol: str) -> str:
    return _ASSET_CLASS_MAP.get(exchange, "equity")


def parse_zerodha_holdings(raw: list[dict[str, Any]]) -> list[Holding]:
    holdings: list[Holding] = []
    for item in raw:
        quantity = float(item.get("quantity", 0))
        if quantity == 0:
            continue
        avg_price = float(item.get("average_price", 0))
        last_price = float(item.get("last_price", 0))
        current_value = quantity * last_price
        cost = quantity * avg_price
        pnl = current_value - cost
        pnl_pct = (pnl / cost * 100) if cost > 0 else 0.0

        exchange = item.get("exchange", "")
        asset_class = _classify_asset(exchange, item.get("tradingsymbol", ""))

        holdings.append(
            Holding(
                symbol=item.get("tradingsymbol", ""),
                name=item.get("tradingsymbol", ""),
                asset_class=asset_class,
                quantity=quantity,
                avg_price=avg_price,
                current_price=last_price,
                current_value=round(current_value, 2),
                pnl=round(pnl, 2),
                pnl_pct=round(pnl_pct, 2),
                source="zerodha",
                metadata={"exchange": exchange, "isin": item.get("isin", "")},
            )
        )
    return holdings


async def sync_holdings_to_db(
    ctx: NexusContext,
    tenant_id: str,
    holdings: list[Holding],
) -> int:
    count = 0
    for h in holdings:
        meta_json = json.dumps(h.metadata) if h.metadata else None
        result = await ctx.send_to_memory(
            "ext_execute",
            {
                "sql": (
                    "INSERT INTO finance_holdings"
                    " (tenant_id, symbol, name, asset_class, quantity, avg_price,"
                    "  current_price, current_value, pnl, pnl_pct, source, metadata, last_synced)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)"
                    " ON CONFLICT(tenant_id, symbol, source) DO UPDATE SET"
                    "  name=excluded.name, asset_class=excluded.asset_class,"
                    "  quantity=excluded.quantity, avg_price=excluded.avg_price,"
                    "  current_price=excluded.current_price, current_value=excluded.current_value,"
                    "  pnl=excluded.pnl, pnl_pct=excluded.pnl_pct,"
                    "  metadata=excluded.metadata, last_synced=CURRENT_TIMESTAMP"
                ),
                "params": [
                    tenant_id,
                    h.symbol,
                    h.name,
                    h.asset_class,
                    h.quantity,
                    h.avg_price,
                    h.current_price,
                    h.current_value,
                    h.pnl,
                    h.pnl_pct,
                    h.source,
                    meta_json,
                ],
            },
        )
        if result.get("status") == "ok":
            count += 1
    return count


async def load_holdings_from_db(
    ctx: NexusContext,
    tenant_id: str,
) -> list[Holding]:
    result = await ctx.send_to_memory(
        "ext_query",
        {
            "sql": (
                "SELECT symbol, name, asset_class, quantity, avg_price,"
                " current_price, current_value, pnl, pnl_pct, source, metadata"
                " FROM finance_holdings WHERE tenant_id = ?"
                " ORDER BY current_value DESC"
            ),
            "params": [tenant_id],
        },
    )
    if "error" in result:
        logger.error("Failed to load holdings: %s", result["error"])
        return []

    holdings: list[Holding] = []
    for row in result.get("rows", []):
        meta = json.loads(row[10]) if row[10] else None
        holdings.append(
            Holding(
                symbol=row[0],
                name=row[1],
                asset_class=row[2],
                quantity=float(row[3]),
                avg_price=float(row[4]),
                current_price=float(row[5]) if row[5] is not None else None,
                current_value=float(row[6]) if row[6] is not None else None,
                pnl=float(row[7]) if row[7] is not None else None,
                pnl_pct=float(row[8]) if row[8] is not None else None,
                source=row[9],
                metadata=meta,
            )
        )
    return holdings


async def save_snapshot(
    ctx: NexusContext,
    tenant_id: str,
    holdings: list[Holding],
) -> dict[str, Any]:
    allocation = calculate_allocation(holdings)
    total_value = sum(h.current_value or 0 for h in holdings)

    by_class: dict[str, float] = {}
    for h in holdings:
        val = h.current_value or 0
        by_class[h.asset_class] = by_class.get(h.asset_class, 0) + val

    snapshot = PortfolioSnapshot(
        total_value=round(total_value, 2),
        equity_value=round(by_class.get("equity", 0), 2),
        mf_value=round(by_class.get("mf", 0), 2),
        etf_value=round(by_class.get("etf", 0), 2),
        gold_value=round(by_class.get("gold", 0), 2),
        debt_value=round(by_class.get("debt", 0), 2),
        day_change=0.0,
        day_change_pct=0.0,
        asset_allocation=allocation,
    )

    result = await ctx.send_to_memory(
        "ext_execute",
        {
            "sql": (
                "INSERT INTO finance_snapshots"
                " (tenant_id, snapshot_date, total_value, equity_value, mf_value,"
                "  etf_value, gold_value, debt_value, day_change, day_change_pct,"
                "  asset_allocation)"
                " VALUES (?, date('now'), ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(tenant_id, snapshot_date) DO UPDATE SET"
                "  total_value=excluded.total_value, equity_value=excluded.equity_value,"
                "  mf_value=excluded.mf_value, etf_value=excluded.etf_value,"
                "  gold_value=excluded.gold_value, debt_value=excluded.debt_value,"
                "  day_change=excluded.day_change, day_change_pct=excluded.day_change_pct,"
                "  asset_allocation=excluded.asset_allocation"
            ),
            "params": [
                tenant_id,
                snapshot.total_value,
                snapshot.equity_value,
                snapshot.mf_value,
                snapshot.etf_value,
                snapshot.gold_value,
                snapshot.debt_value,
                snapshot.day_change,
                snapshot.day_change_pct,
                json.dumps(snapshot.asset_allocation),
            ],
        },
    )
    return result


def format_portfolio_summary(holdings: list[Holding]) -> str:
    if not holdings:
        return "No holdings found. Use `/holdings add` to add manual holdings."

    allocation = calculate_allocation(holdings)
    total_value = sum(h.current_value or 0 for h in holdings)
    total_pnl = sum(h.pnl or 0 for h in holdings)
    total_cost = sum(h.quantity * h.avg_price for h in holdings)
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0.0

    lines: list[str] = []
    lines.append("**Portfolio Summary**\n")
    lines.append(f"Total Value: ₹{total_value:,.2f}")

    pnl_sign = "+" if total_pnl >= 0 else ""
    lines.append(f"Total P&L: {pnl_sign}₹{total_pnl:,.2f} ({pnl_sign}{total_pnl_pct:.2f}%)")

    lines.append("\n**Allocation:**")
    for asset_class, pct in sorted(allocation.items(), key=lambda x: -x[1]):
        class_value = sum(h.current_value or 0 for h in holdings if h.asset_class == asset_class)
        lines.append(f"  {asset_class.upper()}: {pct:.1f}% (₹{class_value:,.2f})")

    lines.append(f"\nHoldings: {len(holdings)}")

    sources = {h.source for h in holdings}
    lines.append(f"Sources: {', '.join(sorted(sources))}")

    return "\n".join(lines)


def format_portfolio_detail(holdings: list[Holding]) -> str:
    if not holdings:
        return "No holdings found. Use `/holdings add` to add manual holdings."

    lines: list[str] = [format_portfolio_summary(holdings), "\n**Holdings Detail:**\n"]

    for h in holdings:
        pnl_sign = "+" if (h.pnl or 0) >= 0 else ""
        val_str = f"₹{h.current_value:,.2f}" if h.current_value else "N/A"
        pnl_str = f"{pnl_sign}₹{h.pnl:,.2f} ({pnl_sign}{h.pnl_pct:.1f}%)" if h.pnl else "N/A"
        lines.append(
            f"• **{h.symbol}** ({h.asset_class.upper()}) — {h.quantity:.2f} × ₹{h.avg_price:,.2f}"
        )
        lines.append(f"  Value: {val_str} | P&L: {pnl_str}")

    return "\n".join(lines)
