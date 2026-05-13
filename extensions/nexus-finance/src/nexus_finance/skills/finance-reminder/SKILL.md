---
name: finance-reminder
description: Monthly reminder to upload fresh bank statements
execution: sequential
tool_groups: [finance]
schedule: "0 9 1 * *"
active_hours_only: true
---

Check when each bank's data was last uploaded:

1. Query finance_reminders table for last_completed dates
2. For each bank (HDFC, SBI) where last upload > 30 days ago:
   - Send reminder with instructions to download from net banking and send as PDF
3. If last upload > 45 days, add urgency about stale portfolio data
4. If all banks are fresh (< 30 days), do nothing
