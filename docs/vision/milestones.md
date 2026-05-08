# Nexus — Milestone Plan

> Version: 1.0
> Last updated: 2026-05-08
> Status: Draft

---

## Principles

1. **Each milestone is demoable.** No milestone ends with "infrastructure only." Every milestone adds visible, user-facing capability.
2. **Reliability first.** Every milestone must demonstrate Civitas supervision working. Crash recovery is not a feature added later — it's verified at every stage.
3. **Governance designed in, implemented progressively.** Presidium hooks are in the architecture from M1. Lightweight in-memory policy + trust in M2. Full Presidium integration when the packages ship.
4. **MCP-prioritized.** Prefer MCP servers where mature. Fall back to custom agents where MCP falls short. Both paths governed identically.
5. **Test as you go.** Each task includes its tests. No "add tests later" phase. Integration tests for supervision from M1.

---

## M1 — Foundation: "It talks, it remembers, it recovers"

**Goal:** Nexus runs on Telegram, answers questions via configurable LLM, persists memory across restarts, and demonstrates crash recovery.

**This is the milestone that proves Civitas matters.** If we can't show seamless crash recovery here, nothing else matters.

### M1.1 — Project Scaffolding

- [ ] `src/nexus/` package with `__init__.py`, `__main__.py`
- [ ] `config.py` — Pydantic models, YAML loading, `${ENV_VAR}` substitution, fail-fast validation
- [ ] `cli.py` — Typer CLI: `nexus run`, `nexus setup`, `nexus version`
- [ ] `Dockerfile` — multi-stage, non-root, Python 3.12
- [ ] `docker-compose.yaml` — nexus service + volume mounts
- [ ] `config.example.yaml` — documented template
- [ ] CI: GitHub Actions — lint + test + docker build

### M1.2 — Transport Abstraction + Telegram

- [ ] `transport/base.py` — `BaseTransport` protocol, `InboundMessage` dataclass
- [ ] `transport/telegram.py` — Telegram transport (polling mode, tenant resolution)
- [ ] ConversationManager receives `InboundMessage`, never sees Telegram objects
- [ ] Reply via `reply_transport` reference on each message
- [ ] Typing indicators during processing

### M1.3 — Multi-Tenant Model

- [ ] `models/tenant.py` — `TenantContext` (frozen, carries permissions)
- [ ] `models/profile.py` — `UserProfiles`, `ProfileConfig`, `WorkspaceAccount`
- [ ] Tenant resolution from transport user ID → DB lookup
- [ ] Permission checking with read/write distinction
- [ ] Unknown users rejected with clear message
- [ ] Config seeding: YAML `seed.users` → SQLite `tenants` + `user_config` tables on first boot

### M1.4 — Persona System

- [ ] `persona/loader.py` — load SOUL.md, inject into system prompt
- [ ] `personas/default.md` — shipping default persona
- [ ] Per-tenant persona selection from `user_config`
- [ ] `USER.md` per tenant — user preferences, facts (loaded alongside persona)

### M1.5 — Memory Agent

- [ ] `agents/memory.py` — `MemoryAgent(AgentProcess)`, aiosqlite backend
- [ ] Schema: `tenants`, `user_config`, `sessions`, `messages`, `memories`, `conversations`, `schedule_runs`
- [ ] Actions: `store`, `recall`, `search`, `delete`, `save_message`, `config_get`, `config_set`, `config_get_all`
- [ ] All payload fields validated with `.get()` — no bare `KeyError`
- [ ] Namespaced by tenant ID
- [ ] Session checkpointing — multi-turn sessions survive restarts

### M1.6 — Conversation Manager + LLM

- [ ] `agents/conversation.py` — `ConversationManager(AgentProcess)`
- [ ] Configurable LLM provider (Anthropic, OpenAI, LiteLLM via civitas-contrib)
- [ ] Intent classifier — `IntentClassifier` protocol, `RegexClassifier` as M1 implementation
- [ ] Stateless commands (single request/response) and stateful conversations (multi-turn)
- [ ] Session state with `to_dict()` / `from_dict()` — deferred restore on first message (not `on_start()`)
- [ ] Persona + user context injected into system prompt
- [ ] Conversation history persisted via MemoryAgent (fire-and-forget)

### M1.7 — Supervision Tree + Crash Recovery

- [ ] `topology.yaml` — root supervisor (ONE_FOR_ALL) + integrations supervisor (ONE_FOR_ONE) + memory + scheduler
- [ ] Crash recovery integration test: kill an agent, verify supervisor restarts it, verify user sees no error
- [ ] Backoff policy: exponential for API-backed agents, immediate for memory/scheduler
- [ ] `nexus dashboard` — basic TUI showing agent status, restart counts (leveraging Civitas dashboard)

### M1.8 — Docker + First Boot

- [ ] `docker compose up` works end-to-end
- [ ] `nexus setup` CLI wizard — Telegram bot token, LLM API key, persona selection
- [ ] First boot: seed tenants from config, create DB schema, start supervision tree

### M1 Exit Criteria

- [ ] Send a message to Nexus on Telegram, get an AI-generated response with the configured persona
- [ ] Two users configured, each with different persona and separate conversation history
- [ ] Kill the conversation_manager process — root supervisor restarts everything, next message works
- [ ] Restart the container — memory and conversation history preserved
- [ ] `nexus dashboard` shows all agents running with restart counts
- [ ] Permission check: restricted user cannot trigger write actions

---

## M2 — Integrations: "It knows your email, calendar, and services"

**Goal:** Nexus reads your email and calendar (MCP), monitors homelab services (custom agents), runs scheduled briefings, and has lightweight governance.

### M2.1 — MCP Infrastructure

- [ ] `mcp.py` — `MCPClient`, `MCPManager` (multi-server, merged tool schemas, per-tool routing)
- [ ] Long-lived `aiohttp.ClientSession` per MCP server (no per-request session)
- [ ] `asyncio.Event` for MCP readiness (no busy-wait)
- [ ] JSON-RPC ID counter (`itertools.count`)
- [ ] Proper SSE parser (accumulate `data:` lines, handle multi-line payloads)
- [ ] Health checks with auto-reconnect on server recovery
- [ ] MCP servers as Docker sidecars in `docker-compose.yaml`

### M2.2 — Google Workspace via MCP

- [ ] Google Workspace MCP sidecar configured
- [ ] Tool-use conversation loop: LLM → MCP tool calls → results → LLM → response
- [ ] Intent-based tool filtering — classify first, send only relevant tool schemas
- [ ] Google OAuth setup via `nexus setup google` wizard
- [ ] Working: "What's on my calendar today?", "Check my email", "Draft a reply to..."

### M2.3 — LLM Gateway / Router

- [ ] `llm/router.py` — `ModelRouter` with task-based routing and configurable toggles
- [ ] Task types: CLASSIFY, FORMAT, SUMMARIZE → lightweight/local model; CONVERSE, BRIEFING → primary cloud model
- [ ] Fallback chain: primary → fallback → local (configurable)
- [ ] Circuit breaker: after N consecutive failures on a model, skip for cooldown period
- [ ] Ollama integration via LiteLLM or direct `ollama.AsyncClient`
- [ ] Config: `model.primary`, `model.lightweight`, `model.local`, `model.fallback_chain`
- [ ] Intent-based tool filtering — classify intent first (cheap model), attach only relevant MCP tool schemas to the actual LLM call (expensive model)
- [ ] Docker compose profile for Ollama sidecar (`--profile local-llm`)

### M2.4 — Scheduled Tasks + Morning Briefing

- [ ] `agents/scheduler.py` — cron-based tick loop, state persist/restore via MemoryAgent
- [ ] Morning briefing — fan-out to parallel chunk agents under `briefing` sub-supervisor
- [ ] Each chunk uses its own LLM call with relevant MCP tools only
- [ ] Per-agent timeout — briefing sends with available data, notes unavailable services
- [ ] Iterate all admin tenants for briefing delivery (not hardcoded `users[0]`)
- [ ] Health monitoring as a scheduled task

### M2.5 — Web Dashboard (GenServer + HTTPGateway)

- [ ] `agents/dashboard.py` — `DashboardServer(GenServer)` maintaining live state:
  - Supervision tree topology (agent names, strategies, parent-child relationships)
  - Per-agent health (status, restart count, last message, backoff state)
  - Recent activity feed (last 100 actions with agent, type, latency, tokens)
  - MCP server connectivity (connected/disconnected, tool count)
  - Trust scores per agent (when governance is active)
- [ ] `HTTPGateway` serving on configurable port (default 8080):
  - `/` — static HTML dashboard page (single-page, vanilla JS, no build step)
  - `/api/health` — overall system health (JSON)
  - `/api/topology` — supervision tree structure (JSON)
  - `/api/agents` — per-agent status and metrics (JSON)
  - `/api/activity` — recent activity feed (JSON)
  - SSE endpoint `/api/events` for live updates (optional, polling fallback)
- [ ] Static HTML dashboard — topology visualization, agent health cards, activity feed
- [ ] Embeddable in homelab dashboards (Homepage, Heimdall, Homarr) via iframe or API
- [ ] GenServer `handle_call` for synchronous state queries, `handle_cast` for async updates from agents
- [ ] Agents send health updates to DashboardServer via `self.send("dashboard", {...})` on lifecycle events

### M2.6 — Lightweight Governance (Pre-Presidium)

- [ ] In-memory policy engine — YAML-defined rules, ALLOW/DENY/REQUIRE_APPROVAL
- [ ] Irreversibility gates — `send_email`, `delete_*`, `accept_invite` → REQUIRE_APPROVAL via transport inline buttons
- [ ] In-memory trust scores per agent — positive on approved actions, negative on rejected
- [ ] Basic audit sink — JSONL file with agent identity, action, policy decision, timestamp
- [ ] Governance hooks in ConversationManager — policy check before MCP tool execution

### M2 Exit Criteria

- [ ] "What's on my calendar today?" → MCP tool call → accurate response
- [ ] "Summarize my unread emails" → MCP tool call → useful summary
- [ ] Morning briefing arrives at configured time with email + calendar sections
- [ ] Kill the Gmail MCP sidecar mid-briefing → briefing arrives with available data + "Gmail unavailable" note
- [ ] LLM router: classification uses local model, conversation uses cloud model, fallback works
- [ ] Web dashboard at `http://nexus:8080` shows live topology, agent health, recent activity
- [ ] Dashboard embeddable in Homepage/Heimdall via iframe
- [ ] "Send this email" → approval gate → user confirms → email sent → audit entry
- [ ] Trust score visible in web dashboard

---

## M3 — Depth: "It earns your trust"

**Goal:** Full governance integration, trust-gated autonomy, voice support, web search, and the earn-autonomy arc.

### M3.1 — Presidium Governance Integration

- [ ] Replace lightweight in-memory policy with Presidium `PolicyEngine` (when available) or production-grade YAML engine
- [ ] Agent Registry integration — `AgentRecord` with grants, trust scores, lifecycle states
- [ ] Per-agent credential scoping — separate OAuth tokens per integration agent
- [ ] GovernanceAuditSink — structured, signed audit entries
- [ ] Intent declaration — agent declares scope before task, drift triggers alert
- [ ] Policy violations → trust score decay → more approvals required

### M3.2 — Trust-Gated Autonomy Arc

- [ ] Trust thresholds: > 0.8 autonomous, 0.5-0.8 approval required, < 0.5 advisory only
- [ ] Trust grows: approved draft without edits → +delta
- [ ] Trust decays: rejected draft, policy violation, drift detection → -delta
- [ ] Dashboard shows trust history per agent — which actions built trust, which eroded it
- [ ] Configurable per tenant — risk-tolerant users can set lower approval thresholds

### M3.3 — Web Search + News via MCP

- [ ] Brave Search MCP sidecar in `docker-compose.yaml`
- [ ] Morning briefing optionally includes news headlines
- [ ] "What's in the news?" → web search tool call → formatted summary

### M3.4 — Voice Support

- [ ] Telegram voice message handler (download OGG, transcribe)
- [ ] STT: OpenAI Whisper API or local faster-whisper
- [ ] TTS: OpenAI TTS or local Kokoro/Piper
- [ ] Voice-originated text routes through normal intent pipeline
- [ ] `nexus setup-voice` CLI for voice configuration

### M3.5 — Persona Builder

- [ ] `nexus setup-persona` — interactive CLI to create a new SOUL.md
- [ ] Conversational persona rebuild via Telegram ("change your personality to...")
- [ ] Persona changes logged in audit trail

### M3.6 — Autonomous Skill Creation

- [ ] Skill format: SKILL.md files in `~/.nexus/skills/` (borrowing OpenClaw/Nanobot conventions)
- [ ] Post-task reflection: agent identifies reusable procedures after completing complex tasks
- [ ] Skill synthesis: writes structured SKILL.md with procedure, pitfalls, verification steps
- [ ] Skill improvement: existing skills refined during subsequent use
- [ ] Governance: new skills queued for approval before activation (Telegram inline buttons or CLI)
- [ ] Skill loading: relevant skills injected into system prompt per task (retrieve-on-demand, not context-packing)
- [ ] Public skill repo integration: load compatible skills from community repos where available

### M3 Exit Criteria

- [ ] Full governance demo: attempt unauthorized action → policy deny → audit entry → trust decay
- [ ] Trust arc demo: 5 approved drafts → trust rises → low-stakes drafts become autonomous
- [ ] Rejection → trust falls → more approvals required again
- [ ] Voice: send voice message → transcribed → processed → voice reply
- [ ] Web search: "Find flights to Tokyo" → search results
- [ ] `nexus setup-persona` creates new persona, next message uses it
- [ ] Skill creation: agent completes a complex task → proposes a skill → user approves → skill available for next similar task

---

## M4 — Breadth: "It connects to everything you use"

**Goal:** Additional messaging integrations, homelab services, financial tracking, visual output, resilience.

### M4.1 — Additional Messaging Integrations

- [ ] WhatsApp (read-only via Matrix bridge or MCP)
- [ ] Discord (monitor channels, summarize, respond to mentions)
- [ ] Slack via MCP (work messaging)
- [ ] Each as a separate transport or MCP integration, governed identically

### M4.2 — Homelab Integration Agents

- [ ] `agents/homelab/base.py` — `IntegrationAgent` base class (httpx async client, auth, health checks)
- [ ] Homelab agents configurable per user's stack (Jellyfin, Paperless, Immich, etc.)
- [ ] Service health monitoring — periodic checks, alert on status transitions
- [ ] Natural language queries routed via intent classifier
- [ ] MCP servers used where available; custom `IntegrationAgent` where not

### M4.3 — Financial Tracking

- [ ] Yahoo Finance MCP + Indian market MCP sidecars
- [ ] Morning briefing finance section with configurable watchlist
- [ ] "What's the gold price today?" → MCP tool call → current price

### M4.4 — Visual Output

- [ ] Telegram photo sending (`send_photo`)
- [ ] QuickChart.io integration for data charts (LLM builds Chart.js config → PNG)
- [ ] Finance charts in briefing (optional)
- [ ] Graceful fallback to text-only on chart service failure

### M4.5 — Resilience & Fallbacks

- [ ] LLM failover: cloud → local, local → cloud
- [ ] MCP auto-reconnect on server recovery
- [ ] Per-tool-call timeout — individual MCP failures don't block the loop
- [ ] System prompt dynamically reflects available capabilities
- [ ] `/status` command shows service health

### M4 Exit Criteria

- [ ] Message Nexus on Discord → same persona, same memory as Telegram
- [ ] Claude API revoked → Nexus responds via Ollama in same conversation turn
- [ ] MCP server restarted → tools automatically restored within 5 minutes
- [ ] Finance query → chart PNG sent to Telegram
- [ ] WhatsApp conversation summary → delivered on Telegram

---

## M5 — Polish: "It's ready for others to use"

**Goal:** Production hardening, documentation, community onboarding, full Presidium governance.

### M5.1 — Full Presidium Integration

- [ ] Replace all lightweight governance with Presidium packages (when shipped)
- [ ] `GovernedModelProvider` wrapping LLM calls
- [ ] `GovernedToolProvider` wrapping MCP tool calls
- [ ] Full audit ledger with compliance-exportable records
- [ ] Behavioral contracts (CONSTITUTION.md per agent)

### M5.2 — Production Hardening

- [ ] Rate limiting per tenant
- [ ] Webhook mode for Telegram (alternative to polling)
- [ ] Graceful shutdown with session persistence
- [ ] Log rotation and structured JSON logging
- [ ] Security audit: prompt injection defense, credential handling review

### M5.3 — Documentation + Community

- [ ] Quickstart guide (git clone → working assistant in 15 minutes)
- [ ] Adding integrations guide
- [ ] Adding transports guide
- [ ] Creating personas guide
- [ ] Demo video script covering all five demo scenarios
- [ ] CONTRIBUTING.md

### M5 Exit Criteria

- [ ] All five demo scenarios work reliably (crash recovery, governance, trust arc, multi-tenant, persona)
- [ ] New user: clone → running in 15 minutes
- [ ] Full Presidium governance active (if Presidium packages available)
- [ ] Autonomous skill creation with governance approval
- [ ] Community contribution possible (clear docs, tests, CI)

---

## Dependency Graph

```
M1 Foundation
├── M1.1 Scaffolding
├── M1.2 Transport + Telegram
├── M1.3 Multi-Tenant
├── M1.4 Persona
├── M1.5 Memory
├── M1.6 Conversation + LLM
├── M1.7 Supervision + Crash Recovery  ← THE DEMO
└── M1.8 Docker + First Boot
     │
     ├── M2.1 MCP Infrastructure
     ├── M2.2 Google Workspace (MCP)
     ├── M2.3 LLM Gateway / Router      ← local + cloud + fallback
     ├── M2.4 Scheduler + Briefing
     ├── M2.5 Web Dashboard              ← GenServer + HTTPGateway
     └── M2.6 Lightweight Governance
          │
          ├── M3.1 Presidium Governance
          ├── M3.2 Trust-Gated Autonomy  ← THE GOVERNANCE DEMO
          ├── M3.3 Web Search (MCP)
          ├── M3.4 Voice
          ├── M3.5 Persona Builder
          └── M3.6 Autonomous Skills     ← agent writes its own procedures
               │
               ├── M4.1 More Messaging
               ├── M4.2 Homelab Agents   ← deferred from M2
               ├── M4.3 Finance
               ├── M4.4 Visual Output
               └── M4.5 Resilience
                    │
                    ├── M5.1 Full Presidium
                    ├── M5.2 Hardening
                    └── M5.3 Docs + Community
```

M1 sub-tasks are sequential (each builds on the previous).
M2-M5 sub-tasks within each milestone are largely independent and can be parallelized.

---

## Key Demos (When to Show What)

| Demo | First Available | What It Proves |
|---|---|---|
| **Crash recovery** | M1.7 | Civitas supervision is real. Kill an agent, watch it restart. |
| **Morning briefing with partial failure** | M2.4 | Reliability under degraded conditions. Briefing arrives even when Gmail is down. |
| **Web dashboard in homelab** | M2.5 | Open `http://nexus:8080` — live topology, agent health, trust scores. Embed in Homepage/Heimdall. |
| **Governance denial + audit** | M2.6 | Actions are policy-enforced, not just logged. |
| **Trust-gated autonomy arc** | M3.2 | Agent earns trust over time. Governance is dynamic, not static. |
| **Multi-tenant + persona** | M1.8 | Two users, different personas, private email, shared calendar. |
| **Voice interaction** | M3.4 | Send voice message, get voice reply. |
| **Autonomous skill creation** | M3.6 | Agent learns a procedure, writes a skill, governance approves it, next time it's faster. |
| **Cross-transport** | M4.1 | Same assistant on Telegram and Discord, shared memory. |
