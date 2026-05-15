# Handoff: M1–M6 Complete + M7.1 Chat UI + First Deployment

> Created: 2026-05-14
> Session: 23 commits — M5 extensions, M6 production, Docker deployment, multi-model routing, web chat

## Status

**M1–M6 complete. M7.1 chat UI built. 292/311 milestones checked. 19 remaining (M7).**

- 718 tests (556 core + 95 finance + 67 work), 89% core coverage
- Deployed on Docker with AgentGateway v1.1.0 (Anthropic + Ollama)
- Google OAuth complete, Telegram + web chat both working

## What's Running

| Service | Container | Port | Status |
|---|---|---|---|
| Nexus | nexus | 8080 | Running |
| AgentGateway v1.1.0 | agentgateway | 4000 | Anthropic (claude-*) + Ollama (*) |
| Google MCP | mcp-google | 8000 | OAuth complete for jerynmathew@gmail.com |
| Ollama | host process | 11434 | qwen3:8b |

### Current LLM Config (config.yaml, gitignored)

```yaml
llm:
  base_url: "http://agentgateway:4000"
  model: "qwen3:8b"
  cheap_model: "qwen3:8b"
  max_tokens: 8192
```

To switch to cloud: `model: "claude-sonnet-4-20250514"`, `cheap_model: "claude-haiku-4-5-20251001"`

## What Was Built This Session (23 commits)

### M5: Extensions
- nexus-finance: 6 commands, 2 MCP servers, 8 signal handlers, charts, XIRR
- nexus-work: 4 commands, 5 DB tables, 6 signal handlers, priority engine, briefings, calendar sync
- User dashboards at /dashboard/finance and /dashboard/work

### M6: Production
- Rate limiting, webhook Telegram, JSON logging, security audit
- Hierarchical model routing (skill/extension/task/default)
- Docs: quickstart, extension dev guide, demo script
- Deployment fix audit (6/8 conformant, 2/8 workarounds)
- M6.1 Presidium closed N/A (lightweight governance sufficient)

### Deployment (13 bugs fixed)
- Anthropic API compat, Telegram HTML, MCP errors, think tags, schema timing, catch-all commands

### Multi-Model
- AgentGateway v0.12.0 to v1.1.0, model-name routing, Ollama support

### M7.1: Web Chat
- /chat page with WebSocket, WebTransport, multi-transport routing
- Needs real-world testing by user

### Architecture Decisions
- #17 Adopt, don't invent
- #18 Local-first, sync-optional

## Pending: M6.4 Codebase Audit Remediation

Full audit at `docs/reviews/codebase-audit.md`. Key findings:
1. **ConversationManager god object** (1091 lines) — extract ToolExecutor, SessionManager, ResponseFormatter
2. **15 tests without assertions** — add postcondition checks
3. **85 non-top-level imports in tests** — move to module level
4. **Gateway API handlers** (100+ lines) — extract DB query helpers
5. **20 over-broad `except Exception:`** — narrow or add logging
6. **Duplicate param parsers** — extract shared utility

Priority: tests → imports → gateway → exceptions → ConversationManager decomposition

## What Remains (M7: 19 items)

- M7.1: PWA manifest, dashboard+chat integration, push notifications, offline (chat UI done)
- M7.2: Android app (not started, recommend skip — PWA covers mobile)
- M7.3: Animated avatar, voice-first, Dross mode (not started)
- M7 exit: cross-platform parity verification

## Context for Continuation

- config.yaml gitignored, currently Ollama. Push: gh auth switch --user jerynmathew
- AgentGateway pinned v1.1.0 (not :latest). Google creds in mcp-google-creds volume
- Web chat channel_id prefix: web_. Test namespaces collide — run tests separately
- Sub-agents deep/oracle fail — use quick/unspecified-high
- Chat UI at /chat needs testing — built but not yet verified by user
