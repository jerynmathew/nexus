HANDOFF CONTEXT
===============

GOAL
----
Continue Nexus development. M1 and M2 Wave A are complete and live. Next: M2 Wave B (web dashboard + content viewer + context compression) or polish/stabilize.

WORK COMPLETED
--------------
### M1 — Foundation (complete, 15 commits)
- Full Civitas supervision tree: MemoryAgent, ConversationManager, SchedulerAgent
- Telegram transport (polling), CLI transport (dev)
- Persona system (SOUL.md + USER.md), Dross persona
- LLMClient → AgentGateway (port 4000) → Anthropic
- Session checkpointing, tenant seeding, FTS5 memory search
- Config system (Pydantic + YAML), CLI (nexus run/setup/version)
- Dockerfile, docker-compose, GitHub Actions CI
- Pre-commit hooks: ruff (17 rule sets), mypy strict, gitleaks, trailing whitespace
- 89 unit + integration tests, all passing

### M2 Wave A — Daily-driver features (complete, 12 commits)
- MCPManager using official `mcp` Python SDK (sse/streamable-http/stdio transports)
- Google Workspace MCP sidecar (taylorwilsdon/google_workspace_mcp, built from source)
- OAuth 2.1 flow completed — Gmail, Calendar, Tasks access working
- Tool-use loop: LLM calls MCP tools, gets results, composes response
- Task-based model routing: Haiku for classify/summarize, Sonnet for converse
- Governance: PolicyEngine (read→ALLOW, write→REQUIRE_APPROVAL), JSONL audit sink
- Skill system: SKILL.md parser, SkillManager, morning briefing skill
- SchedulerAgent: real cron engine using croniter, tick loop
- Telegram formatting: markdown→HTML conversion, message splitting at 4096 chars
- MCP result parsing: handles errors, images, resources
- 133 total tests (121 unit + 12 integration), all passing

### Live verified
- "Check my email" → MCP tool call → Gmail API → email summary on Telegram
- Full tool-use loop: LLM → tool call → MCP → results → LLM → formatted response
- AgentGateway proxying both Sonnet and Haiku models
- OAuth tokens persisted in Docker volume

CURRENT STATE
-------------
- Nexus repo: 43 commits on main, NOT pushed to GitHub
- All repos clean (no uncommitted changes)
- Docker containers running: agentgateway (port 4000), mcp-google (port 8000)
- Nexus runs natively via `uv run nexus run --config config.yaml`
- config.yaml exists with real credentials (gitignored)
- .env has ANTHROPIC_API_KEY, TELEGRAM_BOT_TOKEN, GOOGLE_* credentials
- data/nexus.db has tenant "jeryn" with Dross persona

PENDING TASKS
-------------
### M2 Wave B (planned, not started)
- HTTPGateway + DashboardServer(GenServer) on :8080
  - /api/health, /api/topology, /api/agents, /api/activity
  - /view/<id> — rich HTML content viewer for long responses
  - Static HTML dashboard (vanilla JS, no build step)
- Content viewer: ConversationManager stores rich responses → URL → TL;DR + link on Telegram
- Context compression: 4-phase compression at 50% context window utilization

### Polish & stabilize
- Intent → tool_group mapping (currently falls back to all tools every time)
- Live test: calendar queries, morning briefing trigger, approval flow for send_email
- Push to GitHub (jerynmathew/nexus)

### Future milestones
- M3: Presidium governance, trust-gated autonomy, voice/image, skill auto-creation
- M4: Additional messaging (Discord, Slack), homelab agents, finance, browser automation
- M5: Production hardening, documentation, community
- M6: PWA web app, Android app, animated avatar ("Dross mode")

KEY FILES
---------
- nexus/AGENTS.md — project reference, 14 key decisions, 7 anti-patterns
- nexus/docs/plans/m1-implementation.md — M1 plan (30/30 tasks complete)
- nexus/docs/plans/m2-wave-a-implementation.md — M2 Wave A plan (19/19 tasks complete)
- nexus/docs/vision/milestones.md — M1-M6 milestone plan
- nexus/docs/architecture/overview.md — supervision tree, message flows
- nexus/config.yaml — live config (gitignored)
- nexus/.env — credentials (gitignored)
- nexus/.env.template — credential scaffolding

IMPORTANT DECISIONS
-------------------
- AgentGateway (Rust sidecar) replaces custom ModelRouter — ConversationManager → httpx → localhost:4000
- Official `mcp` Python SDK for MCP clients (not Civitas fabrica, not custom)
- No ModelRouter agent — model_for_task() on LLMClient, AgentGateway handles failover
- taylorwilsdon/google_workspace_mcp built from source (no pre-built Docker image)
- Minimal governance for Wave A: write→prompt, read→auto, JSONL audit. Trust scores in Wave B
- Generic skill system: SKILL.md files, not hardcoded logic
- HTML parse mode for Telegram (not Markdown V1/V2) with markdown→HTML conversion
- Wave B to include content viewer (/view/<id>) alongside dashboard — rich HTML for long responses, Telegram gets TL;DR + link
- Code vs Skill boundary: deterministic transforms = code, judgment-requiring procedures = skills

EXPLICIT CONSTRAINTS
--------------------
- "no code is complete without test code"
- All imports at module level (no function-level imports unless circular dependency escape)
- Functions under 50 statements, cyclomatic complexity under 12
- Pre-commit hooks enforced: ruff (17 rule sets), mypy strict, gitleaks
- PEP8 naming, no print() in source, contextlib.suppress over try/except/pass
- "DO NOT Push to remote yet" (user hasn't requested push)

CIVITAS API SIGNATURES (VERIFIED)
---------------------------------
- AgentProcess: on_start(), handle(message) -> Message | None, on_error(), on_stop()
- Messaging: send(), ask(), broadcast(), reply() (NOT async)
- GenServer: init(), handle_call(payload, from_) -> dict, handle_cast(payload), handle_info(payload), send_after(delay_ms, payload)
- Supervisor(name, children, strategy, max_restarts, restart_window, backoff)
- Runtime(supervisor, transport, model_provider, tool_registry, state_store)
- GenServer: self.llm and self.tools are explicitly None — no LLM injection

DOCKER SERVICES
---------------
- agentgateway: cr.agentgateway.dev/agentgateway:latest, port 4000 + 15000
- mcp-google: built from github.com/taylorwilsdon/google_workspace_mcp, port 8000, profile: google
- nexus: built from Dockerfile, profile: full (for containerized deployment)
