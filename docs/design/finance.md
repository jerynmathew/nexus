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

### Primary: Printing Press Yahoo Finance MCP

The [`pp-yahoo-finance`](../design/printing-press.md) CLI provides Yahoo Finance data as an MCP server (stdio transport). This is the **recommended primary data source** for stocks and global commodities.

| Capability | Coverage | Notes |
|---|---|---|
| Real-time quotes | Global stocks, commodities, forex, crypto | `GC=F` for gold futures, `^NSEI` for Nifty 50 |
| Historical data | Daily OHLCV, configurable time range | Enables trend charts and technical indicators |
| Symbol search | Ticker lookup by name/keyword | "gold" → GC=F, GLD, IAU |
| Watchlist | User-defined symbol lists | Track portfolio positions |

**Setup:** Build container image → add to `docker-compose.yaml` with scoped credentials → configure in `config.yaml` → MCPManager auto-connects via HTTP. See [Printing Press integration](../design/printing-press.md) for container setup and security model.

**Local data mirroring:** SchedulerAgent fetches prices hourly → stores in SQLite → compound queries ("gold trend this week") hit local DB (50ms) instead of API (rate-limited).

### Supplementary Sources

| Source | Type | Coverage | Cost | Use Case |
|---|---|---|---|---|
| GoldAPI.io | REST API | Global + India rates | Free: 50 req/month | India-specific gold (Bangalore/Kerala, 22K/24K) |
| Metal Price API | REST API | Precious metals, INR | Free: 100 req/month | Fallback for India rates |
| NSE India API | REST API | Indian stocks | Free | NSE/BSE specific data (not covered by Yahoo) |
| MCX/NSE scraping | Web scrape | Indian commodity exchange | Free but fragile | Last resort for MCX gold |

### Market Research

Web search (open-websearch, already available) for analyst opinions, news sentiment, macro factors.

> **Note on India gold prices:** Yahoo Finance covers gold futures (GC=F) and gold ETFs but not regional Indian prices (Bangalore/Kerala 22K/24K). For India-specific rates, a supplementary source (GoldAPI.io or Metal Price API) is still needed alongside `pp-yahoo-finance`.

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

1. **Which gold price API works reliably for India-specific rates (Bangalore/Kerala)?** Yahoo Finance covers gold futures (GC=F) but not regional Indian rates. GoldAPI.io or Metal Price API needed as supplement.
2. ~~**Should we build a finance MCP server or use direct API calls in a utility class?**~~ **Resolved:** Use Printing Press `yahoo-finance-pp-mcp` for global finance data. No custom MCP server or utility class needed. See [Printing Press integration](../design/printing-press.md).
3. **How often should price data be cached? (avoid rate limits)** Printing Press CLIs include local SQLite data layer with sync operations. SchedulerAgent can trigger periodic syncs (e.g., hourly for quotes, daily for historical).
4. **Should recommendations be stored in memory for trend tracking?** Yes — store in MemoryAgent's finance tables for historical comparison.
5. **Is the regional gold price (Bangalore vs Kerala vs Mumbai) significantly different enough to track separately?** Typically 1-3% variance. Worth tracking if user is in the gold market.

---

## Next Steps

1. Install and validate `yahoo-finance-pp-mcp` end-to-end (gold futures, stock quotes, historical data)
2. Research and select a reliable India gold price API for regional rates (Bangalore/Kerala 22K/24K)
3. Prototype the chart generation pipeline (matplotlib → ContentStore)
4. Design the SKILL.md + FinanceService code split
5. Build as `nexus-finance` extension (M5+) — see [extensions architecture](../design/extensions.md)
