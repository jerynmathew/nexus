# Design: Finance Intelligence (nexus-finance)

> Status: Design — architecture for FIRE-focused personal finance advisor
> Priority: High — first extension to validate the M5 extension system
> Depends on: M5 extension system (NexusExtension protocol, NexusContext API)
> Distribution: Separate repo (`nexus-finance`), pip-installable

---

## Vision

A personal finance research agent built around FIRE (Financial Independence, Retire Early). Not a price checker — a system that tracks your portfolio, researches investments, and tells you what to do with your money.

The end state: "How's my portfolio doing?" pulls your Zerodha holdings, calculates P&L across MFs/stocks/ETFs/gold, compares against your FIRE target, and tells you if you're on track — with specific rebalance suggestions.

---

## User Profile

- **FIRE stage:** Accumulation (10+ years out)
- **Platform:** Zerodha (Kite for stocks/ETFs, Coin for MFs)
- **Asset classes:** Indian MFs, Indian ETFs, direct equity (NSE/BSE), gold (SGB, digital gold), PPF, FDs
- **Advisory depth:** Full research + recommendations (not just tracking)

---

## Three Layers

### Layer 1: Portfolio Tracking

Connect to Zerodha, pull actual holdings, store locally, track over time.

**What it does:**
- Sync holdings from Zerodha Kite API (MFs, stocks, ETFs)
- Track gold (SGB, digital gold) — manual entry or API where available
- Track debt instruments (PPF, FDs) — manual entry with maturity dates
- Calculate: total corpus, asset allocation %, P&L per holding, XIRR
- Store daily snapshots in SQLite for historical tracking

**Data flow:**
```
Zerodha Kite API → sync holdings → SQLite (portfolio_holdings)
                                 → SQLite (portfolio_snapshots) [daily]
                                 → Asset allocation calculation
                                 → FIRE progress calculation
```

**Zerodha Kite API:**

| Capability | Endpoint | Notes |
|---|---|---|
| Holdings | `/portfolio/holdings` | Stocks, ETFs with avg price, P&L |
| MF holdings | `/portfolio/holdings` | Coin MFs included |
| Positions | `/portfolio/positions` | Intraday + delivery |
| Orders | `/orders` | Order history |
| SIP list | (via Coin) | Active SIPs |

- SDK: `pykiteconnect` (v5.x) — `pip install kiteconnect`
- Auth: OAuth2 (redirect flow). Token valid for one trading day.
- Cost: Free (personal use). WebSocket streaming: Rs500/month (not needed for daily sync).
- Rate limits: 3 requests/second, 200/minute

**Manual holdings** (no API available):
- SGBs — entry: units, purchase price, issue date, coupon rate (2.5% semi-annual)
- PPF — entry: balance, yearly contribution, lock-in tracker
- FDs — entry: principal, rate, tenure, maturity date
- RDs — entry: monthly amount, rate, tenure, maturity date
- Digital gold — entry: grams, purchase price (or Zerodha digital gold via API)

**Banking data (FDs, RDs, loans) from HDFC/SBI:**

Neither HDFC nor SBI offer personal banking APIs to individual developers. Three approaches, in priority order:

| Approach | Safety | How it works |
|---|---|---|
| **Manual entry** (Phase 1) | Safe | User enters FD/RD/loan details via `/holdings add` command |
| **PDF/CSV statement upload** (Phase 2) | Safe | User downloads statement from net banking, uploads to Nexus for parsing |
| **Account Aggregator** (Future, maybe) | Safe | RBI-regulated consent-based data sharing via Finvu/OneMoney SDK |

Screen scraping of bank portals is explicitly **not an option** — IT Act Section 66 risk (unauthorized access), DPDP Act liability, credential storage risk, and bank TOS violation.

**Statement upload flow:**
1. User downloads PDF/CSV from HDFC/SBI net banking (manual, monthly)
2. Uploads via Telegram document or web dashboard
3. Nexus parses: extracts FD/RD details (principal, rate, maturity), loan outstanding, transactions
4. Parsed data stored in `finance_holdings` table
5. Nexus reminds user monthly: "Time to upload your latest bank statements for HDFC/SBI"

**Scheduled reminders:**
- SchedulerAgent sends monthly reminder (1st of each month) via Telegram:
  "📊 Monthly bank data refresh: please upload your latest HDFC and SBI statements so I can update your portfolio. Download from net banking → send here as PDF."
- Tracks last upload date per bank — if >45 days stale, escalates reminder frequency

**Account Aggregator (noted for future):**
India's AA framework (Finvu, OneMoney, CAMS FinServ) enables consent-based encrypted data sharing from banks. 284M users linked, covers FDs/RDs/loans/balances. Requires DPDP compliance (consent management, encryption, audit trails, deletion rights). Cost ~Rs5-20 per data fetch. May integrate in a future phase if the manual approach proves too friction-heavy — but not planned for v1.

### Layer 2: Market Research

Claude researches investments using market data + web search, compares options, proposes actions.

**Capabilities:**

**a) MF Research**
- Fetch NAV + historical returns via MFapi.in (free, 10K+ schemes)
- Compare funds: expense ratio, category rank, rolling returns (1Y/3Y/5Y)
- SIP return calculator (past performance)
- Category analysis: large cap, mid cap, flexi cap, ELSS, debt
- Skill instructs Claude to: "Compare the top 5 flexi cap funds by 5Y CAGR and expense ratio. Recommend the best for a 10+ year FIRE accumulation horizon."

**b) Stock/ETF Research**
- NSE/BSE quotes + historical OHLCV via Yahoo Finance / NSE API
- Technical indicators: SMA, EMA, RSI (computed in code, not LLM)
- Fundamental data via web search (PE ratio, earnings, sector trends)
- ETF comparison: tracking error, expense ratio, AUM, liquidity

**c) Gold Analysis**
- International gold price via Yahoo Finance (`GC=F`)
- India gold prices (22K/24K, city-wise) via Playwright scraping of goodreturns.in
- SGB premium/discount analysis
- Gold allocation recommendation based on portfolio %

**d) FIRE Planning**
- Corpus calculator: current savings rate → years to FIRE at target withdrawal rate
- 4% rule / 3% rule (India-adjusted for inflation)
- Asset allocation recommendation by FIRE stage (accumulation → heavy equity)
- Monthly/quarterly review: "You're saving Rs X/month. At this rate, FIRE in Y years. To reach target in Z years, increase SIP by Rs W."

### Layer 3: Dashboard + Alerts

Visual portfolio overview + proactive notifications.

**Dashboard views (via ContentStore → web dashboard or Telegram):**
- Portfolio summary: total value, day change, allocation pie chart
- Performance: 1M / 6M / 1Y / 3Y / 5Y / since inception
- FIRE progress: corpus vs target, projected timeline
- Gold price trend chart (India 22K, with SMA overlay)
- Individual holding cards: current value, P&L, % of portfolio
- Rebalance suggestions: "Equity is 72% (target: 75%). Consider adding Rs X to flexi cap."

**Proactive alerts (via heartbeat skill):**
- Significant portfolio move (>2% in a day)
- MF NAV below SMA (buy signal)
- Gold price dip/spike
- SIP execution confirmation
- Quarterly rebalance reminder
- FIRE milestone reached ("You've crossed Rs X lakhs!")

---

## Data Sources

| Source | Type | Cost | Coverage | Use Case |
|---|---|---|---|---|
| **Zerodha Kite API** | REST API | Free | Holdings, positions, orders, P&L | Portfolio sync |
| **MFapi.in** | REST API | Free | 10K+ MF schemes, historical NAV | MF research, NAV tracking |
| **Yahoo Finance** | REST/scrape | Free | Indian ETFs (`NIFTYBEES.NS`), global markets, gold futures | ETF data, gold international |
| **goodreturns.in** | Playwright scrape | Free | India gold 22K/24K, city-wise | India gold prices |
| **open-websearch** | MCP (existing) | Free | Web search | Market research, analyst opinions |
| **GoldAPI.io** | REST API | Free (50/mo) | Gold in INR | Fallback for India gold |
| **RBI/bank sites** | Manual | Free | PPF rate, FD rates | Debt instrument tracking |

### Data Source Architecture

Each data source runs as a **containerized MCP server** (sandbox-first, per [integrations policy](integrations.md)):

```
Docker containers (scoped credentials, network isolation)
├── pp-yahoo-finance (Printing Press CLI → ETFs, gold futures, international)
├── nexus-finance-mfapi (custom MCP → MFapi.in wrapper)
├── nexus-finance-zerodha (custom MCP → Kite API wrapper)
├── mcp-browser (existing Playwright → gold price scraping)
└── mcp-search (existing open-websearch → market research)
```

**Why custom MCP servers for MFapi and Zerodha?** No Printing Press CLIs exist for these. Building thin MCP wrappers is straightforward — each is a single-file Python server using the `mcp` SDK that wraps 5-10 API calls.

---

## Architecture (Option B: Skill + Code)

Skills define orchestration. Code handles computation. Extension protocol wires it into Nexus.

### Extension Structure

```
nexus-finance/
├── pyproject.toml
├── src/nexus_finance/
│   ├── __init__.py
│   ├── extension.py          # FinanceExtension(NexusExtension) — entry point
│   ├── portfolio.py          # Portfolio sync, snapshot, allocation calculation
│   ├── research.py           # MF comparison, FIRE calculator, rebalance logic
│   ├── charts.py             # matplotlib chart generation
│   ├── gold.py               # India gold price parsing (from Playwright results)
│   ├── indicators.py         # SMA, EMA, RSI, XIRR calculation
│   ├── schema.py             # SQLite table definitions
│   ├── commands.py           # /portfolio, /fire, /rebalance, /research
│   ├── parsers/
│   │   ├── hdfc.py           # HDFC statement PDF/CSV parser
│   │   └── sbi.py            # SBI statement PDF/CSV parser
│   └── skills/
│       ├── portfolio-review/
│       │   └── SKILL.md      # "How's my portfolio?" → full analysis
│       ├── mf-research/
│       │   └── SKILL.md      # "Best flexi cap fund?" → comparison
│       ├── gold-analysis/
│       │   └── SKILL.md      # "Gold price trend" → chart + recommendation
│       ├── fire-check/
│       │   └── SKILL.md      # "Am I on track for FIRE?" → progress report
│       ├── rebalance/
│       │   └── SKILL.md      # Quarterly rebalance analysis
│       ├── bank-statement-parse/
│       │   └── SKILL.md      # Parse uploaded bank statement → extract holdings
│       ├── finance-reminder/
│       │   └── SKILL.md      # Monthly: "upload your latest bank statements"
│       └── finance-alert/
│           └── SKILL.md      # Scheduled: check for significant moves
├── docker/
│   ├── mfapi.Dockerfile      # MFapi.in MCP server
│   └── zerodha.Dockerfile    # Zerodha Kite MCP server
├── tests/
└── README.md
```

### Extension Entry Point

```python
class FinanceExtension:
    @property
    def name(self) -> str:
        return "nexus-finance"

    async def on_load(self, nexus: NexusContext) -> None:
        nexus.register_schema(FINANCE_SCHEMA)
        nexus.register_skill_dir(Path(__file__).parent / "skills")
        nexus.register_command("portfolio", handle_portfolio)
        nexus.register_command("fire", handle_fire)
        nexus.register_command("rebalance", handle_rebalance)
        nexus.register_command("research", handle_research)
        nexus.register_signal_handler("scheduled_sync", self._sync_portfolio)
```

### Database Schema

```sql
CREATE TABLE IF NOT EXISTS finance_holdings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    name TEXT NOT NULL,
    asset_class TEXT NOT NULL,       -- 'equity', 'mf', 'etf', 'gold', 'debt'
    quantity REAL NOT NULL,
    avg_price REAL NOT NULL,
    current_price REAL,
    current_value REAL,
    pnl REAL,
    pnl_pct REAL,
    source TEXT NOT NULL,            -- 'zerodha', 'manual'
    metadata TEXT,                   -- JSON: MF scheme code, SGB issue date, FD maturity, etc.
    last_synced TIMESTAMP,
    UNIQUE(tenant_id, symbol, source)
);

CREATE TABLE IF NOT EXISTS finance_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    snapshot_date DATE NOT NULL,
    total_value REAL NOT NULL,
    equity_value REAL,
    mf_value REAL,
    etf_value REAL,
    gold_value REAL,
    debt_value REAL,
    day_change REAL,
    day_change_pct REAL,
    asset_allocation TEXT,           -- JSON: {"equity": 45.2, "mf": 30.1, ...}
    UNIQUE(tenant_id, snapshot_date)
);

CREATE TABLE IF NOT EXISTS finance_gold_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE NOT NULL,
    city TEXT NOT NULL,              -- 'bangalore', 'kerala', 'mumbai', 'international'
    gold_22k REAL,
    gold_24k REAL,
    currency TEXT DEFAULT 'INR',
    UNIQUE(date, city)
);

CREATE TABLE IF NOT EXISTS finance_mf_nav (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scheme_code TEXT NOT NULL,
    date DATE NOT NULL,
    nav REAL NOT NULL,
    UNIQUE(scheme_code, date)
);

CREATE TABLE IF NOT EXISTS finance_bank_statements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    bank TEXT NOT NULL,              -- 'hdfc', 'sbi', 'icici'
    upload_date TIMESTAMP NOT NULL,
    statement_period_start DATE,
    statement_period_end DATE,
    parsed_data TEXT,                -- JSON: extracted FDs, RDs, loans, balances
    raw_filename TEXT
);

CREATE TABLE IF NOT EXISTS finance_reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    reminder_type TEXT NOT NULL,     -- 'bank_statement', 'rebalance', 'fire_review'
    last_completed TIMESTAMP,
    frequency_days INTEGER DEFAULT 30,
    UNIQUE(tenant_id, reminder_type)
);

CREATE TABLE IF NOT EXISTS finance_fire_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    target_corpus REAL,              -- FIRE target amount
    monthly_expenses REAL,           -- Current monthly expenses
    withdrawal_rate REAL DEFAULT 0.04, -- 4% rule default
    inflation_rate REAL DEFAULT 0.06,  -- India CPI ~6%
    expected_return REAL DEFAULT 0.12,  -- Equity ~12% nominal
    target_allocation TEXT,          -- JSON: {"equity": 75, "debt": 15, "gold": 10}
    UNIQUE(tenant_id)
);
```

### Chart Generation

```python
def generate_portfolio_chart(snapshots: list[dict], tenant_id: str) -> str:
    """Generate portfolio value over time chart. Returns ContentStore view_id."""
    # matplotlib → PNG → base64 → HTML page → ContentStore
    # Returns URL like http://localhost:8080/view/abc123
```

Chart types:
- Portfolio value line chart (1M/6M/1Y/all)
- Asset allocation pie chart
- Gold price trend with SMA overlay
- FIRE progress bar (corpus vs target)
- Individual holding performance sparklines

---

## Skill Designs

### portfolio-review

```yaml
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
```

### mf-research

```yaml
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
5. Consider user's FIRE stage (accumulation → growth-oriented)
6. Recommend 2-3 funds with reasoning
7. If user holds similar funds, compare against current holdings

Always disclose: "This is AI-generated analysis, not financial advice."
```

### gold-analysis

```yaml
---
name: gold-analysis
description: India gold price analysis with buy/sell recommendation
execution: sequential
tool_groups: [finance, search]
---

When the user asks about gold prices or gold investment:

1. Fetch current India gold price (22K, 24K) from finance tools
2. Fetch 30-day and 90-day historical prices
3. Generate gold price trend chart with 20-day SMA
4. Check gold allocation in portfolio vs target
5. Search for gold market outlook (RBI policy, global factors, festive demand)
6. Calculate SGB yield advantage (2.5% coupon + gold appreciation) vs physical/digital
7. Recommend: BUY / HOLD / SELL with confidence and reasoning

Always disclose: "This is AI-generated analysis, not financial advice."
```

### fire-check

```yaml
---
name: fire-check
description: FIRE progress report — are you on track?
execution: sequential
tool_groups: [finance]
---

When the user asks about FIRE progress or retirement planning:

1. Fetch current portfolio value (total corpus)
2. Load FIRE config (target corpus, monthly expenses, withdrawal rate)
3. Calculate: years to FIRE at current savings rate
4. Calculate: required monthly SIP to reach target by desired date
5. Compare current asset allocation vs recommended for accumulation phase
6. Adjust for inflation (India CPI ~6%)
7. Present: corpus status, projected timeline, gap analysis, specific actions

Example output:
  Current corpus: Rs 45L | Target: Rs 3Cr (at 4% withdrawal, Rs 1L/month expenses)
  Monthly SIP: Rs 50K | Projected FIRE: 2038 (12 years)
  To reach FIRE by 2035: increase SIP to Rs 72K/month
  Allocation: Equity 72% (target 75%) — slightly under, add Rs 15K to flexi cap

Always disclose: "This is AI-generated analysis, not financial advice."
```

---

### finance-reminder

```yaml
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
   - Send reminder: "📊 Your [bank] data is [N] days old. Please download
     your latest statement from net banking and send it here as a PDF.
     This helps me keep your portfolio and FIRE projections accurate."
3. If last upload > 45 days, add urgency: "Your [bank] data is getting stale —
   portfolio allocation and FIRE projections may be inaccurate."
4. If all banks are fresh (< 30 days), do nothing (no spam)
```

### bank-statement-parse

```yaml
---
name: bank-statement-parse
description: Parse an uploaded bank statement PDF/CSV and extract holdings
execution: sequential
tool_groups: [finance]
---

When the user uploads a bank statement (PDF or CSV):

1. Detect the bank from the document format (HDFC, SBI, ICICI, etc.)
2. Extract structured data:
   - FDs: principal, interest rate, tenure, maturity date
   - RDs: monthly deposit, rate, tenure, maturity date
   - Loans: outstanding principal, EMI, rate, tenure remaining
   - Account balance: savings/current account balances
3. Store extracted holdings in finance_holdings table (asset_class='debt')
4. Update finance_reminders with current timestamp
5. Report what was found: "Found 2 FDs (Rs X), 1 RD (Rs Y), 1 home loan (Rs Z outstanding).
   Updated your portfolio."
6. If parsing fails, ask user to verify the format or enter manually

Supported formats: HDFC PDF, HDFC CSV, SBI PDF, SBI CSV.
```

---

## India Gold Prices: Scraping Strategy

Yahoo Finance covers gold futures (`GC=F`) but not India city-wise prices (22K/24K in Bangalore, Kerala, etc.).

**Source:** goodreturns.in/gold-rates/bangalore.htm (and /kerala.htm, /mumbai.htm, etc.)

**Approach:** Playwright MCP server (already running as `mcp-browser`) scrapes the page. A `gold-price-scraper` skill instructs the LLM to:
1. Navigate to goodreturns.in gold rates page
2. Extract 22K and 24K prices for configured cities
3. Store in `finance_gold_prices` table via MemoryAgent

**Schedule:** SchedulerAgent triggers daily at 10 AM IST (after markets update).

**Why scraping over API?** GoldAPI.io gives INR gold price but not city-wise breakdown. goodreturns.in is the canonical source for Indian regional gold prices. The Playwright MCP server already exists and is governed by the same sandbox/trust policies.

---

## Zerodha Integration: Auth Flow

Zerodha Kite uses OAuth2 with a redirect. The token is valid for one trading day (until 6 AM next day).

**Initial setup:**
1. User creates a Kite Connect app at https://developers.kite.trade
2. Gets `api_key` and `api_secret`
3. Nexus generates login URL → user authenticates → redirect gives `request_token`
4. Nexus exchanges `request_token` for `access_token`
5. Token stored (encrypted) in Nexus credentials

**Daily refresh:**
- Token expires at ~6 AM IST
- SchedulerAgent checks token validity before market hours (9 AM)
- If expired, Nexus sends Telegram message: "Zerodha session expired. Tap to re-authenticate: [login URL]"
- User taps → authenticates → new token stored

**Security:**
- API key/secret in `.env` (never in config.yaml)
- Access token stored in Nexus DB (encrypted column)
- Zerodha MCP server container gets only `KITE_API_KEY` and `KITE_ACCESS_TOKEN`
- Token never logged to audit trail

---

## Commands

| Command | Description |
|---|---|
| `/portfolio` | Portfolio summary — value, P&L, allocation, charts |
| `/portfolio detail` | Per-holding breakdown with sparklines |
| `/fire` | FIRE progress — corpus vs target, projected timeline |
| `/fire config` | Set FIRE parameters (target, expenses, withdrawal rate) |
| `/rebalance` | Rebalance suggestions based on target allocation |
| `/research <query>` | Research MFs/ETFs/stocks — "best flexi cap fund", "should I buy gold" |
| `/gold` | Current gold prices (India) + trend chart |
| `/holdings add <type>` | Manually add SGB/PPF/FD/RD/loan holdings |
| `/holdings upload` | Upload bank statement PDF/CSV for parsing |
| `/holdings banks` | Show last upload date per bank, staleness status |

---

## Implementation Phases

### Phase 1: Portfolio Foundation ✅

- [x] Zerodha MCP server (containerized, pykiteconnect wrapper, 8 tools, streamable-http)
- [x] Portfolio sync: parse Zerodha holdings → upsert finance_holdings → daily snapshot
- [x] `/portfolio` command: real data with value, P&L, allocation (summary + detail + sync)
- [x] Daily snapshot via `scheduled_sync` signal handler
- [x] Manual holdings entry for SGB/PPF/FD/RD/gold/loan via `/holdings add`
- [x] MemoryAgent `ext_query`/`ext_execute` for extension DB access
- [x] NexusContext MCP + DB wiring through to extension commands
- **Exit criteria:** "What's my portfolio worth?" returns accurate data from Zerodha + manual holdings ✅

### Phase 2: Market Data + Banking
- MFapi.in MCP server (containerized, NAV data wrapper)
- Gold price scraping via Playwright skill
- Chart generation (matplotlib → ContentStore)
- `/gold` command with trend chart
- Gold price daily collection scheduler
- Bank statement PDF/CSV upload + parsing (HDFC, SBI)
- `/holdings upload` and `/holdings banks` commands
- Monthly bank statement reminder scheduler
- **Exit criteria:** Upload HDFC PDF → FDs/RDs extracted → portfolio updated. Gold chart renders.

### Phase 3: Research + FIRE
- MF research skill (compare, recommend)
- FIRE calculator (corpus projection, SIP calculator)
- `/fire` command with progress report
- `/research` command with Claude-driven analysis
- `/rebalance` with allocation suggestions
- **Exit criteria:** "Best flexi cap fund for FIRE?" returns a researched comparison

### Phase 4: Alerts + Polish
- Finance alert skill (scheduled, via heartbeat)
- Significant portfolio move notifications
- Quarterly rebalance reminders
- FIRE milestone celebrations
- Dashboard finance panel (portfolio value, allocation pie, FIRE progress)
- FD/RD maturity alerts ("HDFC FD matures in 7 days — reinvest or withdraw?")
- **Exit criteria:** Proactive Telegram alert when portfolio drops >2%. Monthly bank reminder works.

---

## Dependencies

### On Nexus Core (M5 Extension System)
- `NexusExtension` protocol + `NexusContext` API
- `register_command()`, `register_schema()`, `register_skill_dir()`
- `register_signal_handler()` for scheduled portfolio sync

### Python Packages (nexus-finance)
```toml
[project]
dependencies = [
    "nexus>=0.2",
    "matplotlib~=3.9",
    "kiteconnect~=5.0",
]
```

### Docker Containers
- `nexus-finance-zerodha` — Kite API MCP server
- `nexus-finance-mfapi` — MFapi.in MCP server
- `pp-yahoo-finance` — Printing Press CLI for ETF/international data
- `mcp-browser` — existing Playwright (gold scraping)
- `mcp-search` — existing open-websearch (market research)

---

## Governance

All finance tools governed by the same policy as every other Nexus tool:

| Operation | Trust | Governance |
|---|---|---|
| Read portfolio (sync holdings) | 0.7 | Autonomous after first auth |
| Fetch market data (NAV, quotes) | 0.8 | Autonomous (read-only public data) |
| Generate chart | 0.9 | Autonomous (local computation) |
| Web search for research | 0.7 | Autonomous (existing search trust) |
| Gold price scrape (Playwright) | 0.6 | Autonomous after pattern established |
| Place order (future) | 0.1 | **Always requires approval** |

**Order execution is explicitly out of scope for v1.** Nexus advises. The user executes on Zerodha directly. This is a safety boundary — an AI placing trades on your behalf requires a fundamentally different trust model.

---

## Open Questions

1. **Zerodha token refresh UX** — daily re-auth is friction. Is there a way to automate? (Kite Connect doesn't support refresh tokens. Some users use `totp` automation — research needed.)
2. **MF direct vs regular** — Coin uses direct plans. Should research compare direct vs regular expense ratios? (Yes, always recommend direct.)
3. **Tax implications** — should the system track LTCG/STCG? Indian tax rules for MFs changed in 2024. (Useful for rebalance decisions — "selling this triggers STCG, hold 3 more months for LTCG.")
4. **Multi-tenant** — should nexus-finance support multiple users with different portfolios? (Yes, via tenant_id. Schema already supports it.)
5. **Backtesting** — should the system backtest recommendations? ("If you had followed this allocation 5 years ago, you'd have Rs X.") Useful for building trust in recommendations.
6. **Currency** — all values in INR. USD conversion needed for global comparison? (Not for v1.)
7. **Account Aggregator** — if manual bank statement uploads prove too friction-heavy, consider integrating Finvu/OneMoney AA SDK. Requires DPDP compliance (consent management, encryption at rest, 7-year audit trails, user deletion rights). Cost ~Rs5-20 per data fetch. Not planned for v1.
8. **Bank statement formats** — HDFC and SBI change PDF layouts occasionally. Parsers need to be resilient or fall back to LLM-assisted extraction. Test with real statements before shipping.

---

## Disclaimer

Every financial output from nexus-finance includes:

> "This is AI-generated analysis based on historical data and publicly available information. It is not financial advice. Past performance does not guarantee future results. Consult a SEBI-registered financial advisor before making investment decisions."

This is not optional. It is hardcoded into every skill and every command response.
