from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from nexus.extensions import NexusContext

from nexus_finance.charts import allocation_pie_chart, gold_price_chart
from nexus_finance.parsers.hdfc import parse_hdfc_csv
from nexus_finance.parsers.sbi import parse_sbi_csv
from nexus_finance.portfolio import (
    Holding,
    calculate_allocation,
    format_portfolio_detail,
    format_portfolio_summary,
    load_holdings_from_db,
    parse_zerodha_holdings,
    save_snapshot,
    sync_holdings_to_db,
)
from nexus_finance.research import (
    fire_target_corpus,
    fire_years_to_target,
    required_monthly_sip,
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
        text += _generate_portfolio_charts(nexus_context, holdings, tenant_id)

    dash_url = nexus_context.dashboard_url("/dashboard/finance")
    if dash_url:
        text += f"\n\n📊 Full dashboard → {dash_url}"

    await send_reply(channel_id, text + _DISCLAIMER)


def _generate_portfolio_charts(ctx: NexusContext, holdings: list[Holding], tenant_id: str) -> str:
    if not holdings:
        return ""
    lines: list[str] = []
    allocation = calculate_allocation(holdings)
    if allocation:
        chart_html = allocation_pie_chart(allocation)
        url = ctx.store_view(chart_html, title="Asset Allocation")
        if url:
            lines.append(f"\n📊 Allocation chart → {url}")
    return "\n".join(lines)


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
    nexus_context: NexusContext | None = None,
    **kwargs: Any,
) -> None:
    if not nexus_context:
        await send_reply(channel_id, "FIRE service unavailable.")
        return

    subcommand = args.strip().lower()
    if subcommand.startswith("config"):
        text = await _handle_fire_config(nexus_context, tenant_id, args.strip()[6:].strip())
    else:
        text = await _fire_progress(nexus_context, tenant_id)
    await send_reply(channel_id, text + _DISCLAIMER)


async def _load_fire_config(ctx: NexusContext, tenant_id: str) -> dict[str, Any]:
    result = await ctx.send_to_memory(
        "ext_query",
        {
            "sql": (
                "SELECT target_corpus, monthly_expenses, withdrawal_rate,"
                " inflation_rate, expected_return, target_allocation"
                " FROM finance_fire_config WHERE tenant_id = ?"
            ),
            "params": [tenant_id],
        },
    )
    rows = result.get("rows", [])
    if not rows:
        return {}
    row = rows[0]
    return {
        "target_corpus": row[0],
        "monthly_expenses": row[1],
        "withdrawal_rate": row[2] or 0.04,
        "inflation_rate": row[3] or 0.06,
        "expected_return": row[4] or 0.12,
        "target_allocation": json.loads(row[5]) if row[5] else {},
    }


async def _handle_fire_config(ctx: NexusContext, tenant_id: str, params_str: str) -> str:
    if not params_str:
        config = await _load_fire_config(ctx, tenant_id)
        if not config:
            return (
                "No FIRE config set. Use:\n"
                "  /fire config monthly_expenses=100000 target_years=15\n\n"
                "Optional: withdrawal_rate=0.04 inflation_rate=0.06 expected_return=0.12"
            )
        lines = ["**FIRE Configuration**\n"]
        if config.get("target_corpus"):
            lines.append(f"Target Corpus: ₹{config['target_corpus']:,.0f}")
        if config.get("monthly_expenses"):
            lines.append(f"Monthly Expenses: ₹{config['monthly_expenses']:,.0f}")
        lines.append(f"Withdrawal Rate: {config.get('withdrawal_rate', 0.04):.0%}")
        lines.append(f"Inflation Rate: {config.get('inflation_rate', 0.06):.0%}")
        lines.append(f"Expected Return: {config.get('expected_return', 0.12):.0%}")
        if config.get("target_allocation"):
            lines.append(f"Target Allocation: {config['target_allocation']}")
        return "\n".join(lines)

    params = _parse_key_value_params(params_str)
    monthly_expenses = float(params.get("monthly_expenses", "0"))
    target_years = int(params.get("target_years", "15"))
    withdrawal_rate = float(params.get("withdrawal_rate", "0.04"))
    inflation_rate = float(params.get("inflation_rate", "0.06"))
    expected_return = float(params.get("expected_return", "0.12"))
    target_alloc = params.get("target_allocation", '{"equity": 75, "debt": 15, "gold": 10}')

    target_corpus = fire_target_corpus(
        monthly_expenses, withdrawal_rate, inflation_rate, target_years
    )

    await ctx.send_to_memory(
        "ext_execute",
        {
            "sql": (
                "INSERT INTO finance_fire_config"
                " (tenant_id, target_corpus, monthly_expenses, withdrawal_rate,"
                "  inflation_rate, expected_return, target_allocation)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(tenant_id) DO UPDATE SET"
                "  target_corpus=excluded.target_corpus,"
                "  monthly_expenses=excluded.monthly_expenses,"
                "  withdrawal_rate=excluded.withdrawal_rate,"
                "  inflation_rate=excluded.inflation_rate,"
                "  expected_return=excluded.expected_return,"
                "  target_allocation=excluded.target_allocation"
            ),
            "params": [
                tenant_id,
                target_corpus,
                monthly_expenses,
                withdrawal_rate,
                inflation_rate,
                expected_return,
                target_alloc,
            ],
        },
    )
    return (
        f"FIRE config saved.\n"
        f"Target Corpus: ₹{target_corpus:,.0f}\n"
        f"Monthly Expenses: ₹{monthly_expenses:,.0f}\n"
        f"Withdrawal Rate: {withdrawal_rate:.0%}\n"
        f"Inflation Rate: {inflation_rate:.0%}\n"
        f"Expected Return: {expected_return:.0%}"
    )


async def _fire_progress(ctx: NexusContext, tenant_id: str) -> str:
    config = await _load_fire_config(ctx, tenant_id)
    if not config or not config.get("target_corpus"):
        return "FIRE config not set. Run `/fire config monthly_expenses=100000 target_years=15`"

    holdings = await load_holdings_from_db(ctx, tenant_id)
    current_corpus = sum(h.current_value or 0 for h in holdings)
    target = config["target_corpus"]
    monthly_expenses = config.get("monthly_expenses", 0)
    expected_return = config.get("expected_return", 0.12)

    pct_complete = (current_corpus / target * 100) if target > 0 else 0
    bar_filled = int(pct_complete / 5)
    bar = "█" * bar_filled + "░" * (20 - bar_filled)

    lines = ["**FIRE Progress**\n"]
    lines.append(f"Corpus: ₹{current_corpus:,.0f} / ₹{target:,.0f}")
    lines.append(f"Progress: [{bar}] {pct_complete:.1f}%")

    monthly_sip_estimate = monthly_expenses * 0.5 if monthly_expenses else 0
    if monthly_sip_estimate > 0:
        years = fire_years_to_target(current_corpus, monthly_sip_estimate, target, expected_return)
        if years is not None:
            lines.append(f"\nAt ₹{monthly_sip_estimate:,.0f}/month SIP → FIRE in {years:.1f} years")

        sip_10y = required_monthly_sip(current_corpus, target, 10, expected_return)
        sip_15y = required_monthly_sip(current_corpus, target, 15, expected_return)
        lines.append(f"To FIRE in 10 years: ₹{sip_10y:,.0f}/month SIP")
        lines.append(f"To FIRE in 15 years: ₹{sip_15y:,.0f}/month SIP")

    allocation = calculate_allocation(holdings)
    if allocation:
        lines.append("\n**Current Allocation:**")
        for ac, pct in sorted(allocation.items(), key=lambda x: -x[1]):
            lines.append(f"  {ac.upper()}: {pct:.1f}%")

    return "\n".join(lines)


async def handle_rebalance(
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
        await send_reply(channel_id, "Rebalance service unavailable.")
        return

    config = await _load_fire_config(nexus_context, tenant_id)
    target_alloc = config.get("target_allocation", {})
    if not target_alloc:
        target_alloc = {"equity": 75, "debt": 15, "gold": 10}

    holdings = await load_holdings_from_db(nexus_context, tenant_id)
    if not holdings:
        await send_reply(channel_id, "No holdings found. Add holdings first." + _DISCLAIMER)
        return

    current_alloc = calculate_allocation(holdings)
    total_value = sum(h.current_value or 0 for h in holdings)

    lines = ["**Rebalance Analysis**\n"]
    lines.append(f"Total Portfolio: ₹{total_value:,.0f}\n")
    lines.append(f"{'Asset':<10} {'Current':>10} {'Target':>10} {'Delta':>10} {'Action':>15}")
    lines.append("-" * 58)

    for asset_class in sorted(set(list(current_alloc.keys()) + list(target_alloc.keys()))):
        current_pct = current_alloc.get(asset_class, 0)
        target_pct = float(target_alloc.get(asset_class, 0))
        delta_pct = current_pct - target_pct
        delta_value = total_value * delta_pct / 100

        if abs(delta_pct) < 1:
            action = "On target"
        elif delta_pct > 0:
            action = f"Reduce ₹{abs(delta_value):,.0f}"
        else:
            action = f"Add ₹{abs(delta_value):,.0f}"

        lines.append(
            f"{asset_class.upper():<10} {current_pct:>9.1f}% {target_pct:>9.1f}%"
            f" {delta_pct:>+9.1f}% {action:>15}"
        )

    await send_reply(channel_id, "\n".join(lines) + _DISCLAIMER)


async def handle_research(
    *,
    command: str,
    args: str,
    tenant_id: str,
    channel_id: str,
    send_reply: Callable[..., Awaitable[None]],
    nexus_context: NexusContext | None = None,
    **kwargs: Any,
) -> None:
    query = args.strip()
    if not query:
        await send_reply(
            channel_id,
            "Usage: /research <query>\n"
            "Examples:\n"
            "  /research best flexi cap fund\n"
            "  /research should I buy gold\n"
            "  /research compare PPFAS vs Parag Parikh",
        )
        return

    if not nexus_context:
        await send_reply(channel_id, "Research service unavailable.")
        return

    lines = [f"**Research: {query}**\n"]

    mf_result = await nexus_context.call_tool("search_funds", {"query": query})
    try:
        funds = json.loads(mf_result)
    except (json.JSONDecodeError, TypeError):
        funds = []

    if isinstance(funds, list) and funds:
        lines.append("**Matching Mutual Funds:**")
        for fund in funds[:5]:
            code = fund.get("schemeCode", "")
            name = fund.get("schemeName", "")
            lines.append(f"  • {name} (Code: {code})")

        nav_details: list[str] = []
        for fund in funds[:3]:
            code = fund.get("schemeCode", "")
            if code:
                nav_raw = await nexus_context.call_tool("get_latest_nav", {"scheme_code": code})
                try:
                    nav_data = json.loads(nav_raw)
                    if isinstance(nav_data, dict) and nav_data.get("nav"):
                        name = nav_data.get("scheme_name", code)
                        category = nav_data.get("scheme_category", "")
                        nav_val = nav_data.get("nav", "")
                        nav_date = nav_data.get("date", "")
                        nav_details.append(
                            f"  **{name}**\n"
                            f"    Category: {category}\n"
                            f"    NAV: ₹{nav_val} ({nav_date})"
                        )
                except (json.JSONDecodeError, TypeError):
                    pass

        if nav_details:
            lines.append("\n**NAV Details (top 3):**")
            lines.extend(nav_details)

        if nexus_context.llm:
            fund_summary = "\n".join(nav_details) if nav_details else "No NAV data available"
            research_model = nexus_context.resolve_model()
            try:
                response = await nexus_context.llm.chat(
                    model=research_model,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a SEBI-compliant mutual fund research analyst. "
                                "Provide brief comparative analysis. Always include the disclaimer "
                                "that this is not financial advice."
                            ),
                        },
                        {
                            "role": "user",
                            "content": f"Query: {query}\n\nFund data:\n{fund_summary}\n\n"
                            "Provide a brief (3-4 sentence) comparative analysis.",
                        },
                    ],
                )
                if response.content:
                    lines.append(f"\n**Analysis:**\n{response.content}")
            except Exception:
                logger.debug("LLM analysis unavailable for research query")

        lines.append(f"\n{len(funds)} funds found.")
    else:
        lines.append("No matching mutual funds found for this query.")

    await send_reply(channel_id, "\n".join(lines) + _DISCLAIMER)


async def handle_gold(
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
        await send_reply(channel_id, "Gold service unavailable.")
        return

    result = await nexus_context.send_to_memory(
        "ext_query",
        {
            "sql": (
                "SELECT date, city, gold_22k, gold_24k FROM finance_gold_prices"
                " ORDER BY date DESC LIMIT 30"
            ),
            "params": [],
        },
    )
    rows = result.get("rows", [])

    if not rows:
        await send_reply(
            channel_id,
            "No gold price data available yet.\n"
            "Gold prices are collected daily via the gold-analysis skill." + _DISCLAIMER,
        )
        return

    latest = rows[0]
    lines = ["**Gold Prices (India)**\n"]
    lines.append(f"Date: {latest[0]}")
    lines.append(f"City: {latest[1].title()}")
    if latest[2]:
        lines.append(f"22K: ₹{float(latest[2]):,.2f}/gram")
    if latest[3]:
        lines.append(f"24K: ₹{float(latest[3]):,.2f}/gram")

    if len(rows) > 1:
        dates_rev = [r[0] for r in reversed(rows) if r[2]]
        prices_22k = [float(r[2]) for r in reversed(rows) if r[2]]
        if len(prices_22k) >= 2:
            change = prices_22k[-1] - prices_22k[0]
            pct = (change / prices_22k[0] * 100) if prices_22k[0] > 0 else 0
            sign = "+" if change >= 0 else ""
            lines.append(f"\n30-day trend: {sign}₹{change:,.2f} ({sign}{pct:.2f}%)")

        if len(prices_22k) >= 3:
            chart_html = gold_price_chart(dates_rev, prices_22k)
            url = nexus_context.store_view(chart_html, title="Gold Price Trend")
            if url:
                lines.append(f"📈 Gold chart → {url}")

    lines.append(f"\nData points: {len(rows)}")
    await send_reply(channel_id, "\n".join(lines) + _DISCLAIMER)


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
        await _handle_holdings_upload(parts[1:], tenant_id, channel_id, send_reply, nexus_context)
    elif subcommand == "banks":
        await _handle_holdings_banks(tenant_id, channel_id, send_reply, nexus_context)
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


async def _handle_holdings_banks(
    tenant_id: str,
    channel_id: str,
    send_reply: Callable[..., Awaitable[None]],
    ctx: NexusContext | None,
) -> None:
    if not ctx:
        await send_reply(channel_id, "Holdings service unavailable.")
        return

    result = await ctx.send_to_memory(
        "ext_query",
        {
            "sql": (
                "SELECT bank, MAX(upload_date) as last_upload"
                " FROM finance_bank_statements WHERE tenant_id = ?"
                " GROUP BY bank ORDER BY bank"
            ),
            "params": [tenant_id],
        },
    )
    rows = result.get("rows", [])

    if not rows:
        await send_reply(
            channel_id,
            "No bank statements uploaded yet.\n"
            "Use `/holdings upload bank=HDFC` with CSV content to upload.",
        )
        return

    lines = ["**Bank Statement Status**\n"]
    for row in rows:
        bank = row[0].upper()
        last_upload = row[1]
        lines.append(f"  {bank}: last uploaded {last_upload}")

    await send_reply(channel_id, "\n".join(lines))


async def _handle_holdings_upload(
    parts: list[str],
    tenant_id: str,
    channel_id: str,
    send_reply: Callable[..., Awaitable[None]],
    ctx: NexusContext | None,
) -> None:
    if not ctx:
        await send_reply(channel_id, "Holdings service unavailable.")
        return

    params = _parse_key_value_params(" ".join(parts)) if parts else {}
    bank = params.get("bank", "").lower()
    if bank not in ("hdfc", "sbi"):
        await send_reply(
            channel_id,
            "Usage: `/holdings upload bank=HDFC` (or SBI)\n"
            "Then send your bank statement CSV as a message.",
        )
        return

    csv_content = params.get("csv", "")
    if not csv_content:
        await send_reply(
            channel_id,
            f"Ready to receive {bank.upper()} CSV statement.\n"
            "Paste the CSV content or send as a document.",
        )
        return

    if bank == "hdfc":
        parsed = parse_hdfc_csv(csv_content)
        balance = parsed.account_balance
        txn_count = parsed.raw_transactions
    else:
        parsed = parse_sbi_csv(csv_content)
        balance = parsed.account_balance
        txn_count = parsed.raw_transactions

    await ctx.send_to_memory(
        "ext_execute",
        {
            "sql": (
                "INSERT INTO finance_bank_statements"
                " (tenant_id, bank, upload_date, parsed_data, raw_filename)"
                " VALUES (?, ?, CURRENT_TIMESTAMP, ?, ?)"
            ),
            "params": [
                tenant_id,
                bank,
                json.dumps({"balance": balance, "transactions": txn_count}),
                f"{bank}_upload",
            ],
        },
    )

    lines = [f"**{bank.upper()} Statement Processed**\n"]
    lines.append(f"Transactions: {txn_count}")
    if balance is not None:
        lines.append(f"Account Balance: ₹{balance:,.2f}")

    await send_reply(channel_id, "\n".join(lines))
