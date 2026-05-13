---
name: portfolio-review
description: Full portfolio analysis — holdings, P&L, allocation, FIRE progress
execution: sequential
tool_groups: [finance, search]
---

When the user asks about their portfolio, investments, or financial status:

1. Fetch current holdings from finance tools (Zerodha sync if stale > 1 hour)
2. Calculate: total value, day change, asset allocation percentages
3. Compare allocation vs target (from FIRE config)
4. Generate portfolio chart (value over time) and allocation pie chart
5. Check FIRE progress: current corpus vs target, projected timeline
6. Identify top gainers/losers in the portfolio
7. Present: summary, charts, FIRE status, any rebalance flags

Always disclose: "This is AI-generated analysis, not financial advice."
