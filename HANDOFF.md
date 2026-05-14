# Handoff: M1–M6 Complete + First Deployment

> Created: 2026-05-14
> Session: M5 extensions + M6 production + Docker deployment + multi-model routing

## Status

M1–M6 complete (except M6.1 Presidium — blocked on upstream). First Docker deployment done and tested. M7 (Presence) planned.

- 718 total tests (556 core + 95 finance + 67 work), 92% core coverage
- 283 of 305 milestone items complete
- Deployed on Docker with AgentGateway v1.1.0 (Anthropic + Ollama multi-provider)

## What's Running

| Service | Container | Port | Provider |
|---|---|---|---|
| Nexus | nexus | 8080 (dashboard) | — |
| AgentGateway v1.1.0 | agentgateway | 4000 | Anthropic (claude-*) + Ollama (*) |
| Google MCP | mcp-google | 8000 | Gmail/Calendar/Tasks (OAuth complete) |
| Ollama | host process | 11434 | qwen3:8b (local) |

## Deployment Fixes Applied

Commit f78162d + subsequent commits fixed 13 bugs found during first Docker deployment:

1. Wrong Anthropic model name (claude-haiku-4-20250414 → claude-haiku-4-5-20251001)
2. Empty content blocks rejected by Anthropic — omit content field when empty
3. Stale session replay — filter empty messages from history
4. Tool loop exhaustion — fallback extracts last tool result
5. Telegram link rendering — extract links before html.escape
6. ANSI escape codes in MCP errors — stripped
7. Auth URL passthrough — captured from tool results
8. LLM error logging — 400/500 responses log body
9. Dockerfile — extensions + skills included
10. Extension schema timing — apply_extension_schemas() after load
11. Catch-all command handler — forwards all /commands to extensions
12. Think tag stripping — Qwen3 `<think>` tags removed from responses
13. Markdown headings/lists — ## → bold, - → bullet in Telegram

## Architecture Decisions Added

- **#17 Adopt, don't invent** — use OSS libraries, build only the intelligence layer
- **#18 Local-first, sync-optional** — works with zero external accounts

## Pending: M6.2.1 Deployment Fix Audit

Verify the 13 fixes against upstream docs (Anthropic, MCP SDK, Telegram, AgentGateway, Google MCP). See milestones.md M6.2.1 for checklist.

## What Remains

| Category | Items | Status |
|---|---|---|
| M6.1 Presidium | 3 | Blocked on upstream |
| M6.2.1 Fix Audit | 6 | Pending — verify fixes against upstream docs |
| M7.1 PWA | 5 | Planned — frontend |
| M7.2 Android | 5 | Planned — mobile |
| M7.3 Avatar | 5 | Planned — frontend |
| M7 Exit | 4 | Planned — verification |

## Key Configuration

### Multi-model routing (agentgateway.yaml)
```yaml
llm:
  port: 4000
  models:
    - name: "claude-*"           # Cloud models → Anthropic
      provider: anthropic
      params:
        apiKey: "$ANTHROPIC_API_KEY"
    - name: "*"                  # Everything else → Ollama
      provider: openAI
      params:
        hostOverride: "host.docker.internal:11434"
```

### Current config.yaml (Ollama for testing)
```yaml
llm:
  base_url: "http://agentgateway:4000"
  model: "qwen3:8b"             # Local via Ollama
  cheap_model: "qwen3:8b"
```

### To switch to Anthropic for conversations
```yaml
llm:
  base_url: "http://agentgateway:4000"
  model: "claude-sonnet-4-20250514"    # Cloud conversations
  cheap_model: "qwen3:8b"              # Local for cheap tasks
```

## Context for Continuation

- Push: `gh auth switch --user jerynmathew`, push, switch back to `jeryn-fiddler`
- Sub-agents with "deep"/"oracle" fail — use "quick" or "unspecified-high"
- Test namespaces collide — run core and extension tests separately
- config.yaml is gitignored — user-specific
- Google OAuth complete for jerynmathew@gmail.com — creds in mcp-google-creds volume
- AgentGateway pinned to v1.1.0 (not :latest which is v0.12.0)
