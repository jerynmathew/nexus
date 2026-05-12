# Nexus

> The reliable personal AI assistant — self-hosted, crash-resilient, governed.

Built on [Civitas](https://github.com/civitas-io/python-civitas) supervision trees. Governed by policy enforcement. Runs on your homelab.

---

## What Nexus Does

Nexus is a self-hosted AI assistant that connects to your email, calendar, and services — and keeps running when things go wrong.

- **Telegram bot** with a configurable personality (Dross, Friday, or create your own)
- **Gmail, Calendar, Tasks** via MCP tool integration — "check my email", "what's on my calendar?"
- **Web search** with no API keys required
- **Morning briefing** delivered at 7am with email, calendar, and task summaries
- **Proactive heartbeat** — pings you when something needs attention, stays silent when it doesn't
- **Trust-gated governance** — write actions require approval until trust is earned
- **Web dashboard** at `:8080` with live topology, agent health, and activity feed
- **Multi-tenant, multi-persona** — different users, different personalities, different trust levels

## What Makes It Different

Every personal AI assistant shares the same weakness: when something crashes, everything stops.

Nexus runs on Civitas supervision trees. Each component is an independent supervised agent. When Gmail crashes, the supervisor restarts it with backoff — your calendar keeps running, your briefing arrives with available data, and Gmail is back before you notice.

| Feature | Nexus | Others |
|---|---|---|
| Crash recovery | Automatic (supervision trees) | Manual restart |
| Governance | Trust-gated approval for write actions | None or all-or-nothing |
| Architecture | Message-passing agents | Monolithic |
| Self-hosted | First-class | Afterthought or impossible |
| Multi-tenant | Built in from day one | Single user |

## Quick Start

### Prerequisites

- Docker and Docker Compose (all deployment modes)
- A Telegram bot token (from [@BotFather](https://t.me/BotFather))
- An Anthropic API key
- For development only: Python ≥ 3.12 + [uv](https://github.com/astral-sh/uv)

### 1. Clone and configure

```bash
git clone https://github.com/jerynmathew/nexus.git
cd nexus

cp .env.template .env
cp config.example.yaml config.yaml
```

Edit `.env` with your API keys. Edit `config.yaml` with your Telegram user ID.

### 2. Choose a deployment mode

| Mode | Nexus runs | MCP tools run | Best for |
|---|---|---|---|
| [Development](#development) | Host process (uv) | Docker containers | Hacking on Nexus itself |
| [Docker Compose](#docker-compose) | Docker container | Docker containers | Homelab, always-on |
| [Production](#production) | Docker (hardened) | Docker (hardened) | Exposed to network, multi-user |

All modes run external tools in Docker containers. Nexus never executes third-party binaries on the host — see [Security Model](#security-model).

---

## Deployment

### Development

Nexus runs on your host for fast iteration. AgentGateway and MCP servers run in containers.

```bash
uv sync --all-extras

docker compose up agentgateway -d

source .env
uv run nexus run --config config.yaml
```

Add Google Workspace (optional):

```bash
uv run nexus setup-google
docker compose --profile google up -d --build
```

Add web search (optional):

```bash
docker compose --profile search up -d --build
```

Dashboard at `http://localhost:8080`. Send a message to your Telegram bot to verify.

### Docker Compose

Everything containerized. The recommended mode for homelab deployments.

```bash
docker compose --profile full up -d --build
```

This starts Nexus + AgentGateway. Add integrations with profiles:

```bash
docker compose --profile full --profile google --profile search up -d --build
```

| Profile | Service | What it adds |
|---|---|---|
| `full` | Nexus | The assistant itself |
| `google` | mcp-google | Gmail, Calendar, Tasks via MCP |
| `search` | mcp-search | Web search (DuckDuckGo, no API key) |
| `browser` | mcp-browser | Playwright browser automation |

Config is mounted read-only from the host. Data persists in Docker volumes (`nexus-data`, `mcp-google-creds`).

### Production

Docker Compose with security hardening. Use this when Nexus is exposed to a network or serves multiple users.

```bash
docker compose --profile full --profile google --profile search up -d --build
```

**Hardening checklist:**

| Concern | Mitigation |
|---|---|
| Secrets in environment | Use Docker secrets or a `.env` file with `chmod 600`. Never commit `.env`. |
| Container permissions | All containers run as non-root (`USER nexus` / `USER ppuser`). |
| Filesystem | Mount config as read-only (`:ro`). Use `read_only: true` for MCP sidecars. |
| Network | All containers communicate over the `nexus-net` bridge. Only expose ports you need (`:8080` for dashboard, `:4000` for AgentGateway if external). |
| Credential scoping | Each MCP container receives only its own API keys. Nexus secrets (Anthropic key, bot token) are never exposed to MCP containers. |
| Audit | Governance enabled by default. All tool calls logged to `data/audit.jsonl`. |
| Updates | Pin image tags/digests. Rebuild periodically: `docker compose build --pull`. |
| TLS | Put a reverse proxy (Caddy, Traefik, nginx) in front of `:8080` for HTTPS. |

**Adding Printing Press tools** (finance, weather, project management):

Each Printing Press CLI runs as a containerized MCP sidecar. See [docs/design/printing-press.md](docs/design/printing-press.md) for container setup, and [config.example.yaml](config.example.yaml) for config examples.

```bash
docker compose --profile full --profile finance --profile work up -d --build
```

### Verifying your deployment

Regardless of mode, verify with:

```bash
docker compose ps
curl -s http://localhost:8080/api/health | python -m json.tool
```

The dashboard at `http://localhost:8080` shows the supervision tree, agent health, and trust scores.

---

## Security Model

Nexus treats security as foundational architecture, not an afterthought.

**Sandbox isolation:** Every external tool (MCP servers, Printing Press CLIs, browser automation) runs in its own Docker container with scoped credentials, network isolation, and a read-only filesystem. Nexus never spawns third-party binaries on the host.

**Governance:** All tool calls pass through the PolicyEngine before execution. Write actions require user approval until trust is earned. Every call is logged to an audit trail.

**Defense in depth:** Container sandbox (infrastructure) + Presidium governance (application) + audit trail (forensic). A compromised tool cannot access host credentials, cannot execute unapproved actions, and its activity is fully recorded.

See [Governance](#governance) for the trust model and [docs/design/integrations.md](docs/design/integrations.md) for the full security architecture.

## Architecture

![Nexus Architecture](docs/assets/readme-architecture.svg)

- **ConversationManager** handles all user-facing I/O, LLM calls, tool execution, and governance
- **MemoryAgent** persists everything to SQLite with FTS5 search
- **SchedulerAgent** runs cron-based skills (morning briefing, heartbeat)
- **DashboardServer** (GenServer) maintains live health state for the web UI
- **AgentGateway** (Rust sidecar) proxies LLM calls to Anthropic
- **MCP servers** (Docker sidecars) provide tool access to Gmail, Calendar, web search

## Dashboard

The web dashboard at `http://localhost:8080` shows:

- **Topology** — supervision tree with health dots for every agent and external service
- **Agent cards** — status, type, restart count, last active
- **Activity feed** — recent messages and tool calls
- **Trust scores** — per-category trust levels (gmail, calendar, etc.)

Embeddable in homelab dashboards (Homepage, Heimdall, Homarr) via iframe.

## Governance

Nexus doesn't blindly execute actions. It has a trust-gated governance system:

- **Read actions** (search, list, get) → auto-allowed
- **Write actions** (send, create, delete) → require approval via Telegram inline buttons
- **Trust grows** with approved actions (+0.05 per approval)
- **Trust decays** on rejection (-0.10) or policy deny (-0.15)
- **High trust** (> 0.8) → write actions become autonomous
- **Low trust** (< 0.5) → actions denied even with approval

All tool calls are audited to `data/audit.jsonl`.

## Skills

Skills are reusable procedures defined as SKILL.md files. Nexus ships with:

- **Morning briefing** — parallel email + calendar + tasks summary at 7am
- **Heartbeat** — proactive check-in every 30 minutes during active hours

Create your own by adding a SKILL.md file to the `skills/` directory:

```yaml
---
name: my-skill
description: What this skill does
execution: parallel  # or sequential
tool_groups: [google]
schedule: "0 9 * * *"  # optional cron
---

Instructions for the LLM...
```

## Personas

Nexus supports multiple personas via SOUL.md files. Create one interactively:

```bash
uv run nexus setup-persona
```

Or manually create `personas/your-persona.md`. Each user can have different personas for different profiles (work, personal).

## CLI Reference

| Command | Description |
|---|---|
| `nexus run --config config.yaml` | Start the assistant |
| `nexus setup` | First-boot setup wizard |
| `nexus setup-google` | Configure Google Workspace MCP |
| `nexus setup-persona` | Create a new persona interactively |
| `nexus personas list` | List available personas |
| `nexus personas set <name>` | Set active persona |
| `nexus version` | Print version info |

## Development

```bash
# Install with dev dependencies
uv sync --all-extras

# Run tests (~2 seconds)
OTEL_SDK_DISABLED=true uv run pytest tests/ -q

# Lint
uv run ruff check .

# Type check
uv run mypy src/nexus/

# Pre-commit hooks (installed automatically)
uv run pre-commit install
```

### Code Quality

- **Ruff** with 17 rule sets (PEP8, complexity, security, import order)
- **mypy** strict mode
- **Pre-commit hooks** — ruff, mypy, gitleaks (secret scanning), trailing whitespace
- Functions under 50 statements, complexity under 12
- All imports at module level
- 85% coverage target

## Project Structure

```
nexus/
├── src/nexus/
│   ├── agents/          # Civitas AgentProcess subclasses
│   │   ├── conversation.py  # Central routing agent
│   │   ├── memory.py        # SQLite + FTS5 persistence
│   │   ├── scheduler.py     # Cron-based skill triggers
│   │   ├── compressor.py    # Context compression
│   │   └── intent.py        # Intent classification
│   ├── llm/             # LLM client (httpx → AgentGateway)
│   ├── mcp/             # MCP server management
│   ├── transport/       # Telegram, CLI transports
│   ├── persona/         # SOUL.md / USER.md loading
│   ├── skills/          # SKILL.md parser + manager
│   ├── governance/      # Policy engine, audit, trust scores
│   ├── dashboard/       # Web dashboard + content viewer
│   ├── config.py        # Pydantic config models
│   ├── cli.py           # Typer CLI
│   └── runtime.py       # Civitas runtime wiring
├── personas/            # SOUL.md personality files
├── skills/              # SKILL.md skill definitions
├── tests/               # Unit + integration tests
├── docs/                # Architecture, design, plans
└── docker-compose.yaml  # AgentGateway + MCP sidecars
```

## Roadmap

| Milestone | Status | Description |
|---|---|---|
| M1 Foundation | ✅ Complete | Telegram bot, supervision tree, memory, crash recovery |
| M2 Integrations | ✅ Complete | MCP tools, Google Workspace, skills, governance, dashboard, compression |
| M3 Depth | ✅ Complete | Trust arc, heartbeat, web search, media (STT/vision), persona builder |
| M4 Breadth | ✅ Complete | Discord, Slack, browser automation, /status, /checkpoint, SSRF protection |
| M5 Extensions | Designed | [Extension architecture](docs/design/extensions.md) — composable plugin system |
| M5 Work Intelligence | Designed | [Work assistant](docs/design/work-assistant.md) — action tracking, delegation, meeting prep (`nexus-work` extension) |
| M6 Production | Planned | Presidium governance, production hardening, community docs |
| M7 Presence | Planned | PWA web app, Android app, animated avatar, TTS voice cloning |

## Extensions

Nexus is a platform. Domain-specific intelligence ships as extensions:

| Extension | Scope | Status |
|---|---|---|
| **nexus-work** | Action tracking, meeting prep, delegation, priority engine | [Designed](docs/design/work-assistant.md) |
| **nexus-finance** | Gold/stocks, charts, buy/sell recommendations | [Designed](docs/design/finance.md) |
| **nexus-homelab** | Service monitoring (Jellyfin, Paperless, etc.) | Planned (skills-only) |

Extensions install via `pip install nexus-work` (code + skills) or by dropping skill folders into `~/.nexus/extensions/`. See [extension architecture](docs/design/extensions.md).

## Ecosystem

Nexus is part of the [civitas-io](https://github.com/civitas-io) ecosystem:

| Repo | Role |
|---|---|
| [python-civitas](https://github.com/civitas-io/python-civitas) | Agent runtime — supervision trees, message passing, OTEL |
| [presidium](https://github.com/civitas-io/presidium) | Governance — policy enforcement, trust scores, audit |
| **nexus** | The platform — personal AI assistant with extension system |
| **nexus-work** | Extension — work intelligence for staff engineers + managers |

## License

Apache 2.0
