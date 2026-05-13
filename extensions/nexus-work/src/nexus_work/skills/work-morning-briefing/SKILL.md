---
name: work-morning-briefing
description: Structured day start — urgent items, meetings, commitments, delegations
execution: parallel
tool_groups: [google, search]
schedule: "0 7 * * 1-5"
active_hours_only: true
---

Generate a structured morning briefing for a work day:

1. **Urgent triage**: Query work_actions for overdue and high-priority items
2. **Today's meetings**: Check calendar for today's events, add context from past interactions
3. **Commitments**: List open action items with due dates this week
4. **Delegation tracker**: Show active delegations, flag stale ones (no update in 3+ days)
5. **Overnight activity**: Summarize emails and Slack messages since last active

Format as a structured briefing, not a wall of text. Group by urgency.
