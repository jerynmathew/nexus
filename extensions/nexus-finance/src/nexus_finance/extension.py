from __future__ import annotations

from pathlib import Path

from nexus.extensions import NexusContext

from nexus_finance.commands import (
    handle_fire,
    handle_gold,
    handle_holdings,
    handle_portfolio,
    handle_rebalance,
    handle_research,
)
from nexus_finance.schema import FINANCE_SCHEMA


class FinanceExtension:
    @property
    def name(self) -> str:
        return "nexus-finance"

    @property
    def version(self) -> str:
        from nexus_finance import __version__

        return __version__

    async def on_load(self, nexus: NexusContext) -> None:
        nexus.register_schema(FINANCE_SCHEMA)
        nexus.register_skill_dir(Path(__file__).parent / "skills")
        nexus.register_command("portfolio", handle_portfolio)
        nexus.register_command("fire", handle_fire)
        nexus.register_command("rebalance", handle_rebalance)
        nexus.register_command("research", handle_research)
        nexus.register_command("gold", handle_gold)
        nexus.register_command("holdings", handle_holdings)

    async def on_unload(self) -> None:
        pass
