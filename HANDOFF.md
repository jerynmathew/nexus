# Handoff: nexus-finance Phase 2

> Created: 2026-05-13
> Session: nexus-finance Phase 1 implementation

## Goal

Build Phase 2 of nexus-finance: MFapi.in MCP server, gold price scraping, chart generation, bank statement upload/parsing, and monthly reminders.

## Work Completed

### Phase 1: Portfolio Foundation (this session)

- Built MemoryAgent `ext_query`/`ext_execute` actions for extension table access (parameterized SQL, guards against DROP/ALTER/CREATE)
- Wired NexusContext through ConversationManager dispatch to extension commands (via kwargs)
- Added MCP access to NexusContext (`mcp` property, `call_tool()` method)
- Built Zerodha MCP server: containerized pykiteconnect wrapper with 8 tools (get_holdings, get_positions, exchange_token, get_login_url, get_profile, check_token_valid, set_access_token, generate_checksum), Dockerfile with non-root user + read-only rootfs, streamable-http on port 8001
- Added `nexus-finance-zerodha` service to docker-compose.yaml on `finance` profile
- Built portfolio sync module: `parse_zerodha_holdings()`, `sync_holdings_to_db()`, `load_holdings_from_db()`, `save_snapshot()`, `format_portfolio_summary()`, `format_portfolio_detail()`
- Implemented `/portfolio` command with real DB data: summary (value, P&L, allocation), detail (per-holding), sync (trigger Zerodha)
- Implemented `/holdings add` command: manual entry for FD, RD, PPF, SGB, gold, loan with key-value params
- Wired `_sync_portfolio` signal handler for `scheduled_sync` events in FinanceExtension
- 70 finance tests (up from 45), 485 core tests (up from 480), all passing
- ruff clean, mypy strict clean, ruff format clean

### Previous session

- Built M5 extension system in Nexus core (NexusExtension protocol, NexusContext API, ExtensionLoader, command registry, schema registration, signal hooks, dynamic skill dirs)
- Scaffolded `extensions/nexus-finance/` as a monorepo extension with pyproject.toml, entry point, 6 commands, 8 skills, 7 database tables
- Wrote real implementations for: indicators.py (SMA/EMA/RSI), research.py (FIRE calculators), charts.py (matplotlib dark theme), gold.py (goodreturns parser), parsers/hdfc.py and sbi.py (CSV parsers), portfolio.py (allocation calculator), schema.py (7 tables)
- Rewrote docs/design/finance.md as full FIRE personal finance advisor design doc

## Current State

- nexus-finance installed in dev mode via `uv pip install -e ./extensions/nexus-finance`
- Extension auto-discovered via entry_points when Nexus starts
- `/portfolio` returns real data from DB (value, P&L, allocation percentages, per-holding detail)
- `/portfolio sync` triggers Zerodha MCP → DB sync
- `/holdings add <type> params...` creates manual holdings (FD/RD/PPF/SGB/gold/loan)
- `scheduled_sync` signal handler syncs Zerodha + saves daily snapshot
- Remaining commands still stub: `/fire`, `/rebalance`, `/research`, `/gold`, `/holdings upload`, `/holdings banks`
- Zerodha MCP server built but not yet tested with real credentials (needs KITE_API_KEY, KITE_API_SECRET)
- Schema tables created, can now be populated via commands or sync
- 555 total tests (485 core + 70 finance), CI green

## Pending Tasks

### Phase 2: Market Data + Banking

- Build MFapi.in MCP server (containerized, NAV data wrapper, no auth needed)
- Gold price scraping via Playwright skill (goodreturns.in)
- Wire chart generation into `/portfolio` and `/gold` commands (matplotlib → ContentStore)
- Bank statement PDF/CSV upload + parsing (wire existing HDFC/SBI parsers)
- Implement `/holdings upload` and `/holdings banks` commands
- Monthly bank statement reminder scheduler
- Add MFapi service to docker-compose.yaml
- Tests for all of the above

### Phase 3: Research + FIRE

- Wire MF research skill to MFapi.in data
- Wire FIRE calculators into `/fire` command
- Wire rebalance logic into `/rebalance` command
- `/research` command with Claude-driven analysis

### Phase 4: Alerts + Polish

- Finance alert skill (scheduled, significant moves)
- FD/RD maturity alerts
- Quarterly rebalance reminders
- Dashboard finance panel

## Key Files

### Core (changed this session)

- `src/nexus/agents/memory.py` — Added `_action_ext_query` and `_action_ext_execute` (lines 484-540)
- `src/nexus/extensions.py` — Added `mcp` property, `call_tool()` method, MCPManager import
- `src/nexus/agents/conversation.py` — Passes `nexus_context` to extension command dispatch
- `src/nexus/runtime.py` — Passes MCP + NexusContext when loading extensions

### Finance extension

- `extensions/nexus-finance/src/nexus_finance/extension.py` — Entry point, registers commands/skills/schema/signals, `_sync_portfolio` handler
- `extensions/nexus-finance/src/nexus_finance/commands.py` — 6 command handlers (portfolio + holdings live, rest stubbed)
- `extensions/nexus-finance/src/nexus_finance/portfolio.py` — Holding dataclass, Zerodha parser, DB sync/load, snapshot, formatting
- `extensions/nexus-finance/src/nexus_finance/schema.py` — 7 SQLite tables
- `extensions/nexus-finance/src/nexus_finance/research.py` — FIRE calculators (implemented)
- `extensions/nexus-finance/src/nexus_finance/charts.py` — matplotlib chart generation (implemented)
- `extensions/nexus-finance/src/nexus_finance/indicators.py` — SMA/EMA/RSI (implemented)
- `extensions/nexus-finance/src/nexus_finance/gold.py` — goodreturns parser (implemented)
- `extensions/nexus-finance/src/nexus_finance/parsers/` — HDFC/SBI CSV parsers (implemented)
- `extensions/nexus-finance/docker/zerodha_mcp.py` — Zerodha MCP server (8 tools)
- `extensions/nexus-finance/docker/zerodha.Dockerfile` — Container definition
- `docs/design/finance.md` — Full FIRE finance advisor design doc (665 lines)

## Important Decisions

- Monorepo: `extensions/nexus-finance/` inside the Nexus repo (not separate)
- MemoryAgent owns all DB access — extensions use `ext_query`/`ext_execute` actions via NexusContext.send_to_memory(), not direct aiosqlite
- NexusContext is passed to extension commands via kwargs (`nexus_context=...`)
- Zerodha Kite API: free personal tier, pykiteconnect SDK, OAuth2 redirect flow, token valid one trading day
- MFapi.in: free API, 10K+ MF schemes, no auth needed
- Gold prices: Playwright scraping goodreturns.in (no city-wise API exists)
- Bank data: manual entry + PDF/CSV upload. Screen scraping ruled out (IT Act risk)
- All external tools in Docker containers (sandbox-first policy)
- Order execution explicitly out of scope — Nexus advises, user executes on Zerodha

## User Profile

- Invests via Zerodha (Kite for stocks/ETFs, Coin for MFs)
- Asset classes: Indian MFs, ETFs, direct equity (NSE/BSE), gold (SGB, digital), PPF, FDs
- FIRE stage: accumulation (10+ years out)
- Advisory depth: full research + recommendations

## Context for Continuation

- Zerodha Kite API: https://kite.trade/docs/connect/v3/ — needs api_key + api_secret from https://developers.kite.trade. Token expires daily at ~6 AM IST.
- MFapi.in: https://api.mfapi.in — no auth. GET /mf for search, GET /mf/{scheme_code} for NAV + history
- The extension system works: `pip install -e ./extensions/nexus-finance` registers it. Commands dispatch through `ConversationManager._ext_commands`.
- Extension commands receive `nexus_context` kwarg — use it for `send_to_memory()` and `call_tool()`
- Push requires: `gh auth switch --user jerynmathew`, `git remote set-url origin https://...`, push, then switch back to `jeryn-fiddler`
- Sub-agents with "deep" and "oracle" categories fail with ProviderModelNotFoundError. Use "quick" or "unspecified-high" or work directly.
- Every financial output must include disclaimer about AI-generated analysis.
- Combined test run (`pytest tests/ extensions/nexus-finance/tests/`) has namespace collision — run separately. Both pass independently.
