# M4 Implementation Plan — Breadth: "It connects to everything you use"

> Version: 1.0
> Created: 2026-05-11
> Status: Review
> Depends on: M3 complete

---

## Scope

M4 adds production resilience, browser automation, session management, and cross-platform messaging.

| Component | Wave | What ships |
|---|---|---|
| **M4.5 Resilience** | A | /status command, dynamic system prompt, Ollama failover via AgentGateway |
| **M4.6 Browser** | A | Playwright MCP sidecar + SSRF policy |
| **M4.7 Checkpoints** | A | /checkpoint and /rollback Telegram commands |
| **M4.1 Discord** | B | Discord transport (discord.py) |
| **M4.1 Slack** | B | Slack transport (Slack MCP + Bolt SDK) |

**Deferred:** Finance (separate design doc at `docs/design/finance.md`), homelab agents (users add MCP sidecars via config).

## Key Decisions

| # | Decision | Rationale |
|---|---|---|
| 1 | Discord + Slack | Personal (Discord) + work (Slack). Two audiences. |
| 2 | Skip homelab agents | MCP-first. Users add sidecars via config. No custom agent code. |
| 3 | Finance deferred | Multi-step workflow needs proper scoping. Design doc created. |
| 4 | Charts deferred with finance | Primary consumer is finance. Local matplotlib rendering. |
| 5 | Full resilience pass | Production readiness. Failover, /status, dynamic capabilities. |
| 6 | Playwright MCP for browser | Official Microsoft MCP server. SSRF blocklist for security. |
| 7 | Session checkpoints | /checkpoint and /rollback. Extends existing checkpointing. |

---

## Task Breakdown

### Phase 1: M4.5 — Resilience & Fallbacks

#### T4.5.1 — /status command
- [ ] Handle `/status` in ConversationManager (or as a Telegram command handler)
- [ ] Query DashboardServer for health, agent status, MCP connectivity
- [ ] Format as a concise status report on Telegram
- [ ] Show: agents (running/crashed), MCP servers (connected/disconnected), trust scores, uptime
- **Tests:**
  - [ ] /status returns formatted health report

#### T4.5.2 — Dynamic system prompt
- [ ] System prompt reflects currently available capabilities
- [ ] If MCP server disconnected → prompt says "Gmail is currently unavailable"
- [ ] If no STT configured → prompt doesn't mention voice capability
- [ ] Query MCPManager.health_check() and MediaHandler state at prompt build time
- **Tests:**
  - [ ] Prompt includes available services
  - [ ] Prompt excludes unavailable services

#### T4.5.3 — Ollama fallback via AgentGateway
- [ ] Update `agentgateway.yaml` with Ollama backend (optional profile)
- [ ] Update `docker-compose.yaml` with Ollama sidecar (profile: local-llm)
- [ ] Document failover configuration
- [ ] When Claude is down, AgentGateway routes to Ollama automatically
- **Tests:**
  - [ ] AgentGateway config validates with Ollama backend

#### T4.5.4 — MCP health monitoring
- [ ] Periodic MCP health check via SchedulerAgent (every 5 min)
- [ ] On health change: update DashboardServer, update system prompt
- [ ] On recovery: log reconnection, restore tools
- **Tests:**
  - [ ] Health check detects disconnected server
  - [ ] Reconnected server restores tools

**Phase 1 exit:** `/status` works on Telegram. System prompt adapts to available services. Ollama fallback documented.

---

### Phase 2: M4.6 — Browser Automation

#### T4.6.1 — Playwright MCP Docker sidecar
- [ ] Add `mcp-browser` service to `docker-compose.yaml`
  - Official `@playwright/mcp` server or community equivalent
  - Profile: `browser`
  - Port mapping for MCP communication
- [ ] SSRF policy: environment variable blocklist for private IP ranges (10.x, 172.16-31.x, 192.168.x)
- [ ] Update `config.example.yaml` with browser MCP config

#### T4.6.2 — Browser intent patterns
- [ ] Add browser patterns to RegexClassifier: "browse", "open", "navigate", "screenshot", "fill form"
- [ ] `tool_groups=["browser", "playwright"]`
- **Tests:**
  - [ ] "open google.com" → browser intent
  - [ ] "take a screenshot of ..." → browser intent

#### T4.6.3 — Governance for browser actions
- [ ] Browser navigation → REQUIRE_APPROVAL (write-like action)
- [ ] SSRF check in policy engine: deny navigation to private IPs
- [ ] Add browser-specific deny patterns
- **Tests:**
  - [ ] Navigation to public URL → approval required
  - [ ] Navigation to 192.168.x.x → denied

**Phase 2 exit:** "Open google.com and screenshot" → Playwright MCP → approval gate → result.

---

### Phase 3: M4.7 — Session Checkpoints

#### T4.7.1 — /checkpoint command
- [ ] Telegram command handler for `/checkpoint`
- [ ] Save named checkpoint: session state + timestamp + label
- [ ] Store in MemoryAgent under `namespace="checkpoints"`
- [ ] Confirm: "Checkpoint saved: {label}"
- **Tests:**
  - [ ] /checkpoint saves session state
  - [ ] Multiple checkpoints stored independently

#### T4.7.2 — /rollback command
- [ ] Telegram command handler for `/rollback`
- [ ] List available checkpoints if no argument
- [ ] Restore session to checkpoint state
- [ ] Confirm: "Rolled back to: {label}"
- **Tests:**
  - [ ] /rollback restores session
  - [ ] /rollback with no checkpoints → helpful message

**Phase 3 exit:** User says "/checkpoint before we try something risky" → checkpoint saved. "/rollback" → restored.

---

### Phase 4: M4.1 — Discord Transport

#### T4.1.1 — Discord transport (`src/nexus/transport/discord.py`)
- [ ] `DiscordTransport` implementing BaseTransport protocol
- [ ] Bot connects to configured guilds/channels
- [ ] Message handler: convert Discord message → InboundMessage → ConversationManager
- [ ] Reply via same channel
- [ ] Support mentions (@Nexus) and DM
- [ ] Add `discord.py` to optional deps: `nexus[discord]`
- **Tests:**
  - [ ] Mock Discord message → InboundMessage
  - [ ] send_text calls correct Discord API

#### T4.1.2 — Discord config + setup
- [ ] `DiscordConfig` in config models
- [ ] `nexus setup-discord` CLI command
- [ ] Tenant resolution: Discord user ID → tenant_id mapping
- [ ] Update config.example.yaml

#### T4.1.3 — Cross-transport continuity
- [ ] Same tenant_id resolved from Discord and Telegram → shared memory, persona, trust
- [ ] Session isolated per transport (different conversations)
- [ ] Verify: message on Discord, then Telegram → both have same memories
- **Tests:**
  - [ ] Same tenant via different transports shares memory

**Phase 4 exit:** Message Nexus on Discord → same persona, same memory as Telegram.

---

### Phase 5: M4.1 — Slack Transport

#### T4.1.4 — Slack transport (`src/nexus/transport/slack.py`)
- [ ] `SlackTransport` implementing BaseTransport protocol
- [ ] Slack Bolt SDK for event handling
- [ ] Message handler: Slack event → InboundMessage → ConversationManager
- [ ] Reply via same channel/thread
- [ ] Support app mentions and DMs
- [ ] Add `slack-bolt` to optional deps: `nexus[slack]`
- **Tests:**
  - [ ] Mock Slack event → InboundMessage
  - [ ] send_text calls Slack API

#### T4.1.5 — Slack config + setup
- [ ] `SlackConfig` in config models
- [ ] `nexus setup-slack` CLI command (bot token, signing secret)
- [ ] Tenant resolution: Slack user ID → tenant_id mapping
- **Tests:**
  - [ ] Config parsing with Slack settings

**Phase 5 exit:** Message Nexus on Slack → same persona, shared memory with Telegram and Discord.

---

## M4 Exit Criteria

| Criterion | How to verify |
|---|---|
| `/status` shows service health on Telegram | Send /status command |
| System prompt reflects available services | Disconnect MCP, verify prompt changes |
| Playwright browses a URL via MCP | "Screenshot google.com" → approval → image |
| SSRF blocked for private IPs | Try to navigate to 192.168.x.x → denied |
| /checkpoint saves, /rollback restores | Multi-turn task with checkpoint/rollback |
| Discord message → same persona as Telegram | Send on Discord, verify response |
| Slack message → shared memory | Send on Slack, ask about previous conversation |
| Cross-transport: Telegram + Discord same tenant | Verify shared memories across transports |

---

## Build Order

```
T4.5.1 /status command
    │
    ├── T4.5.2 Dynamic system prompt
    │
    ├── T4.5.3 Ollama failover config
    │
    └── T4.5.4 MCP health monitoring
              │
T4.6.1 Playwright MCP sidecar
    │
    ├── T4.6.2 Browser intent patterns
    │
    └── T4.6.3 Browser governance
              │
T4.7.1 /checkpoint command
    │
    └── T4.7.2 /rollback command
              │
T4.1.1 Discord transport
    │
    ├── T4.1.2 Discord config + setup
    │
    └── T4.1.3 Cross-transport continuity
              │
T4.1.4 Slack transport
    │
    └── T4.1.5 Slack config + setup
```

---

## Progress Tracking

| Phase | Task | Status | Notes |
|---|---|---|---|
| 1 | T4.5.1 /status command | ⬜ Not started | |
| 1 | T4.5.2 Dynamic system prompt | ⬜ Not started | |
| 1 | T4.5.3 Ollama failover config | ⬜ Not started | |
| 1 | T4.5.4 MCP health monitoring | ⬜ Not started | |
| 2 | T4.6.1 Playwright MCP sidecar | ⬜ Not started | |
| 2 | T4.6.2 Browser intent patterns | ⬜ Not started | |
| 2 | T4.6.3 Browser governance | ⬜ Not started | |
| 3 | T4.7.1 /checkpoint command | ⬜ Not started | |
| 3 | T4.7.2 /rollback command | ⬜ Not started | |
| 4 | T4.1.1 Discord transport | ⬜ Not started | |
| 4 | T4.1.2 Discord config + setup | ⬜ Not started | |
| 4 | T4.1.3 Cross-transport continuity | ⬜ Not started | |
| 5 | T4.1.4 Slack transport | ⬜ Not started | |
| 5 | T4.1.5 Slack config + setup | ⬜ Not started | |
