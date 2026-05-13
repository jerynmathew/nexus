---
name: work-evening-wrap
description: End-of-day summary — completed items, still open, tomorrow preview
execution: sequential
tool_groups: [google]
schedule: "0 18 * * 1-5"
active_hours_only: true
---

Generate an end-of-day summary:

1. **Completed today**: Action items marked done today
2. **Still open**: Remaining open items, highlight overdue
3. **Delegations**: Any updates or stale delegations
4. **Tomorrow preview**: First meeting, any deadlines
5. **Suggestion**: If items are overdue, suggest delegation or deprioritization
