from __future__ import annotations

import json
import logging
import uuid

from nexus.extensions import NexusContext

logger = logging.getLogger(__name__)

_EXTRACTION_PROMPT = """\
Extract action items from this message. For each action item, return a JSON array.
Each item should have: title, assigned_to ("self" or person name), due_date (ISO format or null), \
priority ("critical", "high", "medium", "low").

If the sender is asking the reader to do something, assigned_to is "self".
If the reader is asking someone else, it's a delegation — set assigned_to to that person's name.

If no action items, return: []

Message:
{message}

Respond ONLY with a JSON array, nothing else."""


async def store_signal(
    ctx: NexusContext,
    tenant_id: str,
    source: str,
    event_type: str,
    title: str,
    body: str = "",
    author: str = "",
    author_email: str = "",
    channel: str = "",
    url: str = "",
    project: str = "",
    priority: str = "medium",
) -> str:
    signal_id = f"{source}_{uuid.uuid4().hex[:12]}"
    await ctx.send_to_memory(
        "ext_execute",
        {
            "sql": (
                "INSERT INTO work_signals"
                " (tenant_id, signal_id, source, event_type, timestamp,"
                "  title, body, url, author, author_email, channel, project, priority)"
                " VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(signal_id) DO NOTHING"
            ),
            "params": [
                tenant_id,
                signal_id,
                source,
                event_type,
                title,
                body,
                url,
                author,
                author_email,
                channel,
                project,
                priority,
            ],
        },
    )
    return signal_id


async def extract_actions_from_signal(
    ctx: NexusContext,
    tenant_id: str,
    message_text: str,
    source: str,
    source_ref: str = "",
    author: str = "",
) -> int:
    if not ctx.llm:
        return 0

    prompt = _EXTRACTION_PROMPT.format(message=message_text[:2000])

    model = ctx.resolve_model(task="SKILL_EXEC")
    try:
        response = await ctx.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            model=model,
        )
    except Exception:
        logger.debug("LLM call failed for action extraction")
        return 0

    content = response.content.strip()
    if not content or content == "[]":
        return 0

    try:
        items = json.loads(content)
    except json.JSONDecodeError:
        logger.debug("Failed to parse extraction response: %s", content[:200])
        return 0

    if not isinstance(items, list):
        return 0

    count = 0
    for item in items:
        if not isinstance(item, dict) or not item.get("title"):
            continue

        title = item["title"]
        assigned_to = item.get("assigned_to", "self")
        due_date = item.get("due_date")
        priority = item.get("priority", "medium")

        if assigned_to != "self":
            await ctx.send_to_memory(
                "ext_execute",
                {
                    "sql": (
                        "INSERT INTO work_delegations"
                        " (tenant_id, delegated_to, task, status, due_date, source)"
                        " VALUES (?, ?, ?, 'assigned', ?, ?)"
                    ),
                    "params": [tenant_id, assigned_to, title, due_date, source],
                },
            )
        else:
            await ctx.send_to_memory(
                "ext_execute",
                {
                    "sql": (
                        "INSERT INTO work_actions"
                        " (tenant_id, title, status, priority, due_date,"
                        "  source, source_ref, assigned_to, assigned_by)"
                        " VALUES (?, ?, 'open', ?, ?, ?, ?, 'self', ?)"
                    ),
                    "params": [
                        tenant_id,
                        title,
                        priority,
                        due_date,
                        source,
                        source_ref,
                        author,
                    ],
                },
            )
        count += 1

    return count
