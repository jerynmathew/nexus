# Handoff: nexus-finance Complete

> Created: 2026-05-13
> Session: nexus-finance Phases 1–4 implementation

## Goal

nexus-finance extension is feature-complete for all four phases. Remaining work is integration wiring (charts → ContentStore, schedulers, Claude-driven deep research).

## Work Completed

### Phase 1: Portfolio Foundation

- MemoryAgent `ext_query`/`ext_execute` actions for extension table access
- NexusContext MCP access + command dispatch wiring
- Zerodha MCP server (containerized, 8 tools, streamable-http)
- Portfolio sync: parse Zerodha holdings → upsert finance_holdings → daily snapshot
- `/portfolio` command with real DB data (summary, detail, sync)
- `/holdings add` for manual entry (FD/RD/PPF/SGB/gold/loan)
- Extension signal handler for `scheduled_sync` events

### Phase 2: Market Data + Banking

- MFapi.in MCP server (containerized, 4 tools, streamable-http, no auth)
- `/gold` command: queries finance_gold_prices, shows 30-day trend
- `/holdings banks`: shows last upload date per bank
- `/holdings upload`: parses HDFC/SBI CSV via existing parsers, stores in finance_bank_statements

### Phase 3: Research + FIRE

- `/fire` command: FIRE progress with corpus vs target, progress bar, SIP projections (10/15 year)
- `/fire config`: set/view monthly expenses, target years, withdrawal/inflation/return rates
- `/rebalance`: current vs target allocation with delta amounts and add/reduce suggestions
- `/research`: searches MFapi.in, displays top 5 matching mutual fund schemes

### Phase 4: Alerts + Polish

- `finance_alert_check` signal handler: compares consecutive daily snapshots, logs significant moves

## Current State

- All 6 commands fully implemented: `/portfolio`, `/fire`, `/rebalance`, `/research`, `/gold`, `/holdings`
- All holdings subcommands implemented: `add`, `upload`, `banks`
- 2 MCP servers: Zerodha (port 8001), MFapi.in (port 8002)
- 2 signal handlers: `scheduled_sync`, `finance_alert_check`
- 594 total tests (509 core at 93% coverage + 85 finance), all passing
- ruff clean, mypy strict clean, ruff format clean

## Remaining Integration Work

These items have code/skills written but need wiring to schedulers or other systems:

- **Chart rendering**: charts.py has `portfolio_value_chart()`, `allocation_pie_chart()`, `gold_price_chart()` — need to wire into commands via ContentStore
- **Gold price collection**: gold.py `parse_goodreturns_html()` implemented, skill exists — needs Playwright MCP call + scheduler trigger
- **Bank statement reminders**: finance-reminder skill exists — needs SchedulerAgent cron entry
- **Deep MF research**: mf-research skill exists — needs LLM integration in `/research` command for Claude-driven comparative analysis
- **FD/RD maturity alerts**: data model supports maturity_date — needs scheduler check
- **Dashboard finance panel**: snapshot data available — needs DashboardServer panel
- **XIRR calculation**: `calculate_xirr()` stub in portfolio.py — needs Newton-Raphson implementation

## Key Files

### Core (modified)

- `src/nexus/agents/memory.py` — `_action_ext_query`, `_action_ext_execute`
- `src/nexus/extensions.py` — `mcp` property, `call_tool()` method
- `src/nexus/agents/conversation.py` — `nexus_context` kwarg in command dispatch
- `src/nexus/runtime.py` — MCP + NexusContext passed to extensions

### Finance extension

- `extensions/nexus-finance/src/nexus_finance/commands.py` — All 6 command handlers (live)
- `extensions/nexus-finance/src/nexus_finance/extension.py` — Entry point with 2 signal handlers
- `extensions/nexus-finance/src/nexus_finance/portfolio.py` — Holding dataclass, sync, snapshot, formatting
- `extensions/nexus-finance/src/nexus_finance/research.py` — FIRE calculators
- `extensions/nexus-finance/src/nexus_finance/schema.py` — 7 SQLite tables
- `extensions/nexus-finance/src/nexus_finance/charts.py` — matplotlib charts (implemented, unwired)
- `extensions/nexus-finance/src/nexus_finance/indicators.py` — SMA/EMA/RSI
- `extensions/nexus-finance/src/nexus_finance/gold.py` — goodreturns parser
- `extensions/nexus-finance/src/nexus_finance/parsers/` — HDFC/SBI CSV parsers
- `extensions/nexus-finance/docker/zerodha_mcp.py` — Zerodha MCP server (8 tools)
- `extensions/nexus-finance/docker/mfapi_mcp.py` — MFapi.in MCP server (4 tools)

## Important Decisions

- MemoryAgent owns all DB access — extensions use `ext_query`/`ext_execute` via NexusContext
- NexusContext passed to extension commands via kwargs (`nexus_context=...`)
- Zerodha: pykiteconnect, OAuth2 redirect, token valid one trading day
- MFapi.in: free API, no auth, 10K+ schemes
- All external tools in Docker containers (sandbox-first)
- Order execution explicitly out of scope — Nexus advises only

## Context for Continuation

- Extension commands receive `nexus_context` kwarg — use for `send_to_memory()` and `call_tool()`
- Push requires: `gh auth switch --user jerynmathew`, push, switch back to `jeryn-fiddler`
- Sub-agents with "deep" and "oracle" fail with ProviderModelNotFoundError — use "quick" or "unspecified-high"
- Every financial output includes disclaimer about AI-generated analysis
- Combined test run (`pytest tests/ extensions/nexus-finance/tests/`) has namespace collision — run separately
