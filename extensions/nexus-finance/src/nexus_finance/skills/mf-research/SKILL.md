---
name: mf-research
description: Research and compare mutual funds for investment
execution: sequential
tool_groups: [finance, search]
---

When the user asks about mutual fund recommendations or comparisons:

1. Identify the category (large cap, flexi cap, mid cap, ELSS, debt, etc.)
2. Fetch top funds in the category via MF tools (by 5Y CAGR)
3. Compare: expense ratio, AUM, fund manager track record, rolling returns
4. Search web for recent analyst opinions on shortlisted funds
5. Consider user's FIRE stage (accumulation = growth-oriented)
6. Recommend 2-3 funds with reasoning
7. If user holds similar funds, compare against current holdings

Always disclose: "This is AI-generated analysis, not financial advice."
