---
name: work-delegation-check
description: Check for stale delegations and flag items needing follow-up
execution: sequential
tool_groups: [google]
schedule: "*/30 * * * 1-5"
active_hours_only: true
---

Check active delegations for staleness:

1. Query work_delegations for items with no update in 3+ days
2. If delegation is due within 2 days and no recent update, flag as urgent
3. Suggest follow-up message to the delegatee
4. If delegation is past due with no update, escalate to user

Only notify if there's something actionable. Silence is valid.
