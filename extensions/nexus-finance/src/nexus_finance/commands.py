from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger(__name__)

_DISCLAIMER = (
    "\n\n_This is AI-generated analysis, not financial advice. "
    "Consult a SEBI-registered advisor before investing._"
)


async def handle_portfolio(
    *,
    command: str,
    args: str,
    tenant_id: str,
    channel_id: str,
    send_reply: Callable[..., Awaitable[None]],
    **kwargs: Any,
) -> None:
    subcommand = args.strip().lower()
    if subcommand == "detail":
        await send_reply(channel_id, "Portfolio detail view — not yet implemented.")
        return
    await send_reply(channel_id, "Portfolio summary — not yet implemented.")


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
    **kwargs: Any,
) -> None:
    subcommand = args.strip().lower().split(maxsplit=1)[0] if args.strip() else ""
    if subcommand == "add":
        await send_reply(channel_id, "Add holding — not yet implemented.")
    elif subcommand == "upload":
        await send_reply(channel_id, "Upload bank statement — not yet implemented.")
    elif subcommand == "banks":
        await send_reply(channel_id, "Bank statement status — not yet implemented.")
    else:
        await send_reply(
            channel_id,
            "Usage:\n"
            "  /holdings add <type> — manually add SGB/PPF/FD/RD\n"
            "  /holdings upload — upload bank statement PDF/CSV\n"
            "  /holdings banks — show last upload date per bank",
        )
