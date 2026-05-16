# Handoff: M1–M6 Complete (incl. M6.4 Audit) + M7.1 Chat UI

> Created: 2026-05-14
> Updated: 2026-05-16
> Sessions: 24 commits — M5 extensions, M6 production, Docker deployment, multi-model routing, web chat, codebase audit remediation

## Status

**M1–M6 complete (incl. M6.4 audit remediation + ConversationManager decomposition). M7.1 chat UI built. 299/311 milestones checked. 12 remaining (M7).**

- 546 core unit tests + 95 finance + 59 work = 700 total, 88.7% core coverage
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

## What Was Built (24 commits)

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

### M6.4: Codebase Audit Remediation (latest)
- 44 assertion-less tests → all now have postcondition checks (0 remaining)
- 86 non-top-level imports → all moved to module level across 14 files (0 remaining)
- Gateway handlers decomposed: 7 query helpers extracted (99→22 and 78→29 lines)
- 8 silent `except Exception:` handlers → all now have `logger.debug` calls
- Shared `nexus.utils.parse_key_value_params` extracted from duplicate extension code
- Extension `__version__` inline import documented as accepted exception in AGENTS.md
- ConversationManager decomposed: ToolExecutor (152 lines), ResponseFormatter (75 lines), help.py (122 lines). 1095→826 lines (−25%)

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

## What Remains (M7: 13 items)

- M7.1: PWA manifest, dashboard+chat integration, push notifications, offline (chat UI done)
- M7.2: Android app (not started, recommend skip — PWA covers mobile)
- M7.3: Animated avatar, voice-first, Dross mode (not started)
- M7 exit: cross-platform parity verification

## Context for Continuation

- config.yaml gitignored, currently Ollama. Push: gh auth switch --user jerynmathew
- AgentGateway pinned v1.1.0 (not :latest). Google creds in mcp-google-creds volume
- Web chat channel_id prefix: web_. Test namespaces collide — run tests separately
- Chat UI at /chat needs testing — built but not yet verified by user
- New files: `src/nexus/utils.py`, `src/nexus/agents/tool_executor.py`, `src/nexus/agents/response_formatter.py`, `src/nexus/agents/help.py`
- AGENTS.md updated: import exception for extension version properties, new modules in layout
- ConversationManager no longer owns transport directly — uses `self._formatter` (ResponseFormatter)
