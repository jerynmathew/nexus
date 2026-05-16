from __future__ import annotations

from typing import Any

from nexus.media.handler import MediaHandler


def is_help_query(text: str) -> bool:
    lower = text.lower().strip()
    patterns = [
        "what commands",
        "what can you do",
        "what are the commands",
        "available commands",
        "list commands",
        "help",
        "/help",
        "show commands",
    ]
    return any(p in lower for p in patterns)


def build_help_response(ext_commands: dict[str, Any]) -> str:
    cmd_descriptions = {
        "actions": "Manage action items — add, list, done, priority, block",
        "delegate": "Track delegations — add, list, done",
        "meetings": "Track meetings — add, list, notes",
        "next": "Show highest-priority action item",
        "portfolio": "Portfolio summary — value, P&L, allocation",
        "fire": "FIRE progress — corpus vs target, SIP projections",
        "rebalance": "Rebalance suggestions vs target allocation",
        "research": "Research mutual funds",
        "gold": "Gold price data and trends",
        "holdings": "Manage holdings — add FD/PPF/SGB/gold/loan, upload, banks",
        "status": "Check Nexus system health",
    }

    lines = ["**Available Commands**\n"]

    work_cmds = ["actions", "delegate", "meetings", "next"]
    finance_cmds = ["portfolio", "fire", "rebalance", "research", "gold", "holdings"]
    system_cmds = ["status"]

    lines.append("**Work**")
    for cmd in work_cmds:
        if cmd in ext_commands or cmd in ("status",):
            desc = cmd_descriptions.get(cmd, "")
            lines.append(f"• /{cmd} — {desc}")

    lines.append("\n**Finance**")
    for cmd in finance_cmds:
        if cmd in ext_commands:
            desc = cmd_descriptions.get(cmd, "")
            lines.append(f"• /{cmd} — {desc}")

    lines.append("\n**System**")
    for cmd in system_cmds:
        desc = cmd_descriptions.get(cmd, "")
        lines.append(f"• /{cmd} — {desc}")

    lines.append(
        "\nYou can also ask me anything in natural language — "
        "check email, calendar, search the web, and more."
    )

    return "\n".join(lines)


def build_capabilities_section(
    ext_commands: dict[str, Any],
    mcp: Any | None,
    media_handler: MediaHandler | None,
) -> str:
    lines: list[str] = ["# Available Capabilities"]

    if mcp:
        tools = mcp.all_tool_schemas()
        if tools:
            lines.append(f"\nYou have {len(tools)} tools available via MCP.")
        else:
            lines.append("\nNo MCP tools currently connected.")
    else:
        lines.append(
            "\nNo MCP connection. You cannot access email, calendar, or external services.",
        )

    if ext_commands:
        lines.append("\n## User Slash Commands (IMPORTANT)")
        lines.append(
            "These are the PRIMARY commands available to the user. "
            "When asked about available commands, list THESE FIRST. "
            "These are NOT tools — the user types them directly."
        )
        cmd_descriptions = {
            "actions": "Manage action items — add, list, done, priority, block",
            "delegate": "Track delegations to people — add, list, done",
            "meetings": "Track meetings — add, list, notes",
            "next": "Show highest-priority action item",
            "portfolio": "Portfolio summary — value, P&L, allocation",
            "fire": "FIRE progress — corpus vs target, SIP projections",
            "rebalance": "Rebalance suggestions vs target allocation",
            "research": "Research mutual funds via MFapi.in",
            "gold": "Gold price data and trends",
            "holdings": "Manage holdings — add FD/PPF/SGB/gold/loan, upload, banks",
        }
        for cmd_name in sorted(ext_commands):
            desc = cmd_descriptions.get(cmd_name, "")
            lines.append(f"  /{cmd_name} — {desc}" if desc else f"  /{cmd_name}")

    if media_handler:
        if media_handler.has_vision:
            lines.append("\nYou can analyze images sent by the user.")
    else:
        lines.append("\nVoice and image processing are not available.")

    lines.append("\n## Formatting")
    lines.append(
        "Use markdown: **bold**, *italic*, [links](url), `code`. "
        "Use **bold** for headings instead of ##. Use • for bullet lists."
    )

    return "\n".join(lines)
