# Design: Finance Intelligence

> Status: Draft — scoping document, not yet planned for implementation
> Priority: Deferred from M4, to be scheduled independently

---

## Problem

"What's the gold price?" is a simple query. But the actual need is: **should I buy or sell?**

That requires:
1. Current price (gold in Bangalore/Kerala, stocks in watchlist)
2. Historical trend data (7-day, 30-day, 90-day)
3. Chart visualization (trend line, moving averages)
4. Market research (news, analyst sentiment, macroeconomic factors)
5. Synthesized recommendation with confidence level

This is not a single tool call. It's a multi-step analytical workflow.

---

## Architecture Options

### Option A: Pure Skill

A `finance-analysis/SKILL.md` that instructs the LLM to:
1. Fetch current price via finance MCP tool
2. Fetch historical data via same tool
3. Search for market analysis via web search
4. Synthesize recommendation

**Pros:** No code, editable, uses existing infrastructure.
**Cons:** LLM may not reliably orchestrate 4+ sequential tool calls. Chart generation not possible in a skill.

### Option B: Skill + Code

Skill handles the orchestration narrative. Code handles:
- Chart generation (matplotlib → PNG/HTML)
- Price data formatting
- Technical indicator calculation (SMA, EMA, RSI)

**Pros:** Best of both. Skill defines *what*, code handles *how*.
**Cons:** Needs a `FinanceService` utility class.

### Option C: Dedicated Agent

A `FinanceAgent(AgentProcess)` with structured workflow:
1. Receive query → parse asset/timeframe
2. Fetch data → calculate indicators
3. Generate chart → store in content viewer
4. Search for analysis → summarize
5. Compose recommendation → return

**Pros:** Most deterministic. Full control over pipeline.
**Cons:** Custom agent (exception, not norm). More code to maintain.

### Recommendation

**Option B (Skill + Code)** — aligns with the architecture principle while handling the parts that need deterministic computation.

---

## Data Sources

### Gold Prices (India)

| Source | Type | Coverage | Cost |
|---|---|---|---|
| GoldAPI.io | REST API | Global + India rates | Free tier: 50 req/month |
| Metal Price API | REST API | Precious metals, INR | Free tier: 100 req/month |
| MCX/NSE scraping | Web scrape | Indian commodity exchange | Free but fragile |
| Gold Price India MCP | MCP server | India-specific, Bangalore/Kerala | To be found/built |

### Stocks (India + Global)

| Source | Type | Coverage | Cost |
|---|---|---|---|
| Yahoo Finance | REST/scrape | Global + NSE/BSE | Free (via yfinance) |
| Alpha Vantage | REST API | Global | Free: 25 req/day |
| NSE India API | REST API | Indian stocks | Free |

### Market Research

Web search (open-websearch, already available) for analyst opinions, news sentiment, macro factors.

---

## Chart Generation

### Local rendering (preferred)

```python
import matplotlib.pyplot as plt

fig, ax = plt.subplots(figsize=(10, 5))
ax.plot(dates, prices, label="Gold (22K)")
ax.plot(dates, sma_20, label="20-day SMA", linestyle="--")
ax.set_title("Gold Price — Bangalore (30 days)")
fig.savefig("chart.png")
```

Rendered chart stored via ContentStore → URL sent on Telegram.

### Dependencies

```toml
[project.optional-dependencies]
finance = [
    "matplotlib~=3.9",
    "yfinance~=0.2",
]
```

---

## Skill Design

```yaml
---
name: finance-analysis
description: Analyze asset price, generate chart, and recommend buy/sell
execution: sequential
tool_groups: [search]
---

# Finance Analysis

When the user asks about gold prices, stock prices, or market analysis:

1. Identify the asset (gold 22K, gold 24K, specific stock ticker)
2. Identify the market (Bangalore, Kerala, NSE, BSE)
3. Fetch current price using finance tools
4. Fetch 30-day historical data
5. Generate a price chart with trend line and 20-day moving average
6. Search for recent market analysis and news
7. Synthesize a recommendation: BUY / HOLD / SELL with confidence (low/medium/high)
8. Present: current price, chart link, key factors, recommendation

Always disclose: "This is AI-generated analysis, not financial advice."
```

---

## Open Questions

1. **Which gold price API works reliably for India-specific rates (Bangalore/Kerala)?**
2. **Should we build a finance MCP server or use direct API calls in a utility class?**
3. **How often should price data be cached? (avoid rate limits)**
4. **Should recommendations be stored in memory for trend tracking?**
5. **Is the regional gold price (Bangalore vs Kerala vs Mumbai) significantly different enough to track separately?**

---

## Next Steps

1. Research and select a reliable India gold price API
2. Prototype the chart generation pipeline
3. Design the SKILL.md + FinanceService code split
4. Add to a future milestone (M4.5 or M5)
