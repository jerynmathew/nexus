---
name: work-action-extract
description: Extract action items from incoming messages (emails, Slack, meetings)
execution: sequential
tool_groups: [google]
---

When processing a work message, scan for action items:

1. Identify commitments: "Can you...", "Please...", "by [date]", "need your..."
2. For each action item, extract: what, who, when, urgency
3. Store in work_actions table via memory tools
4. If it's a delegation (you asking someone else), store in work_delegations

If no action items found, respond with "NONE" — do not create spurious items.
