---
name: finance-alert
description: Check for significant portfolio moves and market events
execution: sequential
tool_groups: [finance]
schedule: "0 18 * * 1-5"
active_hours_only: true
---

End-of-day finance check (weekdays at 6 PM):

1. Compare today's portfolio snapshot with yesterday's
2. If total value changed > 2%, alert the user with top movers
3. Check if any FD/RD is maturing within 7 days
4. Check gold price trend (significant move in last 3 days)
5. If nothing notable, stay silent (no spam)

Only alert on actionable events. "Your portfolio is fine" is not an alert.
