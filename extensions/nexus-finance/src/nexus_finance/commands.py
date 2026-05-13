from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from nexus.extensions import NexusContext

from nexus_finance.portfolio import (
    Holding,
    format_portfolio_detail,
    format_portfolio_summary,
    load_holdings_from_db,
    parse_zerodha_holdings,
    save_snapshot,
    sync_holdings_to_db,
)

logger = logging.getLogger(__name__)

_DISCLAIMER = (
    "\n\n_This is AI-generated analysis, not financial advice. "
    "Consult a SEBI-registered advisor before investing._"
)

_VALID_MANUAL_TYPES = {"sgb", "ppf", "fd", "rd", "gold", "loan"}


async def handle_portfolio(
    *,
    command: str,
    args: str,
    tenant_id: str,
    channel_id: str,
    send_reply: Callable[..., Awaitable[None]],
    nexus_context: NexusContext | None = None,
    **kwargs: Any,
) -> None:
    if not nexus_context:
        await send_reply(channel_id, "Portfolio service unavailable.")
        return

    holdings = await load_holdings_from_db(nexus_context, tenant_id)

    subcommand = args.strip().lower()
    if subcommand == "detail":
        text = format_portfolio_detail(holdings)
    elif subcommand == "sync":
        text = await _do_portfolio_sync(nexus_context, tenant_id)
    else:
        text = format_portfolio_summary(holdings)

    await send_reply(channel_id, text + _DISCLAIMER)


async def _do_portfolio_sync(ctx: NexusContext, tenant_id: str) -> str:
    raw = await ctx.call_tool("get_holdings")

    try:
        zerodha_data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return f"Failed to parse Zerodha response: {raw[:200]}"

    if isinstance(zerodha_data, dict) and "error" in zerodha_data:
        return f"Zerodha sync failed: {zerodha_data['error']}"

    if not isinstance(zerodha_data, list):
        return "Unexpected response format from Zerodha."

    holdings = parse_zerodha_holdings(zerodha_data)
    count = await sync_holdings_to_db(ctx, tenant_id, holdings)
    all_holdings = await load_holdings_from_db(ctx, tenant_id)
    await save_snapshot(ctx, tenant_id, all_holdings)
    return f"Synced {count} holdings from Zerodha.\n\n" + format_portfolio_summary(all_holdings)


async def handle_fire(
    *,
    command: str,
    args: str,
    tenant_id: str,
    channel_id: str,
    send_reply: Callable[..., Awaitable[None]],
    **kwargs: Any,
) -> None:
    subcommand = args.strip().lower()
    if subcommand == "config":
        await send_reply(channel_id, "FIRE config — not yet implemented.")
        return
    await send_reply(channel_id, "FIRE progress — not yet implemented.")


async def handle_rebalance(
    *,
    command: str,
    args: str,
    tenant_id: str,
    channel_id: str,
    send_reply: Callable[..., Awaitable[None]],
    **kwargs: Any,
) -> None:
    await send_reply(channel_id, "Rebalance suggestions — not yet implemented.")


async def handle_research(
    *,
    command: str,
    args: str,
    tenant_id: str,
    channel_id: str,
    send_reply: Callable[..., Awaitable[None]],
    **kwargs: Any,
) -> None:
    if not args.strip():
        await send_reply(
            channel_id,
            "Usage: /research <query>\n"
            "Examples:\n"
            "  /research best flexi cap fund\n"
            "  /research should I buy gold\n"
            "  /research compare PPFAS vs Parag Parikh",
        )
        return
    await send_reply(channel_id, f"Researching: {args.strip()} — not yet implemented.")


async def handle_gold(
    *,
    command: str,
    args: str,
    tenant_id: str,
    channel_id: str,
    send_reply: Callable[..., Awaitable[None]],
    **kwargs: Any,
) -> None:
    await send_reply(channel_id, "Gold prices — not yet implemented.")


async def handle_holdings(
    *,
    command: str,
    args: str,
    tenant_id: str,
    channel_id: str,
    send_reply: Callable[..., Awaitable[None]],
    nexus_context: NexusContext | None = None,
    **kwargs: Any,
) -> None:
    parts = args.strip().split(maxsplit=2) if args.strip() else []
    subcommand = parts[0].lower() if parts else ""

    if subcommand == "add":
        await _handle_holdings_add(parts[1:], tenant_id, channel_id, send_reply, nexus_context)
    elif subcommand == "upload":
        await send_reply(channel_id, "Upload bank statement — not yet implemented.")
    elif subcommand == "banks":
        await send_reply(channel_id, "Bank statement status — not yet implemented.")
    else:
        await send_reply(
            channel_id,
            "Usage:\n"
            "  /holdings add <type> <details> — manually add SGB/PPF/FD/RD/gold/loan\n"
            "  /holdings upload — upload bank statement PDF/CSV\n"
            "  /holdings banks — show last upload date per bank\n\n"
            "Add examples:\n"
            "  /holdings add FD principal=500000 rate=7.1 tenure_months=12 bank=HDFC\n"
            "  /holdings add PPF balance=1500000\n"
            "  /holdings add SGB units=10 purchase_price=4800 coupon_rate=2.5\n"
            "  /holdings add RD monthly=10000 rate=6.5 tenure_months=24 bank=SBI\n"
            "  /holdings add gold grams=50 purchase_price=5500",
        )


async def _handle_holdings_add(
    parts: list[str],
    tenant_id: str,
    channel_id: str,
    send_reply: Callable[..., Awaitable[None]],
    ctx: NexusContext | None,
) -> None:
    if not ctx:
        await send_reply(channel_id, "Holdings service unavailable.")
        return

    if not parts:
        await send_reply(
            channel_id,
            f"Specify holding type: {', '.join(t.upper() for t in sorted(_VALID_MANUAL_TYPES))}",
        )
        return

    holding_type = parts[0].lower()
    if holding_type not in _VALID_MANUAL_TYPES:
        await send_reply(
            channel_id,
            f"Unknown type: {parts[0]}. "
            f"Valid: {', '.join(t.upper() for t in sorted(_VALID_MANUAL_TYPES))}",
        )
        return

    detail_str = parts[1] if len(parts) > 1 else ""
    params = _parse_key_value_params(detail_str)

    holding = _build_manual_holding(holding_type, params)
    if isinstance(holding, str):
        await send_reply(channel_id, holding)
        return

    count = await sync_holdings_to_db(ctx, tenant_id, [holding])
    if count > 0:
        val_str = f"₹{holding.current_value:,.2f}" if holding.current_value else "N/A"
        await send_reply(
            channel_id,
            f"Added {holding_type.upper()}: **{holding.symbol}** — {val_str}",
        )
    else:
        await send_reply(channel_id, "Failed to save holding.")


def _parse_key_value_params(text: str) -> dict[str, str]:
    params: dict[str, str] = {}
    for token in text.split():
        if "=" in token:
            key, _, value = token.partition("=")
            params[key.lower()] = value
    return params


def _build_manual_holding(
    holding_type: str,
    params: dict[str, str],
) -> Holding | str:
    if holding_type == "fd":
        return _build_fd(params)
    if holding_type == "rd":
        return _build_rd(params)
    if holding_type == "ppf":
        return _build_ppf(params)
    if holding_type == "sgb":
        return _build_sgb(params)
    if holding_type == "gold":
        return _build_gold(params)
    if holding_type == "loan":
        return _build_loan(params)
    return f"Unknown type: {holding_type}"


def _build_fd(params: dict[str, str]) -> Holding | str:
    principal = params.get("principal")
    if not principal:
        return "FD requires: principal. Optional: rate, tenure_months, bank, maturity_date"
    try:
        principal_val = float(principal)
    except ValueError:
        return f"Invalid principal: {principal}"

    bank = params.get("bank", "UNKNOWN")
    rate = params.get("rate", "0")
    symbol = f"FD-{bank}-{principal}"

    return Holding(
        symbol=symbol,
        name=f"{bank} Fixed Deposit",
        asset_class="debt",
        quantity=1,
        avg_price=principal_val,
        current_price=principal_val,
        current_value=principal_val,
        pnl=0.0,
        pnl_pct=0.0,
        source="manual",
        metadata={
            "type": "fd",
            "bank": bank,
            "rate": rate,
            "tenure_months": params.get("tenure_months", ""),
            "maturity_date": params.get("maturity_date", ""),
        },
    )


def _build_rd(params: dict[str, str]) -> Holding | str:
    monthly = params.get("monthly")
    if not monthly:
        return "RD requires: monthly. Optional: rate, tenure_months, bank"
    try:
        monthly_val = float(monthly)
    except ValueError:
        return f"Invalid monthly amount: {monthly}"

    bank = params.get("bank", "UNKNOWN")
    tenure = int(params.get("tenure_months", "12"))
    total_deposited = monthly_val * tenure
    symbol = f"RD-{bank}-{int(monthly_val)}"

    return Holding(
        symbol=symbol,
        name=f"{bank} Recurring Deposit",
        asset_class="debt",
        quantity=1,
        avg_price=total_deposited,
        current_price=total_deposited,
        current_value=total_deposited,
        pnl=0.0,
        pnl_pct=0.0,
        source="manual",
        metadata={
            "type": "rd",
            "bank": bank,
            "monthly": str(monthly_val),
            "rate": params.get("rate", "0"),
            "tenure_months": str(tenure),
        },
    )


def _build_ppf(params: dict[str, str]) -> Holding | str:
    balance = params.get("balance")
    if not balance:
        return "PPF requires: balance. Optional: yearly_contribution"
    try:
        balance_val = float(balance)
    except ValueError:
        return f"Invalid balance: {balance}"

    return Holding(
        symbol="PPF",
        name="Public Provident Fund",
        asset_class="debt",
        quantity=1,
        avg_price=balance_val,
        current_price=balance_val,
        current_value=balance_val,
        pnl=0.0,
        pnl_pct=0.0,
        source="manual",
        metadata={
            "type": "ppf",
            "yearly_contribution": params.get("yearly_contribution", ""),
        },
    )


def _build_sgb(params: dict[str, str]) -> Holding | str:
    units = params.get("units")
    purchase_price = params.get("purchase_price")
    if not units or not purchase_price:
        return "SGB requires: units, purchase_price. Optional: coupon_rate, issue_date"
    try:
        units_val = float(units)
        price_val = float(purchase_price)
    except ValueError:
        return "Invalid units or purchase_price — must be numbers."

    total = units_val * price_val
    return Holding(
        symbol="SGB",
        name="Sovereign Gold Bond",
        asset_class="gold",
        quantity=units_val,
        avg_price=price_val,
        current_price=price_val,
        current_value=total,
        pnl=0.0,
        pnl_pct=0.0,
        source="manual",
        metadata={
            "type": "sgb",
            "coupon_rate": params.get("coupon_rate", "2.5"),
            "issue_date": params.get("issue_date", ""),
        },
    )


def _build_gold(params: dict[str, str]) -> Holding | str:
    grams = params.get("grams")
    purchase_price = params.get("purchase_price")
    if not grams or not purchase_price:
        return "Gold requires: grams, purchase_price (per gram)"
    try:
        grams_val = float(grams)
        price_val = float(purchase_price)
    except ValueError:
        return "Invalid grams or purchase_price — must be numbers."

    total = grams_val * price_val
    return Holding(
        symbol="GOLD-PHYSICAL",
        name="Physical/Digital Gold",
        asset_class="gold",
        quantity=grams_val,
        avg_price=price_val,
        current_price=price_val,
        current_value=total,
        pnl=0.0,
        pnl_pct=0.0,
        source="manual",
        metadata={"type": "gold"},
    )


def _build_loan(params: dict[str, str]) -> Holding | str:
    outstanding = params.get("outstanding")
    if not outstanding:
        return "Loan requires: outstanding. Optional: rate, emi, tenure_months, bank"
    try:
        outstanding_val = float(outstanding)
    except ValueError:
        return f"Invalid outstanding: {outstanding}"

    bank = params.get("bank", "UNKNOWN")
    symbol = f"LOAN-{bank}"

    return Holding(
        symbol=symbol,
        name=f"{bank} Loan",
        asset_class="debt",
        quantity=1,
        avg_price=outstanding_val,
        current_price=outstanding_val,
        current_value=-outstanding_val,
        pnl=0.0,
        pnl_pct=0.0,
        source="manual",
        metadata={
            "type": "loan",
            "bank": bank,
            "outstanding": str(outstanding_val),
            "rate": params.get("rate", ""),
            "emi": params.get("emi", ""),
            "tenure_months": params.get("tenure_months", ""),
        },
    )
