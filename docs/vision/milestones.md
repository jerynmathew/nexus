# Nexus — Milestone Plan

> Version: 2.0
> Last updated: 2026-05-11
> Status: M1–M3 complete, M4+ planned

---

## Principles

1. **Each milestone is demoable.** No milestone ends with "infrastructure only." Every milestone adds visible, user-facing capability.
2. **Reliability first.** Every milestone must demonstrate Civitas supervision working. Crash recovery is not a feature added later — it's verified at every stage.
3. **Governance designed in, implemented progressively.** Presidium hooks are in the architecture from M1. Lightweight in-memory policy + trust in M2. Full Presidium integration when the packages ship.
4. **MCP-prioritized.** Prefer MCP servers where mature. Fall back to custom agents where MCP falls short. Both paths governed identically.
5. **Test as you go.** Each task includes its tests. No "add tests later" phase. Integration tests for supervision from M1.

---

## M1 — Foundation: "It talks, it remembers, it recovers" ✅

**Status: Complete** — 30 tasks, 89 tests. [Implementation plan](../plans/m1-implementation.md)

**Goal:** Nexus runs on Telegram, answers questions via configurable LLM, persists memory across restarts, and demonstrates crash recovery.

### M1.1 — Project Scaffolding

- [x] `src/nexus/` package with `__init__.py`, `__main__.py`
- [x] `config.py` — Pydantic models, YAML loading, `${ENV_VAR}` substitution, fail-fast validation
- [x] `cli.py` — Typer CLI: `nexus run`, `nexus setup`, `nexus version`
- [x] `Dockerfile` — multi-stage, non-root, Python 3.12
- [x] `docker-compose.yaml` — nexus service + volume mounts
- [x] `config.example.yaml` — documented template
- [x] CI: GitHub Actions — lint + test + docker build

### M1.2 — Transport Abstraction + Telegram

- [x] `transport/base.py` — `BaseTransport` protocol, `InboundMessage` dataclass
- [x] `transport/telegram.py` — Telegram transport (polling mode, tenant resolution)
- [x] ConversationManager receives `InboundMessage`, never sees Telegram objects
- [x] Reply via `reply_transport` reference on each message
- [x] Typing indicators during processing

### M1.3 — Multi-Tenant Model

- [x] `models/tenant.py` — `TenantContext` (frozen, carries permissions)
- [x] `models/profile.py` — `UserProfiles`, `ProfileConfig`, `WorkspaceAccount`
- [x] Tenant resolution from transport user ID → DB lookup
- [x] Permission checking with read/write distinction
- [x] Unknown users rejected with clear message
- [x] Config seeding: YAML `seed.users` → SQLite `tenants` + `user_config` tables on first boot

### M1.4 — Persona System

- [x] `persona/loader.py` — load SOUL.md, inject into system prompt
- [x] `personas/default.md` — shipping default persona
- [x] Per-tenant persona selection from `user_config`
- [x] `USER.md` per tenant — user preferences, facts (loaded alongside persona)

### M1.5 — Memory Agent

- [x] `agents/memory.py` — `MemoryAgent(AgentProcess)`, aiosqlite backend
- [x] Schema: `tenants`, `user_config`, `sessions`, `messages`, `memories`, `conversations`, `schedule_runs`
- [x] Actions: `store`, `recall`, `search`, `delete`, `save_message`, `config_get`, `config_set`, `config_get_all`
- [x] All payload fields validated with `.get()` — no bare `KeyError`
- [x] Namespaced by tenant ID
- [x] Session checkpointing — multi-turn sessions survive restarts

### M1.6 — Conversation Manager + LLM

- [x] `agents/conversation.py` — `ConversationManager(AgentProcess)`
- [x] Configurable LLM provider (Anthropic, OpenAI, LiteLLM via civitas-contrib)
- [x] Intent classifier — `IntentClassifier` protocol, `RegexClassifier` as M1 implementation
- [x] Stateless commands (single request/response) and stateful conversations (multi-turn)
- [x] Session state with `to_dict()` / `from_dict()` — deferred restore on first message (not `on_start()`)
- [x] Persona + user context injected into system prompt
- [x] Conversation history persisted via MemoryAgent (fire-and-forget)

### M1.7 — Supervision Tree + Crash Recovery

- [x] `topology.yaml` — root supervisor (ONE_FOR_ALL) + integrations supervisor (ONE_FOR_ONE) + memory + scheduler
- [x] Crash recovery integration test: kill an agent, verify supervisor restarts it, verify user sees no error
- [x] Backoff policy: exponential for API-backed agents, immediate for memory/scheduler
- [x] `nexus dashboard` — basic TUI showing agent status, restart counts (leveraging Civitas dashboard)

### M1.8 — Docker + First Boot

- [x] `docker compose up` works end-to-end
- [x] `nexus setup` CLI wizard — Telegram bot token, LLM API key, persona selection
- [x] First boot: seed tenants from config, create DB schema, start supervision tree

### M1 Exit Criteria

- [x] Send a message to Nexus on Telegram, get an AI-generated response with the configured persona
- [x] Two users configured, each with different persona and separate conversation history
- [x] Kill the conversation_manager process — root supervisor restarts everything, next message works
- [x] Restart the container — memory and conversation history preserved
- [x] `nexus dashboard` shows all agents running with restart counts
- [x] Permission check: restricted user cannot trigger write actions

---

## M2 — Integrations: "It knows your email, calendar, and services" ✅

**Status: Complete** — Wave A (19 tasks) + Wave B (8 tasks). [Wave A plan](../plans/m2-wave-a-implementation.md) · [Wave B plan](../plans/m2-wave-b-implementation.md)

**Goal:** Nexus reads your email and calendar (MCP), monitors homelab services (custom agents), runs scheduled briefings, and has lightweight governance.

### M2.1 — MCP Infrastructure

- [x] `mcp.py` — `MCPClient`, `MCPManager` (multi-server, merged tool schemas, per-tool routing)
- [x] Long-lived `aiohttp.ClientSession` per MCP server (no per-request session)
- [x] `asyncio.Event` for MCP readiness (no busy-wait)
- [x] JSON-RPC ID counter (`itertools.count`)
- [x] Proper SSE parser (accumulate `data:` lines, handle multi-line payloads)
- [x] Health checks with auto-reconnect on server recovery
- [x] MCP servers as Docker sidecars in `docker-compose.yaml`

### M2.2 — Google Workspace via MCP

- [x] Google Workspace MCP sidecar configured
- [x] Tool-use conversation loop: LLM → MCP tool calls → results → LLM → response
- [x] Intent-based tool filtering — classify first, send only relevant tool schemas
- [x] Google OAuth setup via `nexus setup google` wizard
- [x] Working: "What's on my calendar today?", "Check my email", "Draft a reply to..."

### M2.3 — LLM Gateway / Router

- [x] `llm/router.py` — `ModelRouter` with task-based routing and configurable toggles
- [x] Task types: CLASSIFY, FORMAT, SUMMARIZE → lightweight/local model; CONVERSE, BRIEFING → primary cloud model
- [x] Fallback chain: primary → fallback → local (configurable)
- [x] Circuit breaker: after N consecutive failures on a model, skip for cooldown period
- [x] Ollama integration via LiteLLM or direct `ollama.AsyncClient`
- [x] Config: `model.primary`, `model.lightweight`, `model.local`, `model.fallback_chain`
- [x] Intent-based tool filtering — classify intent first (cheap model), attach only relevant MCP tool schemas to the actual LLM call (expensive model)
- [x] Docker compose profile for Ollama sidecar (`--profile local-llm`)

### M2.4 — Scheduled Tasks + Morning Briefing (Skill-Driven)

- [x] `agents/scheduler.py` — cron-based tick loop, state persist/restore via MemoryAgent
- [x] Morning briefing as a **skill**: `~/.nexus/skills/morning-briefing/SKILL.md` shipped as default
- [x] Scheduler triggers skill execution via ConversationManager (not dedicated briefing agents)
- [x] ConversationManager executes skill: parallel MCP tool calls via `asyncio.TaskGroup`
- [x] Each tool call uses cheap model (Haiku) via ModelRouter
- [x] Per-tool-call timeout (30s) — TaskGroup catches failures, available sections still sent
- [x] Iterate all admin tenants for briefing delivery (not hardcoded `users[0]`)
- [x] Users can edit SKILL.md to customize briefing format, sections, timing

### M2.5 — Web Dashboard (GenServer + HTTPGateway)

- [x] `agents/dashboard.py` — `DashboardServer(GenServer)` maintaining live state:
  - Supervision tree topology (agent names, strategies, parent-child relationships)
  - Per-agent health (status, restart count, last message, backoff state)
  - Recent activity feed (last 100 actions with agent, type, latency, tokens)
  - MCP server connectivity (connected/disconnected, tool count)
  - Trust scores per agent (when governance is active)
- [x] `HTTPGateway` serving on configurable port (default 8080):
  - `/` — static HTML dashboard page (single-page, vanilla JS, no build step)
  - `/api/health` — overall system health (JSON)
  - `/api/topology` — supervision tree structure (JSON)
  - `/api/agents` — per-agent status and metrics (JSON)
  - `/api/activity` — recent activity feed (JSON)
  - SSE endpoint `/api/events` for live updates (optional, polling fallback)
- [x] Static HTML dashboard — topology visualization, agent health cards, activity feed
- [x] Embeddable in homelab dashboards (Homepage, Heimdall, Homarr) via iframe or API
- [x] GenServer `handle_call` for synchronous state queries, `handle_cast` for async updates from agents
- [x] Agents send health updates to DashboardServer via `self.send("dashboard", {...})` on lifecycle events

### M2.6 — Context Compression

- [x] `ContextCompressor` protocol — pluggable compression engine
- [x] Default implementation: 4-phase compression (prune old tool results → determine boundaries → LLM summarize middle turns → assemble compressed messages)
- [x] Trigger: at 50% context window utilization (configurable threshold)
- [x] Iterative re-compression: updates existing summary across multiple compressions, doesn't re-summarize from scratch
- [x] Tail protection: last N messages always preserved (configurable, default 20)
- [x] Uses cheap model (Haiku) for summarization — separate from conversation model
- [x] Essential for daily-driver use: without this, multi-day conversations degrade or crash

### M2.7 — Lightweight Governance (Pre-Presidium)

- [x] In-memory policy engine — YAML-defined rules, ALLOW/DENY/REQUIRE_APPROVAL
- [x] Irreversibility gates — `send_email`, `delete_*`, `accept_invite` → REQUIRE_APPROVAL via transport inline buttons
- [x] **Risk-based tool approval** — classify tool calls by risk level:
  - Low (read-only: search, list, get) → auto-allowed
  - Medium (mutations: create, update, label) → configurable (default: auto-allowed)
  - High (destructive: delete, send, execute shell) → always prompted
  - Hardline blocklist: `rm -rf /`, fork bombs, `dd` to block devices — always denied, no override
- [x] In-memory trust scores per agent — positive on approved actions, negative on rejected
- [x] Basic audit sink — JSONL file with agent identity, action, policy decision, timestamp
- [x] Governance hooks in ConversationManager — policy check before MCP tool execution

### M2 Exit Criteria

- [x] "What's on my calendar today?" → MCP tool call → accurate response
- [x] "Summarize my unread emails" → MCP tool call → useful summary
- [x] Morning briefing arrives at configured time with email + calendar sections
- [x] Kill the Gmail MCP sidecar mid-briefing → briefing arrives with available data + "Gmail unavailable" note
- [x] LLM router: classification uses local model, conversation uses cloud model, fallback works
- [x] Web dashboard at `http://nexus:8080` shows live topology, agent health, recent activity
- [x] Dashboard embeddable in Homepage/Heimdall via iframe
- [x] "Send this email" → approval gate → user confirms → email sent → audit entry
- [x] Trust score visible in web dashboard

---

## M3 — Depth: "It earns your trust" ✅

**Status: Complete** — Wave A (13 tasks) + Wave B (8 tasks). [Wave A plan](../plans/m3-wave-a-implementation.md) · [Wave B plan](../plans/m3-wave-b-implementation.md)

**Note:** M3.1 (Presidium integration) deferred — blocked on upstream package. M3.6 (autonomous skill creation) deferred to M4+.

**Goal:** Full governance integration, trust-gated autonomy, voice support, web search, and the earn-autonomy arc.

### M3.1 — Presidium Governance Integration

- [x] Replace lightweight in-memory policy with Presidium `PolicyEngine` (when available) or production-grade YAML engine
- [x] Agent Registry integration — `AgentRecord` with grants, trust scores, lifecycle states
- [x] Per-agent credential scoping — separate OAuth tokens per integration agent
- [x] GovernanceAuditSink — structured, signed audit entries
- [x] Intent declaration — agent declares scope before task, drift triggers alert
- [x] Policy violations → trust score decay → more approvals required

### M3.2 — Trust-Gated Autonomy Arc

- [x] Trust thresholds: > 0.8 autonomous, 0.5-0.8 approval required, < 0.5 advisory only
- [x] Trust grows: approved draft without edits → +delta
- [x] Trust decays: rejected draft, policy violation, drift detection → -delta
- [x] Dashboard shows trust history per agent — which actions built trust, which eroded it
- [x] Configurable per tenant — risk-tolerant users can set lower approval thresholds

### M3.3 — Web Search + News via MCP

- [x] Brave Search MCP sidecar in `docker-compose.yaml`
- [x] Morning briefing optionally includes news headlines
- [x] "What's in the news?" → web search tool call → formatted summary

### M3.4 — Media Support (Voice, Image, Video)

- [x] **Voice (inbound):** Telegram voice/audio handler → download OGG → STT (OpenAI Whisper API or local faster-whisper) → text pipeline
- [x] **Voice (outbound):** TTS response generation (OpenAI TTS or local Kokoro/Piper) → send as Telegram voice note alongside text
- [x] **Image (inbound):** Telegram photo handler → download highest-res image → send to vision-capable LLM (Claude, GPT-4o) for analysis/description
- [x] **Image (outbound):** Chart rendering (QuickChart.io) → send as Telegram photo with caption. Claude image generation → decode + send.
- [x] **Video (inbound):** Telegram video/video_note handler → extract audio (ffmpeg pipe) → STT → text pipeline. Optionally: extract frames → vision LLM.
- [x] **Document (inbound):** Telegram document handler → download → parse (PDF text extraction, plain text) → include in LLM context
- [x] `InboundMessage.media_type` + `media_bytes` fields in transport protocol (already in design)
- [x] `BaseTransport.send_photo()`, `send_voice()`, `send_document()` outbound methods
- [x] `nexus setup-voice` CLI for STT/TTS provider configuration
- [x] ffmpeg added to Docker image for audio extraction

### M3.5 — Persona Builder + Identity Evolution

- [x] `nexus setup-persona` — interactive CLI to create a new SOUL.md
- [x] Conversational persona rebuild via Telegram ("change your personality to...")
- [x] Persona changes logged in audit trail
- [x] **Agent-initiated identity evolution** — agent proposes SOUL.md updates based on interaction patterns:
  - "I've noticed you prefer shorter responses. Should I update my personality?"
  - Changes go through approval gate (same as skill creation)
  - Diff shown before applying — user sees exactly what changes
  - Audit trail captures before/after for governance

### M3.7 — Proactive Heartbeat

- [x] Default skill: `~/.nexus/skills/heartbeat/SKILL.md` — shipped alongside morning-briefing
- [x] Schedule: `*/30 * * * *` (every 30 minutes, configurable)
- [x] Agent reviews: recent session context, USER.md, pending tasks, upcoming events
- [x] Decision: agent decides whether to notify — not just a timer, model-driven judgment
- [x] Silence is valid: if nothing actionable, agent responds `HEARTBEAT_OK` (no notification sent)
- [x] Active hours: configurable window (e.g., 7am-10pm) — no 3am pings
- [x] Reengagement cooldown: won't ping again within N minutes of last interaction
- [x] Uses cheap model (Haiku) — low token cost per check (~2-5K tokens)
- [x] Delivery: via tenant's configured transport (Telegram, etc.)

### M3.6 — Autonomous Skill Creation + Skill Ecosystem

- [x] Skill format: SKILL.md files in `~/.nexus/skills/` (borrowing OpenClaw/Nanobot conventions)
- [x] Skill persistence: filesystem (primary) + SQLite `skills` table (backup) + optional git export
- [x] Startup reconciliation: MemoryAgent syncs filesystem ↔ SQLite on boot
- [x] Post-task reflection: agent identifies reusable procedures after completing complex tasks
- [x] Skill synthesis: writes structured SKILL.md with procedure, pitfalls, verification steps
- [x] Skill improvement: existing skills refined during subsequent use
- [x] Governance: all skills (local, community, discovered) require approval before activation (Telegram inline buttons)
- [x] Skill loading: relevant skills injected into system prompt per task (retrieve-on-demand, not context-packing)
- [x] Community repo sync: `nexus skills sync` pulls from public `civitas-io/nexus-skills` repo, stages as pending
- [x] Skill publishing: `nexus skills publish <skill>` opens PR against community repo
- [x] Skill discovery (SkillScanner): scheduled background search for useful procedures on web/GitHub, synthesized into SKILL.md, proposed for approval
- [x] `nexus skills export` / `nexus skills import --from-repo` for migration and backup

### M3 Exit Criteria

- [x] Full governance demo: attempt unauthorized action → policy deny → audit entry → trust decay
- [x] Trust arc demo: 5 approved drafts → trust rises → low-stakes drafts become autonomous
- [x] Rejection → trust falls → more approvals required again
- [x] Voice: send voice message → transcribed → processed → voice reply
- [x] Image: send photo → vision LLM describes/analyzes → text response
- [x] Image outbound: chart data → QuickChart PNG → sent as Telegram photo
- [x] Web search: "Find flights to Tokyo" → search results
- [x] `nexus setup-persona` creates new persona, next message uses it
- [x] Skill creation: agent completes a complex task → proposes a skill → user approves → skill available for next similar task

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

### M4.6 — Browser Automation (via MCP)

- [ ] Playwright MCP server as Docker sidecar (not custom browser implementation)
- [ ] Web browsing: navigate, click, type, screenshot, extract text
- [ ] Use case: fill forms, check status pages, interact with web UIs that have no API
- [ ] SSRF policy: block private network navigation by default, opt-in allowlist
- [ ] Governed: browser actions go through same policy check as all tool calls

### M4.7 — Session Checkpoints + Rollback

- [ ] Manual checkpoint: user says "checkpoint this" or `/checkpoint` → session snapshot saved
- [ ] Rollback: `/rollback` restores to last checkpoint — undo for conversations
- [ ] Checkpoint storage: alongside session messages in SQLite
- [ ] Useful for complex multi-turn tasks where you want to try different approaches

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

## M6 — Presence: "It lives where you are"

**Goal:** Native apps, animated avatar, voice-first interaction. Low priority — Telegram + web dashboard covers core use cases. This milestone is about presence and personality.

### M6.1 — Web App (PWA)

- [ ] Progressive Web App — installable on any device, works offline for cached data
- [ ] Chat interface: full conversation UI (alternative to Telegram for users who prefer browser)
- [ ] Dashboard integration: conversation + dashboard in one interface
- [ ] Push notifications via service worker
- [ ] Builds on M2.5 HTTPGateway — same backend, richer frontend

### M6.2 — Android App

- [ ] Companion app — connects to Nexus instance via WebSocket (LAN or Tailscale)
- [ ] Chat interface + push notifications
- [ ] Voice input/output (STT/TTS on device or via Nexus backend)
- [ ] Device pairing: approval flow before first connection
- [ ] Foreground service for persistent connection

### M6.3 — Animated Avatar + Voice-First Mode

- [ ] Animated persona representation — simple avatar with idle/speaking/thinking animations
- [ ] Voice-first interaction: wake word or push-to-talk → STT → process → TTS → animated response
- [ ] Avatar rendered in web app (M6.1) and optionally in Android app (M6.2)
- [ ] Persona-driven: avatar style, voice, and animations tied to SOUL.md selection
- [ ] "Dross mode": the assistant has a visual presence, not just text in a chat window

### M6 Exit Criteria

- [ ] Open `http://nexus:8080/chat` — full conversation UI with animated avatar
- [ ] Android app installed, paired, push notifications working
- [ ] Voice-first: tap mic → speak → see avatar animate → hear voice response
- [ ] Same persona, same memory, same governance across Telegram + web + Android

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
     ├── M2.4 Scheduler + Briefing       ← skill-driven, not hardcoded agents
     ├── M2.5 Web Dashboard              ← GenServer + HTTPGateway
     ├── M2.6 Context Compression        ← essential for daily-driver use
     └── M2.7 Lightweight Governance     ← risk-based tool approval
          │
          ├── M3.1 Presidium Governance
          ├── M3.2 Trust-Gated Autonomy  ← THE GOVERNANCE DEMO
          ├── M3.3 Web Search (MCP)
          ├── M3.4 Media (voice/image/video)
          ├── M3.5 Persona Builder + Identity Evolution
          ├── M3.6 Autonomous Skills     ← agent writes its own procedures
          └── M3.7 Proactive Heartbeat   ← agent decides when to notify
               │
               ├── M4.1 More Messaging
               ├── M4.2 Homelab Agents
               ├── M4.3 Finance
               ├── M4.4 Visual Output
               ├── M4.5 Resilience
               ├── M4.6 Browser (MCP)
               └── M4.7 Session Checkpoints
                    │
                    ├── M5.1 Full Presidium
                    ├── M5.2 Hardening
                    └── M5.3 Docs + Community
                         │
                         ├── M6.1 Web App (PWA)
                         ├── M6.2 Android App
                         └── M6.3 Animated Avatar + Voice-First  ← "Dross mode"
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
| **Media interaction** | M3.4 | Send voice → voice reply. Send photo → vision analysis. Charts sent as images. |
| **Autonomous skill creation** | M3.6 | Agent learns a procedure, writes a skill, governance approves it, next time it's faster. |
| **Proactive check-in** | M3.7 | Agent notices something and pings you — without being asked. Model-driven, not just a timer. |
| **Cross-transport** | M4.1 | Same assistant on Telegram and Discord, shared memory. |
| **Browser automation** | M4.6 | "Book that restaurant" → Playwright MCP browses, fills form, confirms. |
| **Animated avatar** | M6.3 | Talk to Dross — see it animate, hear its voice, feel its personality. |
