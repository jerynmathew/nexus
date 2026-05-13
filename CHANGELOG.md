# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
- **nexus-finance Phases 2–4 — Market Data, FIRE, Alerts**
  - MFapi.in MCP server: containerized httpx wrapper with 4 tools (search_funds, get_nav, get_latest_nav, get_scheme_details), streamable-http on port 8002, no auth required
  - `/gold` command: queries finance_gold_prices table, 30-day trend with percentage change
  - `/fire` command: FIRE progress report with corpus vs target, progress bar, SIP projections for 10/15 year targets. `/fire config` to set monthly expenses, target years, withdrawal/inflation/return rates
  - `/rebalance` command: compares current allocation vs target allocation with delta amounts and add/reduce suggestions
  - `/research` command: searches MFapi.in for matching mutual fund schemes, displays top 5 with scheme codes
  - `/holdings banks` command: shows last upload date per bank from finance_bank_statements
  - `/holdings upload` command: parses HDFC/SBI CSV statements via existing parsers, stores in finance_bank_statements
  - Finance alert signal handler: `finance_alert_check` compares consecutive snapshots, logs when portfolio moves beyond threshold percentage
  - MFapi service in docker-compose.yaml on `finance` profile with read-only rootfs
  - 85 finance extension tests (up from 70)
- **nexus-finance Phase 1 — Portfolio Foundation**
  - Zerodha MCP server: containerized pykiteconnect wrapper with 8 tools (get_holdings, get_positions, exchange_token, login URL, profile, token validation), streamable-http transport on port 8001, Dockerfile with non-root user and read-only rootfs
  - Portfolio sync module: `parse_zerodha_holdings()` maps Kite API response to Holding objects with asset class classification (equity/MF/ETF/gold), `sync_holdings_to_db()` upserts to finance_holdings table, `load_holdings_from_db()` queries by tenant, `save_snapshot()` daily portfolio snapshot with allocation breakdown
  - `/portfolio` command: returns real data from DB with total value, P&L, asset allocation percentages. Subcommands: `detail` (per-holding breakdown), `sync` (trigger Zerodha sync)
  - `/holdings add` command: manual entry for FD, RD, PPF, SGB, gold, loan with key-value syntax (e.g., `/holdings add FD principal=500000 rate=7.1 bank=HDFC`)
  - Portfolio formatting: `format_portfolio_summary()` and `format_portfolio_detail()` with ₹ currency formatting, P&L with signs, allocation percentages
  - Extension signal handler: `_sync_portfolio` registered for `scheduled_sync` events — calls Zerodha MCP, syncs holdings, saves daily snapshot
  - Zerodha service in docker-compose.yaml on `finance` profile with scoped env vars
- **Extension system enhancements (core)**
  - MemoryAgent `ext_query` action: parameterized SELECT on extension tables (guards against non-SELECT)
  - MemoryAgent `ext_execute` action: parameterized INSERT/UPDATE/DELETE on extension tables (guards against DROP/ALTER/CREATE/PRAGMA)
  - NexusContext `mcp` property and `call_tool()` method: extensions can call MCP tools
  - NexusContext passed through ConversationManager dispatch to extension command handlers via kwargs
  - Runtime wiring: MCP manager and NexusContext passed to extensions at load time
- 70 finance extension tests (up from 45), 485 core tests (up from 480), all passing
- Project scaffolding and documentation-first foundation
- Product Requirements Document (PRD)
- Competitive analysis covering OpenClaw, Hermes, Nanobot, NanoClaw, IronClaw
- Milestone plan (M1–M5) with exit criteria and demo checkpoints
- System architecture SVG diagram
- AGENTS.md with conventions, anti-patterns, and wiki maintenance protocol
