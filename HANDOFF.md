# Handoff: M5 Complete (nexus-finance + nexus-work)

> Created: 2026-05-13
> Session: M5.1–M5.5 implementation

## Goal

M5 milestone complete. Two extensions built: nexus-finance (FIRE personal finance) and nexus-work (work intelligence). Remaining work is integration wiring (schedulers, LLM analysis, charts).

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

### M5.1–M5.4: nexus-work

- Action item tracking: `/actions` (list/add/done/all) with multi-factor priority scoring
- Delegation tracking: `/delegate` (list/add/done) with stale detection signal handler
- Meeting intelligence: `/meetings` (list/add/notes) with attendee and date tracking
- Priority engine: `/next` returns highest-priority action item
- 4 DB tables: work_actions, work_delegations, work_meetings, work_people
- 5 work skills: morning-briefing, meeting-prep, evening-wrap, action-extract, delegation-check
- 39 tests

## Current State

- 2 extensions installed in dev mode, auto-discovered via entry_points
- 10 commands total (6 finance + 4 work), all live — zero stubs remaining
- 2 MCP servers: Zerodha (port 8001), MFapi.in (port 8002)
- 3 signal handlers: `scheduled_sync`, `finance_alert_check`, `delegation_check`
- 633 total tests (509 core at 93% coverage + 85 finance + 39 work), all passing
- ruff clean, mypy strict clean, ruff format clean

## Remaining Integration Work

These items have code/skills written but need wiring to schedulers, LLM, or other systems:

### nexus-finance
- Chart rendering via ContentStore (charts.py implemented)
- Gold price collection via Playwright MCP (gold.py implemented)
- Bank statement reminder scheduler (skill exists)
- Deep MF research with Claude analysis (skill exists)
- XIRR Newton-Raphson implementation
- Dashboard finance panel

### nexus-work
- Action extraction from emails/Slack via LLM scan (skill exists)
- Morning briefing with full work context via scheduler (skill exists)
- Pre-meeting context briefs via scheduler trigger (skill exists)
- Delegation detection from outbound messages via LLM scan
- Auto-rerank priority on new signals

## Key Files

### Core (modified)

- `src/nexus/agents/memory.py` — `_action_ext_query`, `_action_ext_execute`
- `src/nexus/extensions.py` — `mcp` property, `call_tool()` method
- `src/nexus/agents/conversation.py` — `nexus_context` kwarg in command dispatch
- `src/nexus/runtime.py` — MCP + NexusContext passed to extensions

### nexus-work

- `extensions/nexus-work/src/nexus_work/extension.py` — WorkExtension entry point
- `extensions/nexus-work/src/nexus_work/commands.py` — 4 command handlers (/actions, /delegate, /meetings, /next)
- `extensions/nexus-work/src/nexus_work/priority.py` — Multi-factor priority scoring
- `extensions/nexus-work/src/nexus_work/schema.py` — 4 tables

### nexus-finance

- `extensions/nexus-finance/src/nexus_finance/commands.py` — 6 command handlers
- `extensions/nexus-finance/src/nexus_finance/extension.py` — Entry point with 2 signal handlers
- `extensions/nexus-finance/src/nexus_finance/portfolio.py` — Sync, snapshot, formatting
- `extensions/nexus-finance/docker/` — Zerodha + MFapi MCP servers

## Context for Continuation

- Extension commands receive `nexus_context` kwarg for DB + MCP access
- Push requires: `gh auth switch --user jerynmathew`, push, switch back to `jeryn-fiddler`
- Sub-agents with "deep"/"oracle" fail — use "quick" or "unspecified-high"
- Combined test runs have namespace collision — run core and extension tests separately
- M6+ (Production, Presence) not started
