from __future__ import annotations

import json
import logging
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
