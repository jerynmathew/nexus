---
name: rebalance
description: Quarterly rebalance analysis against target allocation
execution: sequential
tool_groups: [finance, search]
---

When the user asks about rebalancing or portfolio allocation:

1. Fetch current holdings and calculate asset allocation percentages
2. Load target allocation from FIRE config
3. Identify deviations: which asset classes are over/underweight
4. Calculate specific amounts to move (buy X of category Y, reduce Z)
5. Check tax implications (LTCG vs STCG for holdings about to be sold)
6. Search for current market conditions that might affect timing
7. Present: current vs target allocation, specific buy/sell actions, tax notes

Always disclose: "This is AI-generated analysis, not financial advice."
