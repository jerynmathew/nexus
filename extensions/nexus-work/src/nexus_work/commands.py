from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from nexus.extensions import NexusContext

from nexus_work.priority import score_action

logger = logging.getLogger(__name__)

_STATUS_ICONS = {"open": "⏳", "in_progress": "🔄", "done": "✅", "overdue": "❌"}
_PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


async def handle_actions(
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
        await send_reply(channel_id, "Actions service unavailable.")
        return

    parts = args.strip().split(maxsplit=1) if args.strip() else []
    subcommand = parts[0].lower() if parts else ""
    rest = parts[1] if len(parts) > 1 else ""

    if subcommand == "add":
        await _actions_add(nexus_context, tenant_id, channel_id, send_reply, rest)
    elif subcommand == "done":
        await _actions_done(nexus_context, tenant_id, channel_id, send_reply, rest)
    elif subcommand == "all":
        await _actions_list(nexus_context, tenant_id, channel_id, send_reply, include_done=True)
    else:
        await _actions_list(nexus_context, tenant_id, channel_id, send_reply)


async def _actions_add(
    ctx: NexusContext,
    tenant_id: str,
    channel_id: str,
    send_reply: Callable[..., Awaitable[None]],
    text: str,
) -> None:
    if not text:
        await send_reply(
            channel_id,
            "Usage: /actions add <title> [due=DATE] [priority=high] [for=PERSON]\n\n"
            "Examples:\n"
            "  /actions add Review Sarah's PR due=tomorrow priority=high\n"
            "  /actions add Write migration runbook due=2026-05-16\n"
            "  /actions add Reply to infra team",
        )
        return

    params = _extract_inline_params(text)
    title = params["title"]
    due_date = params.get("due")
    priority = params.get("priority", "medium")
    assigned_to = params.get("for", "self")

    await ctx.send_to_memory(
        "ext_execute",
        {
            "sql": (
                "INSERT INTO work_actions"
                " (tenant_id, title, status, priority, due_date, source,"
                "  assigned_to, assigned_by)"
                " VALUES (?, ?, 'open', ?, ?, 'manual', ?, 'self')"
            ),
            "params": [tenant_id, title, priority, due_date, assigned_to],
        },
    )
    due_str = f" (due {due_date})" if due_date else ""
    await send_reply(channel_id, f"Added: **{title}**{due_str} [{priority}]")


async def _actions_done(
    ctx: NexusContext,
    tenant_id: str,
    channel_id: str,
    send_reply: Callable[..., Awaitable[None]],
    id_str: str,
) -> None:
    if not id_str.strip().isdigit():
        await send_reply(channel_id, "Usage: /actions done <id>")
        return

    action_id = int(id_str.strip())
    result = await ctx.send_to_memory(
        "ext_execute",
        {
            "sql": (
                "UPDATE work_actions SET status='done', completed_at=CURRENT_TIMESTAMP"
                " WHERE id=? AND tenant_id=?"
            ),
            "params": [action_id, tenant_id],
        },
    )
    if result.get("status") == "ok":
        await send_reply(channel_id, f"✅ Action #{action_id} marked done.")
    else:
        await send_reply(channel_id, f"Failed to update action #{action_id}.")


async def _actions_list(
    ctx: NexusContext,
    tenant_id: str,
    channel_id: str,
    send_reply: Callable[..., Awaitable[None]],
    include_done: bool = False,
) -> None:
    status_filter = "" if include_done else " AND status != 'done'"
    result = await ctx.send_to_memory(
        "ext_query",
        {
            "sql": (
                "SELECT id, title, status, priority, due_date, assigned_to"
                f" FROM work_actions WHERE tenant_id = ?{status_filter}"
                " ORDER BY created_at DESC"
            ),
            "params": [tenant_id],
        },
    )
    rows = result.get("rows", [])
    if not rows:
        await send_reply(channel_id, "No action items. Use `/actions add` to create one.")
        return

    scored = []
    for row in rows:
        action = {
            "id": row[0],
            "title": row[1],
            "status": row[2],
            "priority": row[3],
            "due_date": row[4],
            "assigned_to": row[5],
        }
        action["score"] = score_action(action)
        scored.append(action)

    scored.sort(key=lambda a: a["score"], reverse=True)

    lines = ["**Action Items**\n"]
    for a in scored:
        icon = _STATUS_ICONS.get(a["status"], "•")
        due = f" — due {a['due_date']}" if a["due_date"] else ""
        assignee = f" → {a['assigned_to']}" if a["assigned_to"] != "self" else ""
        lines.append(f"{icon} #{a['id']} **{a['title']}** [{a['priority']}]{due}{assignee}")

    lines.append(f"\n{len(scored)} item(s). `/actions done <id>` to complete.")
    dash_url = ctx.dashboard_url("/dashboard/work")
    if dash_url:
        lines.append(f"📋 Full dashboard → {dash_url}")
    await send_reply(channel_id, "\n".join(lines))


async def handle_delegate(
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
        await send_reply(channel_id, "Delegation service unavailable.")
        return

    parts = args.strip().split(maxsplit=1) if args.strip() else []
    subcommand = parts[0].lower() if parts else ""
    rest = parts[1] if len(parts) > 1 else ""

    if subcommand == "add":
        await _delegate_add(nexus_context, tenant_id, channel_id, send_reply, rest)
    elif subcommand == "done":
        await _delegate_done(nexus_context, tenant_id, channel_id, send_reply, rest)
    else:
        await _delegate_list(nexus_context, tenant_id, channel_id, send_reply)


async def _delegate_add(
    ctx: NexusContext,
    tenant_id: str,
    channel_id: str,
    send_reply: Callable[..., Awaitable[None]],
    text: str,
) -> None:
    if not text:
        await send_reply(
            channel_id,
            "Usage: /delegate add <person> <task> [due=DATE]\n\n"
            "Examples:\n"
            "  /delegate add Raj Cache redesign due=Friday\n"
            "  /delegate add Priya Onboarding doc due=2026-05-19",
        )
        return

    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        await send_reply(channel_id, "Specify both person and task: /delegate add <person> <task>")
        return

    person = parts[0]
    params = _extract_inline_params(parts[1])
    task = params["title"]
    due_date = params.get("due")

    await ctx.send_to_memory(
        "ext_execute",
        {
            "sql": (
                "INSERT INTO work_delegations"
                " (tenant_id, delegated_to, task, status, due_date, source)"
                " VALUES (?, ?, ?, 'assigned', ?, 'manual')"
            ),
            "params": [tenant_id, person, task, due_date],
        },
    )
    due_str = f" (due {due_date})" if due_date else ""
    await send_reply(channel_id, f"Delegated to **{person}**: {task}{due_str}")


async def _delegate_done(
    ctx: NexusContext,
    tenant_id: str,
    channel_id: str,
    send_reply: Callable[..., Awaitable[None]],
    id_str: str,
) -> None:
    if not id_str.strip().isdigit():
        await send_reply(channel_id, "Usage: /delegate done <id>")
        return

    deleg_id = int(id_str.strip())
    result = await ctx.send_to_memory(
        "ext_execute",
        {
            "sql": (
                "UPDATE work_delegations SET status='done', last_update=CURRENT_TIMESTAMP"
                " WHERE id=? AND tenant_id=?"
            ),
            "params": [deleg_id, tenant_id],
        },
    )
    if result.get("status") == "ok":
        await send_reply(channel_id, f"✅ Delegation #{deleg_id} marked done.")
    else:
        await send_reply(channel_id, f"Failed to update delegation #{deleg_id}.")


async def _delegate_list(
    ctx: NexusContext,
    tenant_id: str,
    channel_id: str,
    send_reply: Callable[..., Awaitable[None]],
) -> None:
    result = await ctx.send_to_memory(
        "ext_query",
        {
            "sql": (
                "SELECT id, delegated_to, task, status, due_date, last_update"
                " FROM work_delegations WHERE tenant_id = ? AND status != 'done'"
                " ORDER BY created_at DESC"
            ),
            "params": [tenant_id],
        },
    )
    rows = result.get("rows", [])
    if not rows:
        await send_reply(channel_id, "No active delegations. Use `/delegate add` to create one.")
        return

    lines = ["**Delegation Tracker**\n"]
    for row in rows:
        status_icon = {"assigned": "📋", "in_progress": "🔄", "review": "👀", "stale": "⚠️"}.get(
            row[3], "•"
        )
        due = f" — due {row[4]}" if row[4] else ""
        update = f" (last update: {row[5]})" if row[5] else " (no updates)"
        lines.append(f"{status_icon} #{row[0]} **{row[1]}**: {row[2]}{due}{update}")

    lines.append(f"\n{len(rows)} active delegation(s). `/delegate done <id>` to complete.")
    await send_reply(channel_id, "\n".join(lines))


async def handle_meetings(
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
        await send_reply(channel_id, "Meetings service unavailable.")
        return

    parts = args.strip().split(maxsplit=1) if args.strip() else []
    subcommand = parts[0].lower() if parts else ""
    rest = parts[1] if len(parts) > 1 else ""

    if subcommand == "add":
        await _meetings_add(nexus_context, tenant_id, channel_id, send_reply, rest)
    elif subcommand == "notes":
        await _meetings_notes(nexus_context, tenant_id, channel_id, send_reply, rest)
    else:
        await _meetings_list(nexus_context, tenant_id, channel_id, send_reply)


async def _meetings_add(
    ctx: NexusContext,
    tenant_id: str,
    channel_id: str,
    send_reply: Callable[..., Awaitable[None]],
    text: str,
) -> None:
    if not text:
        await send_reply(
            channel_id,
            "Usage: /meetings add <title> [date=DATE] [attendees=A,B,C]\n\n"
            "Examples:\n"
            "  /meetings add 1:1 with Raj date=2026-05-14 attendees=Raj\n"
            "  /meetings add Architecture review date=tomorrow",
        )
        return

    params = _extract_inline_params(text)
    title = params["title"]
    meeting_date = params.get("date")
    attendees = params.get("attendees", "")
    attendees_json = json.dumps(attendees.split(",")) if attendees else None

    await ctx.send_to_memory(
        "ext_execute",
        {
            "sql": (
                "INSERT INTO work_meetings"
                " (tenant_id, title, attendees, meeting_date)"
                " VALUES (?, ?, ?, ?)"
            ),
            "params": [tenant_id, title, attendees_json, meeting_date],
        },
    )
    date_str = f" on {meeting_date}" if meeting_date else ""
    await send_reply(channel_id, f"Meeting added: **{title}**{date_str}")


async def _meetings_notes(
    ctx: NexusContext,
    tenant_id: str,
    channel_id: str,
    send_reply: Callable[..., Awaitable[None]],
    text: str,
) -> None:
    parts = text.split(maxsplit=1) if text else []
    if len(parts) < 2 or not parts[0].isdigit():
        await send_reply(channel_id, "Usage: /meetings notes <id> <notes text>")
        return

    meeting_id = int(parts[0])
    notes = parts[1]

    result = await ctx.send_to_memory(
        "ext_execute",
        {
            "sql": "UPDATE work_meetings SET notes=? WHERE id=? AND tenant_id=?",
            "params": [notes, meeting_id, tenant_id],
        },
    )
    if result.get("status") == "ok":
        await send_reply(channel_id, f"📝 Notes saved for meeting #{meeting_id}.")
    else:
        await send_reply(channel_id, f"Failed to save notes for meeting #{meeting_id}.")


async def _meetings_list(
    ctx: NexusContext,
    tenant_id: str,
    channel_id: str,
    send_reply: Callable[..., Awaitable[None]],
) -> None:
    result = await ctx.send_to_memory(
        "ext_query",
        {
            "sql": (
                "SELECT id, title, meeting_date, attendees, notes"
                " FROM work_meetings WHERE tenant_id = ?"
                " ORDER BY meeting_date DESC LIMIT 10"
            ),
            "params": [tenant_id],
        },
    )
    rows = result.get("rows", [])
    if not rows:
        await send_reply(channel_id, "No meetings tracked. Use `/meetings add` to create one.")
        return

    lines = ["**Recent Meetings**\n"]
    for row in rows:
        date_str = f" ({row[2]})" if row[2] else ""
        attendees = json.loads(row[3]) if row[3] else []
        att_str = f" — with {', '.join(attendees)}" if attendees else ""
        notes_flag = " 📝" if row[4] else ""
        lines.append(f"#{row[0]} **{row[1]}**{date_str}{att_str}{notes_flag}")

    await send_reply(channel_id, "\n".join(lines))


async def handle_next(
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
        await send_reply(channel_id, "Priority service unavailable.")
        return

    result = await nexus_context.send_to_memory(
        "ext_query",
        {
            "sql": (
                "SELECT id, title, status, priority, due_date, assigned_to"
                " FROM work_actions WHERE tenant_id = ? AND status IN ('open', 'in_progress')"
                " ORDER BY created_at DESC"
            ),
            "params": [tenant_id],
        },
    )
    rows = result.get("rows", [])
    if not rows:
        await send_reply(channel_id, "No open action items. You're clear! 🎉")
        return

    scored = []
    for row in rows:
        action = {
            "id": row[0],
            "title": row[1],
            "status": row[2],
            "priority": row[3],
            "due_date": row[4],
            "assigned_to": row[5],
        }
        action["score"] = score_action(action)
        scored.append(action)

    scored.sort(key=lambda a: a["score"], reverse=True)

    top = scored[0]
    lines = [f"**Do next: #{top['id']} {top['title']}**"]
    if top["due_date"]:
        lines.append(f"Due: {top['due_date']}")
    lines.append(f"Priority: {top['priority']} (score: {top['score']})")

    if len(scored) > 1:
        lines.append(f"\n{len(scored) - 1} more item(s) after this. `/actions` for full list.")

    await send_reply(channel_id, "\n".join(lines))


def _extract_inline_params(text: str) -> dict[str, str]:
    params: dict[str, str] = {}
    title_parts: list[str] = []
    for token in text.split():
        if "=" in token:
            key, _, value = token.partition("=")
            params[key.lower()] = value
        else:
            title_parts.append(token)
    params["title"] = " ".join(title_parts)
    return params
