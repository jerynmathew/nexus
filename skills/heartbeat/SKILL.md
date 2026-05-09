---
name: heartbeat
description: Proactive check-in — review context and decide whether to notify the user
execution: sequential
tool_groups: [google]
schedule: "*/30 * * * *"
active_hours_only: true
---

# Proactive Heartbeat

You are performing a proactive check-in for the user. Review the following and decide
whether there is anything actionable to notify them about.

## What to check

1. **Upcoming events**: Are there any events in the next 2 hours? If so, mention them.
2. **Urgent emails**: Are there unread emails from known contacts or with urgent subjects?
3. **Overdue tasks**: Are there tasks due today that haven't been completed?

## Decision rules

- If there is something actionable (upcoming meeting, urgent email, overdue task),
  compose a brief, friendly notification. Keep it under 3 sentences.
- If there is nothing actionable, respond with exactly: HEARTBEAT_OK
- Do NOT notify about routine emails, newsletters, or non-urgent items.
- Do NOT repeat information you already notified about recently.

## Tone

Use the user's configured persona tone. Be brief and direct.
