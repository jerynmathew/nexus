from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from nexus.extensions import NexusContext

from nexus_finance.commands import (
    handle_fire,
    handle_gold,
    handle_holdings,
    handle_portfolio,
    handle_rebalance,
    handle_research,
)
from nexus_finance.gold import parse_goodreturns_html
from nexus_finance.portfolio import (
    load_holdings_from_db,
    parse_zerodha_holdings,
    save_snapshot,
    sync_holdings_to_db,
)
from nexus_finance.schema import FINANCE_SCHEMA

logger = logging.getLogger(__name__)


class FinanceExtension:
    def __init__(self) -> None:
        self._ctx: NexusContext | None = None

    @property
    def name(self) -> str:
        return "nexus-finance"

    @property
    def version(self) -> str:
        from nexus_finance import __version__

        return __version__

    async def on_load(self, nexus: NexusContext) -> None:
        self._ctx = nexus
        nexus.register_schema(FINANCE_SCHEMA)
        nexus.register_skill_dir(Path(__file__).parent / "skills")
        nexus.register_command("portfolio", handle_portfolio)
        nexus.register_command("fire", handle_fire)
        nexus.register_command("rebalance", handle_rebalance)
        nexus.register_command("research", handle_research)
        nexus.register_command("gold", handle_gold)
        nexus.register_command("holdings", handle_holdings)
        nexus.register_signal_handler("scheduled_sync", self._sync_portfolio)
        nexus.register_signal_handler("finance_alert_check", self._check_alerts)
        nexus.register_signal_handler("gold_price_collect", self._collect_gold_prices)
        nexus.register_signal_handler("bank_statement_reminder", self._check_bank_reminders)
        nexus.register_signal_handler("maturity_alert", self._check_maturity_alerts)

    async def on_unload(self) -> None:
        self._ctx = None

    async def _sync_portfolio(self, payload: dict[str, Any]) -> None:
        if not self._ctx:
            return

        tenant_id = payload.get("tenant_id")
        if not tenant_id:
            logger.warning("scheduled_sync missing tenant_id")
            return

        raw = await self._ctx.call_tool("get_holdings")

        try:
            zerodha_data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.error("Failed to parse Zerodha holdings: %s", raw[:200])
            return

        if not isinstance(zerodha_data, list):
            logger.error("Unexpected Zerodha response type: %s", type(zerodha_data))
            return

        holdings = parse_zerodha_holdings(zerodha_data)
        count = await sync_holdings_to_db(self._ctx, tenant_id, holdings)
        logger.info("Synced %d holdings for tenant %s", count, tenant_id)

        all_holdings = await load_holdings_from_db(self._ctx, tenant_id)
        await save_snapshot(self._ctx, tenant_id, all_holdings)
        logger.info("Saved daily snapshot for tenant %s", tenant_id)

    async def _check_alerts(self, payload: dict[str, Any]) -> None:
        if not self._ctx:
            return

        tenant_id = payload.get("tenant_id")
        if not tenant_id:
            return

        threshold_pct = float(payload.get("threshold_pct", 2.0))

        result = await self._ctx.send_to_memory(
            "ext_query",
            {
                "sql": (
                    "SELECT total_value, day_change_pct FROM finance_snapshots"
                    " WHERE tenant_id = ? ORDER BY snapshot_date DESC LIMIT 2"
                ),
                "params": [tenant_id],
            },
        )
        rows = result.get("rows", [])
        if len(rows) < 2:
            return

        current_value = float(rows[0][0])
        previous_value = float(rows[1][0])
        if previous_value == 0:
            return

        change_pct = (current_value - previous_value) / previous_value * 100

        if abs(change_pct) >= threshold_pct:
            direction = "up" if change_pct > 0 else "down"
            change_abs = current_value - previous_value
            sign = "+" if change_abs >= 0 else ""
            logger.info(
                "Finance alert for %s: portfolio %s %.1f%% (%s₹%s)",
                tenant_id,
                direction,
                abs(change_pct),
                sign,
                f"{abs(change_abs):,.0f}",
            )

    async def _collect_gold_prices(self, payload: dict[str, Any]) -> None:
        if not self._ctx:
            return

        city = payload.get("city", "bangalore")
        url = f"https://www.goodreturns.in/gold-rates/{city}.htm"

        html = await self._ctx.call_tool("playwright_navigate", {"url": url})
        price = parse_goodreturns_html(html, city)
        if not price:
            logger.warning("Failed to parse gold prices for %s", city)
            return

        await self._ctx.send_to_memory(
            "ext_execute",
            {
                "sql": (
                    "INSERT INTO finance_gold_prices (date, city, gold_22k, gold_24k)"
                    " VALUES (date('now'), ?, ?, ?)"
                    " ON CONFLICT(date, city) DO UPDATE SET"
                    "  gold_22k=excluded.gold_22k, gold_24k=excluded.gold_24k"
                ),
                "params": [city, price.gold_22k, price.gold_24k],
            },
        )
        logger.info(
            "Gold prices stored for %s: 22K=%.2f, 24K=%.2f",
            city,
            price.gold_22k or 0,
            price.gold_24k or 0,
        )

    async def _check_bank_reminders(self, payload: dict[str, Any]) -> None:
        if not self._ctx:
            return

        tenant_id = payload.get("tenant_id")
        if not tenant_id:
            return

        stale_days = int(payload.get("stale_days", 30))

        result = await self._ctx.send_to_memory(
            "ext_query",
            {
                "sql": (
                    "SELECT bank, MAX(upload_date) as last_upload"
                    " FROM finance_bank_statements WHERE tenant_id = ?"
                    " GROUP BY bank"
                ),
                "params": [tenant_id],
            },
        )

        stale_banks: list[str] = []
        for row in result.get("rows", []):
            bank = row[0]
            last_upload = row[1]
            if not last_upload:
                stale_banks.append(bank.upper())
                continue

            try:
                upload_dt = datetime.fromisoformat(last_upload)
                age_days = (datetime.now() - upload_dt).days
                if age_days > stale_days:
                    stale_banks.append(f"{bank.upper()} ({age_days} days old)")
            except ValueError:
                stale_banks.append(bank.upper())

        if stale_banks:
            logger.info("Bank statement reminder for %s: %s", tenant_id, ", ".join(stale_banks))

    async def _check_maturity_alerts(self, payload: dict[str, Any]) -> None:
        if not self._ctx:
            return

        tenant_id = payload.get("tenant_id")
        if not tenant_id:
            return

        days_ahead = int(payload.get("days_ahead", 30))

        result = await self._ctx.send_to_memory(
            "ext_query",
            {
                "sql": (
                    "SELECT symbol, name, metadata FROM finance_holdings"
                    " WHERE tenant_id = ? AND metadata IS NOT NULL"
                ),
                "params": [tenant_id],
            },
        )

        for row in result.get("rows", []):
            try:
                meta = json.loads(row[2]) if row[2] else {}
            except (json.JSONDecodeError, TypeError):
                continue

            maturity_date = meta.get("maturity_date")
            if not maturity_date:
                continue

            try:
                mat_dt = datetime.strptime(maturity_date, "%Y-%m-%d")
                days_until = (mat_dt - datetime.now()).days
                if 0 <= days_until <= days_ahead:
                    logger.info(
                        "Maturity alert for %s: %s (%s) matures in %d days",
                        tenant_id,
                        row[0],
                        row[1],
                        days_until,
                    )
            except ValueError:
                continue
