# Handoff: M1–M6 Complete

> Created: 2026-05-13
> Session: Full M5 + M6 implementation

## Status

M1–M6 complete (except M6.1 Presidium — blocked on upstream). M7 (Presence) planned.

- 718 total tests (556 core + 95 finance + 67 work), 92% core coverage
- 283 of 305 milestone items complete
- 12 commits this session, all pre-commit hooks passing

## What's Built

### Core (M1–M4, prior sessions)
Telegram bot, supervision trees, crash recovery, MCP tools, Google Workspace, LLM routing, morning briefing, web dashboard, trust-gated governance, voice/vision media, Discord/Slack transports, browser automation, session checkpoints.

### M5: Extensions
- **Extension system**: NexusExtension protocol, scoped NexusContext per extension, entry_points discovery, command registry, schema registration, signal hooks
- **nexus-finance**: 6 commands, 2 MCP servers (Zerodha + MFapi.in), 7 DB tables, 8 signal handlers, charts via ContentStore, XIRR, LLM-driven research
- **nexus-work**: 4 commands, 5 DB tables, 6 signal handlers, priority engine (blocking + requester seniority), briefing assembly, LLM action extraction, calendar sync
- **User dashboards**: `/dashboard/finance` and `/dashboard/work` with API endpoints

### M6: Production
- **Rate limiting**: RateLimiter with sliding window per tenant
- **Webhook Telegram**: configurable `webhook_url` + `webhook_port`
- **JSON logging**: JSONFormatter + RotatingFileHandler, `NEXUS_JSON_LOGS=true`
- **Security audit**: docs/design/security.md
- **Hierarchical model routing**: skill.model → extension config → cheap_model → default. Scoped NexusContext, runtime overrides.
- **Documentation**: quickstart guide, extension dev guide, demo video script

## What Remains

### M6.1 — Presidium Governance (3 items, blocked)
Depends on upstream `civitas-io/presidium` package. GovernedModelProvider, GovernedToolProvider, behavioral contracts.

### M7 — Presence (19 items, planned)
- M7.1: PWA web app (chat UI, push notifications)
- M7.2: Android app (WebSocket, voice, device pairing)
- M7.3: Animated avatar + voice-first ("Dross mode")

## Context for Continuation

- Push: `gh auth switch --user jerynmathew`, push, switch back to `jeryn-fiddler`
- Sub-agents with "deep"/"oracle" fail — use "quick" or "unspecified-high"
- Test namespaces collide — run core and extension tests separately
- NexusContext is now scoped per extension (carries `_extension_name`)
- Model routing: `ctx.resolve_model()` for extensions, `skill.model` in SKILL.md frontmatter
