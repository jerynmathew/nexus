# AGENTS.md — Nexus

> Machine-readable project reference for AI coding assistants.
> Last updated: 2026-05-13

## Project Identity

**Nexus** is a self-hosted personal AI assistant built on [Civitas](https://github.com/civitas-io/python-civitas)
and governed by [Presidium](https://github.com/civitas-io/presidium).

- **Repository:** `github.com/jerynmathew/nexus`
- **Organization:** `civitas-io` (ecosystem)
- **License:** Apache 2.0
- **Python:** ≥3.12
- **Status:** Pre-alpha (documentation-first phase)

### What Nexus Is

- A self-hosted personal AI assistant for email, calendar, messages, and services
- Built natively on Civitas (supervision trees, message passing, transports, OTEL)
- Governed by Presidium (policy enforcement, trust scores, audit trail, credential scoping)
- Multi-tenant, multi-profile, multi-transport from day one
- The reference application that proves Civitas is production-ready

### What Nexus Is NOT

- NOT a framework — it's an application built on Civitas
- NOT a replacement for OpenClaw/Hermes — different architectural philosophy (reliability over breadth)
- NOT cloud-only — self-hosted first, runs on your homelab
- NOT single-user — designed for households and small teams

### Relationship to Other Repos

| Repo | Relationship |
|---|---|
| `civitas-io/python-civitas` | Runtime dependency. Nexus subclasses `AgentProcess`, uses `Supervisor`, `Runtime`, `MessageBus` |
| `civitas-io/civitas-contrib` | Plugin dependency. Model providers (Anthropic, OpenAI, LiteLLM), state stores |
| `civitas-io/presidium` | Governance dependency. Policy engine, agent registry, trust scores, credential vault |
| `civitas-io/context` | Cross-cutting context. ADRs, boundary definitions, roadmap |

**Dependency direction:** Nexus → Civitas + Presidium. Never the reverse.

---

## Conventions

### Matching Civitas Patterns

This repo follows the conventions established in `civitas-io/python-civitas`:

| Convention | Standard |
|---|---|
| Package manager | uv (Astral) |
| Build backend | hatchling |
| Python version | ≥3.12 |
| Linting | Ruff, 100 char line length |
| Rule sets | E, F, I, UP, B, ASYNC |
| Type checking | mypy strict |
| Testing | pytest + pytest-asyncio |
| Async mode | `asyncio_mode = "auto"` |
| License | Apache 2.0 |
| Package layout | `src/nexus/` |

### Code Style

- **Formatter / linter:** `ruff`. Config in `pyproject.toml`.
- **Line length:** 100.
- **Imports:** top-level only, sorted by ruff `I` rules.
- **Type hints:** required on all public functions and methods.
- **Docstrings:** Google style on all public classes and functions.
- **Private symbols:** prefix `_`.
- **Comments:** only when the WHY is non-obvious.

### Async Conventions

- All I/O-bound operations **must be async**.
- Never use `time.sleep()` — always `await asyncio.sleep()`.
- Never call `asyncio.run()` inside agents or library code.
- Use `asyncio.TaskGroup` for concurrent tasks.
- Use `aiosqlite` for database access — never synchronous `sqlite3`.
- Blocking calls: wrap with `asyncio.to_thread`.

### Testing

- **Unit tests** (`tests/unit/`): no network, no API keys. Mock LLM, mock MCP.
- **Integration tests** (`tests/integration/`): may use real APIs. Test supervision tree, crash recovery.
- Coverage target: **≥ 85%**.
- Test file names mirror source: `src/nexus/agents/memory.py` → `tests/unit/test_memory.py`.

---

## Repository Layout

```
nexus/
├── AGENTS.md                    # This file
├── README.md                    # Public-facing overview
├── CHANGELOG.md                 # Release history
├── pyproject.toml               # Dependencies, build, tool config
├── Dockerfile                   # Multi-stage, non-root
├── docker-compose.yaml          # nexus + MCP sidecars + optional Ollama
├── config.example.yaml          # Documented template
│
├── docs/
│   ├── vision/
│   │   ├── prd.md               # Product requirements
│   │   └── milestones.md        # Milestone plan with exit criteria
│   ├── architecture/
│   │   ├── overview.md          # System architecture + supervision tree
│   │   ├── multi-tenant.md      # Tenant, profile, persona model
│   │   └── memory.md            # Memory architecture (session/persistent/skill)
│   ├── design/
│   │   ├── conversation.md      # ConversationManager design
│   │   ├── persona.md           # Persona system (SOUL.md)
│   │   ├── transport.md         # Multi-transport abstraction
│   │   ├── scheduler.md         # Scheduled tasks + briefings
│   │   └── integrations.md      # MCP-first integration model
│   ├── research/
│   │   └── competitive-analysis.md
│   └── assets/                  # SVG diagrams
│
├── src/
│   └── nexus/
│       ├── __init__.py
│       ├── __main__.py          # Entry point: python -m nexus
│       ├── cli.py               # Typer CLI: nexus run, nexus setup, nexus dashboard
│       ├── config.py            # Pydantic config models + YAML loading
│       ├── extensions.py        # NexusExtension protocol, NexusContext API (MCP + DB), ExtensionLoader
│       │
│       ├── agents/
│       │   ├── conversation.py  # ConversationManager — routing, sessions, LLM, skill execution
│       │   ├── memory.py        # MemoryAgent — SQLite, facts, preferences, ext_query/ext_execute
│       │   ├── scheduler.py     # SchedulerAgent — cron tasks, triggers skills
│       │   ├── intent.py        # IntentClassifier protocol + implementations
│       │   └── dashboard.py     # DashboardServer(GenServer) — live topology + health state
│       │
│       ├── llm/
│       │   ├── __init__.py
│       │   └── client.py        # LLMClient — httpx to AgentGateway (OpenAI-compatible)
│       │
│       ├── transport/
│       │   ├── base.py          # BaseTransport protocol + InboundMessage
│       │   ├── telegram.py      # Telegram transport
│       │   ├── cli.py           # CLI transport (stdin/stdout, for dev/testing)
│       │   └── ...              # Future: Discord, Slack, SMS
│       │
│       ├── persona/
│       │   ├── loader.py        # Persona (SOUL.md) loading + injection
│       │   └── builder.py       # Conversational persona builder
│       │
│       ├── skills/
│       │   ├── manager.py       # SkillManager — load, index, search, CRUD
│       │   ├── scanner.py       # SkillScanner — web/GitHub discovery (scheduled)
│       │   └── sync.py          # Community repo sync + git export/import
│       │
│       ├── models/
│       │   ├── tenant.py        # TenantContext, permissions
│       │   ├── profile.py       # UserProfiles, WorkspaceAccount
│       │   └── session.py       # Session (multi-turn state)
│       │
│       ├── dashboard/
│       │   ├── static/          # HTML + JS + CSS for web dashboard (no build step)
│       │   └── api.py           # HTTPGateway routes for /api/* endpoints
│       │
│       └── telemetry.py         # OTEL metrics + context managers
│
├── personas/                    # Persona definitions (SOUL.md files)
│   └── default.md              # Default persona
│
├── extensions/                  # Monorepo extensions (pip-installable)
│   └── nexus-finance/
│       ├── pyproject.toml       # hatchling, entry_points for nexus.extensions
│       ├── docker/
│       │   ├── zerodha.Dockerfile   # Zerodha Kite MCP server container
│       │   └── zerodha_mcp.py       # MCP server wrapping pykiteconnect
│       ├── src/nexus_finance/
│       │   ├── extension.py     # FinanceExtension — registers commands/skills/schema/signals
│       │   ├── commands.py      # /portfolio, /fire, /rebalance, /research, /gold, /holdings
│       │   ├── portfolio.py     # Holding dataclass, sync, snapshot, formatting
│       │   ├── schema.py        # 7 SQLite tables (finance_holdings, etc.)
│       │   ├── research.py      # FIRE calculators (implemented)
│       │   ├── charts.py        # matplotlib chart generation (implemented)
│       │   ├── indicators.py    # SMA/EMA/RSI (implemented)
│       │   ├── gold.py          # goodreturns parser (implemented)
│       │   ├── parsers/         # HDFC/SBI CSV parsers (implemented)
│       │   └── skills/          # 8 SKILL.md files
│       └── tests/
│
└── tests/
    ├── unit/
    ├── integration/
    └── conftest.py
```

> This layout is authoritative. If you add or remove a module, update this section.

---

## Key Architectural Decisions

These are settled decisions. Do not revisit without discussion.

| # | Decision | Rationale |
|---|---|---|
| 1 | **MCP-prioritized integrations** | Prefer MCP servers where mature (Gmail, Calendar, Drive, web search). Fall back to custom `IntegrationAgent` where MCP coverage is insufficient. Both paths governed identically by Presidium. Learned from Vigil M1.8→M3.0 migration. |
| 2 | **Multi-tenant from day one** | Tenant abstraction on all state. Single-tenant is just config with one user. No retrofitting. |
| 3 | **Multi-transport from day one** | `BaseTransport` protocol. Telegram first, but ConversationManager never sees Telegram objects. |
| 4 | **Persona as first-class concept** | `SOUL.md` files, per-tenant persona selection, conversational builder. Not a config afterthought. |
| 5 | **aiosqlite, not sqlite3** | All database access async. Learned from Vigil issue A1. |
| 6 | **LLM calls in ConversationManager only** | Integration agents are stateless data fetchers. Single point for prompt engineering and cost control. |
| 7 | **Session state checkpointed** | Multi-turn sessions survive agent restarts via MemoryAgent. Learned from Vigil risk R2. |
| 8 | **IntentClassifier is a Protocol** | Swap regex → local LLM → hybrid without code changes. Learned from Vigil's M2.3 evolution. |
| 9 | **Config: YAML for infra, SQLite for user** | Infrastructure (bot tokens, MCP URLs) in YAML. User config (persona, preferences) in DB. Learned from Vigil M4.0. |
| 10 | **Presidium governance hooks designed in** | Policy evaluation points, trust score interfaces, audit sink wiring — all in the architecture from day one, not bolted on. |
| 11 | **Web dashboard via GenServer + HTTPGateway** | `DashboardServer(GenServer)` for thread-safe state, `HTTPGateway` for HTTP serving. Static HTML + vanilla JS, no React/Vue build step. Embeddable in homelab dashboards. |
| 12 | **AgentGateway sidecar for LLM routing** | [AgentGateway](https://github.com/agentgateway/agentgateway) (Rust single binary, ~50MB) runs as a Docker sidecar on port 4000. ConversationManager calls it directly via httpx using the OpenAI-compatible API. Provides native failover, rate limiting, cost tracking via OTEL, and MCP gateway — all without custom code. Task-based model routing (classify → cheap, converse → primary) deferred to M2 as a thin wrapper. Replaces the original ModelRouter(AgentProcess) design. |
| 13 | **FTS5 for memory search** | Zero-dependency full-text search. Sufficient for personal assistant scale. Vector search as optional extra later. |
| 14 | **Skills + MCP are the norm, custom agents are the exception** | Morning briefing, email triage, task management — all skills. Custom agents only for bespoke code (no MCP, custom rendering/UI, stateful API connections). Simplicity over infrastructure. |
| 15 | **External tools run in containers, never on host** | Every MCP server and external binary runs in a Docker container with scoped credentials, network isolation, read-only rootfs, and non-root user. Nexus never spawns external processes on the host. Container sandbox + Presidium governance + audit trail = defense in depth. Security designed in from day one, not bolted on after a breach. |

---

## Agent Anti-Patterns

Mistakes from Vigil's development. Every item here represents a real bug that was found and fixed.

### 1. Sending messages from `on_start()`

The MessageBus is not ready during `on_start()`. Use deferred initialization:

```python
# Wrong — will fail or race
async def on_start(self) -> None:
    response = await self.ask("memory", {"action": "load"})

# Correct — defer to first handle()
async def on_start(self) -> None:
    self._state_loaded = False

async def handle(self, message: Message) -> Message | None:
    if not self._state_loaded:
        await self._load_state()
        self._state_loaded = True
    ...
```

### 2. Synchronous database access

`sqlite3` blocks the event loop. Always use `aiosqlite`:

```python
# Wrong — blocks event loop
import sqlite3
conn = sqlite3.connect("data.db")
conn.execute("SELECT ...")

# Correct
import aiosqlite
async with aiosqlite.connect("data.db") as conn:
    await conn.execute("SELECT ...")
```

### 3. Bare KeyError on missing payload fields

Validate before accessing. Return structured errors, don't crash the agent:

```python
# Wrong — crashes agent on missing field
key = message.payload["key"]

# Correct — graceful validation
key = message.payload.get("key")
if not key:
    return self.reply({"error": "Missing required field: key"})
```

### 4. Hardcoded permission level

Check read vs write based on the action, not hardcoded `.read`:

```python
# Wrong
permission = f"{agent}.read"  # always .read, even for create/delete

# Correct
WRITE_ACTIONS = {"create", "send", "delete", "update", "write"}
level = "write" if action in WRITE_ACTIONS else "read"
permission = f"{agent}.{level}"
```

### 5. Busy-wait for async readiness

Use `asyncio.Event`, not polling loops:

```python
# Wrong — 30-second busy-wait
for _ in range(30):
    if self._mcp and self._mcp.tool_schemas:
        break
    await asyncio.sleep(1)

# Correct
await asyncio.wait_for(self._mcp_ready.wait(), timeout=30)
```

### 6. New HTTP session per request

Reuse `aiohttp.ClientSession` or `httpx.AsyncClient`:

```python
# Wrong — new TCP connection per request
async with aiohttp.ClientSession() as session:
    async with session.post(url) as resp: ...

# Correct — long-lived session
self._session = aiohttp.ClientSession()  # created once in on_start()
async with self._session.post(url) as resp: ...
```

### 7. Hardcoded first user for scheduled tasks

Iterate all eligible tenants, don't assume `allowed_users[0]`:

```python
# Wrong
tenant_id = str(config.telegram.allowed_users[0].telegram_user_id)

# Correct
for tenant in await self._get_admin_tenants():
    await self._execute_briefing(tenant)
```

---

## Wiki Maintenance

This project follows the [LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).

- `docs/` is a persistent, compounding knowledge base
- AI assistants own the wiki's maintenance
- Every ingest, query, and design decision gets recorded
- See presidium's `AGENTS.md § Wiki Maintenance` for the full workflow

---

## PR Checklist

- [ ] `uv run ruff check .` passes
- [ ] `uv run ruff format .` produces no diff
- [ ] `uv run mypy src/nexus/` passes
- [ ] `uv run pytest tests/unit` passes with ≥85% coverage
- [ ] Type hints on all new public functions
- [ ] Google-style docstrings on all new public classes / functions
- [ ] AGENTS.md updated if layout or conventions changed
- [ ] CHANGELOG.md updated for user-visible changes
