from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from nexus.extensions import NexusContext

from nexus_work.priority import score_action

_STATUS_ICONS = {"open": "⏳", "in_progress": "🔄", "done": "✅", "overdue": "❌"}


async def assemble_morning_briefing(ctx: NexusContext, tenant_id: str) -> str:
    urgent = await _get_urgent_actions(ctx, tenant_id)
    commitments = await _get_open_actions(ctx, tenant_id)
    delegations = await _get_active_delegations(ctx, tenant_id)
    meetings = await _get_todays_meetings(ctx, tenant_id)

    lines: list[str] = ["**Good morning. Here's your day:**\n"]

    if urgent:
        lines.append("⚡ **URGENT (do first):**")
        for a in urgent:
            due = f" (due {a['due_date']})" if a.get("due_date") else ""
            lines.append(f"  - {a['title']}{due}")
        lines.append("")

    if meetings:
        lines.append("📅 **TODAY'S MEETINGS:**")
        for m in meetings:
            att = m.get("attendees_list", [])
            att_str = f" — with {', '.join(att)}" if att else ""
            lines.append(f"  {m.get('meeting_date', '')}: {m['title']}{att_str}")
        lines.append("")

    if commitments:
        lines.append("📋 **YOUR COMMITMENTS:**")
        for a in commitments:
            icon = _STATUS_ICONS.get(a["status"], "⏳")
            due = f" — due {a['due_date']}" if a.get("due_date") else ""
            lines.append(f"  {icon} {a['title']}{due}")
        lines.append("")

    if delegations:
        lines.append("👥 **DELEGATION TRACKER:**")
        for d in delegations:
            status = d.get("status", "assigned")
            flag = " ⚠️ STALE" if status == "stale" else ""
            due = f" (due {d['due_date']})" if d.get("due_date") else ""
            last = d.get("last_update")
            update = f", last update: {last}" if last else ", no updates"
            lines.append(f"  {d['delegated_to']}: {d['task']}{due}{update}{flag}")
        lines.append("")

    if not urgent and not commitments and not delegations and not meetings:
        lines.append("All clear — no open items or meetings today. 🎉")

    return "\n".join(lines)


async def assemble_evening_wrap(ctx: NexusContext, tenant_id: str) -> str:
    completed = await _get_completed_today(ctx, tenant_id)
    still_open = await _get_open_actions(ctx, tenant_id)
    delegations = await _get_active_delegations(ctx, tenant_id)

    lines: list[str] = ["**📊 Day Summary**\n"]

    if completed:
        lines.append("**Completed:**")
        for a in completed:
            lines.append(f"  ✅ {a['title']}")
        lines.append("")

    overdue = [a for a in still_open if a["status"] == "overdue" or _is_overdue(a)]
    upcoming = [a for a in still_open if a not in overdue]

    if overdue:
        lines.append("**Overdue:**")
        for a in overdue:
            lines.append(f"  ❌ {a['title']} — due {a.get('due_date', 'unknown')}")
        lines.append("")

    if upcoming:
        lines.append("**Still open:**")
        for a in upcoming[:5]:
            due = f" — due {a['due_date']}" if a.get("due_date") else ""
            lines.append(f"  ⏳ {a['title']}{due}")
        if len(upcoming) > 5:
            lines.append(f"  ... and {len(upcoming) - 5} more")
        lines.append("")

    stale = [d for d in delegations if d.get("status") == "stale"]
    if stale:
        lines.append("**Stale delegations:**")
        for d in stale:
            lines.append(f"  ⚠️ {d['delegated_to']}: {d['task']}")
        lines.append("")

    if not completed and not overdue and not upcoming:
        lines.append("Quiet day — nothing tracked.")

    return "\n".join(lines)


async def assemble_meeting_prep(ctx: NexusContext, tenant_id: str, meeting_id: int) -> str | None:
    result = await ctx.send_to_memory(
        "ext_query",
        {
            "sql": (
                "SELECT title, attendees, meeting_date, notes"
                " FROM work_meetings WHERE id = ? AND tenant_id = ?"
            ),
            "params": [meeting_id, tenant_id],
        },
    )
    rows = result.get("rows", [])
    if not rows:
        return None

    row = rows[0]
    title = row[0]
    attendees = _parse_json_list(row[1])
    meeting_date = row[2]

    lines = [f"**📅 Meeting Prep: {title}**"]
    if meeting_date:
        lines.append(f"Date: {meeting_date}")
    if attendees:
        lines.append(f"Attendees: {', '.join(attendees)}")
    lines.append("")

    for person in attendees:
        person_actions = await _get_actions_involving(ctx, tenant_id, person)
        person_delegations = await _get_delegations_for(ctx, tenant_id, person)

        if person_actions or person_delegations:
            lines.append(f"**{person}:**")
            for a in person_actions[:3]:
                lines.append(f"  - Action: {a['title']} [{a['status']}]")
            for d in person_delegations[:3]:
                lines.append(f"  - Delegation: {d['task']} [{d['status']}]")
            lines.append("")

    prev_notes = row[3]
    if prev_notes:
        lines.append(f"**Previous notes:** {prev_notes[:200]}")

    return "\n".join(lines)


def _is_overdue(action: dict[str, Any]) -> bool:
    due = action.get("due_date")
    if not due:
        return False
    try:
        return datetime.strptime(due, "%Y-%m-%d").date() < date.today()
    except ValueError:
        return False


def _parse_json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
        return list(parsed) if isinstance(parsed, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


async def _get_urgent_actions(ctx: NexusContext, tenant_id: str) -> list[dict[str, Any]]:
    result = await ctx.send_to_memory(
        "ext_query",
        {
            "sql": (
                "SELECT id, title, status, priority, due_date, assigned_to"
                " FROM work_actions"
                " WHERE tenant_id = ? AND status IN ('open', 'in_progress')"
                " AND (priority IN ('critical', 'high') OR due_date <= date('now'))"
                " ORDER BY created_at DESC"
            ),
            "params": [tenant_id],
        },
    )
    actions = [_row_to_action(r) for r in result.get("rows", [])]
    actions.sort(key=lambda a: score_action(a), reverse=True)
    return actions


async def _get_open_actions(ctx: NexusContext, tenant_id: str) -> list[dict[str, Any]]:
    result = await ctx.send_to_memory(
        "ext_query",
        {
            "sql": (
                "SELECT id, title, status, priority, due_date, assigned_to"
                " FROM work_actions"
                " WHERE tenant_id = ? AND status IN ('open', 'in_progress')"
                " ORDER BY created_at DESC LIMIT 20"
            ),
            "params": [tenant_id],
        },
    )
    return [_row_to_action(r) for r in result.get("rows", [])]


async def _get_completed_today(ctx: NexusContext, tenant_id: str) -> list[dict[str, Any]]:
    result = await ctx.send_to_memory(
        "ext_query",
        {
            "sql": (
                "SELECT id, title, status, priority, due_date, assigned_to"
                " FROM work_actions"
                " WHERE tenant_id = ? AND status = 'done'"
                " AND date(completed_at) = date('now')"
            ),
            "params": [tenant_id],
        },
    )
    return [_row_to_action(r) for r in result.get("rows", [])]


async def _get_active_delegations(ctx: NexusContext, tenant_id: str) -> list[dict[str, Any]]:
    result = await ctx.send_to_memory(
        "ext_query",
        {
            "sql": (
                "SELECT id, delegated_to, task, status, due_date, last_update"
                " FROM work_delegations"
                " WHERE tenant_id = ? AND status != 'done'"
                " ORDER BY created_at DESC"
            ),
            "params": [tenant_id],
        },
    )
    return [
        {
            "id": r[0],
            "delegated_to": r[1],
            "task": r[2],
            "status": r[3],
            "due_date": r[4],
            "last_update": r[5],
        }
        for r in result.get("rows", [])
    ]


async def _get_todays_meetings(ctx: NexusContext, tenant_id: str) -> list[dict[str, Any]]:
    result = await ctx.send_to_memory(
        "ext_query",
        {
            "sql": (
                "SELECT id, title, meeting_date, attendees"
                " FROM work_meetings"
                " WHERE tenant_id = ? AND meeting_date = date('now')"
                " ORDER BY meeting_date"
            ),
            "params": [tenant_id],
        },
    )
    return [
        {
            "id": r[0],
            "title": r[1],
            "meeting_date": r[2],
            "attendees_list": _parse_json_list(r[3]),
        }
        for r in result.get("rows", [])
    ]


async def _get_actions_involving(
    ctx: NexusContext, tenant_id: str, person: str
) -> list[dict[str, Any]]:
    result = await ctx.send_to_memory(
        "ext_query",
        {
            "sql": (
                "SELECT id, title, status, priority, due_date, assigned_to"
                " FROM work_actions"
                " WHERE tenant_id = ? AND status != 'done'"
                " AND (assigned_to = ? OR assigned_by = ?)"
            ),
            "params": [tenant_id, person, person],
        },
    )
    return [_row_to_action(r) for r in result.get("rows", [])]


async def _get_delegations_for(
    ctx: NexusContext, tenant_id: str, person: str
) -> list[dict[str, Any]]:
    result = await ctx.send_to_memory(
        "ext_query",
        {
            "sql": (
                "SELECT id, delegated_to, task, status, due_date, last_update"
                " FROM work_delegations"
                " WHERE tenant_id = ? AND delegated_to = ? AND status != 'done'"
            ),
            "params": [tenant_id, person],
        },
    )
    return [
        {
            "id": r[0],
            "delegated_to": r[1],
            "task": r[2],
            "status": r[3],
            "due_date": r[4],
            "last_update": r[5],
        }
        for r in result.get("rows", [])
    ]


def _row_to_action(row: list[Any]) -> dict[str, Any]:
    return {
        "id": row[0],
        "title": row[1],
        "status": row[2],
        "priority": row[3],
        "due_date": row[4],
        "assigned_to": row[5],
    }
