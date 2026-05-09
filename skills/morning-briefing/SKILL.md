---
name: morning-briefing
description: Compile and deliver morning briefing
execution: parallel
timeout_per_section: 30
tool_groups: [google]
schedule: "0 7 * * *"
---

# Morning Briefing

Compile a concise morning briefing for the user.

## Sections

### 📧 Email Summary

Fetch the top 5 unread emails using search_gmail_messages.
Flag emails from known contacts or with action words as important.
Format: sender, subject, one-line summary.

### 📅 Today's Calendar

Fetch today's events using list_events or get_events.
Include time, title, and attendees.
Flag conflicts or back-to-back meetings.

### ✅ Pending Tasks

Fetch pending tasks using list_tasks.
Sort by priority. Flag overdue items.

## Delivery

Send each section to the user as it completes.
If any section fails or times out, note it with ⚠ and continue with available data.
