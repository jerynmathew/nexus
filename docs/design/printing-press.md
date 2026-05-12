# Design: Printing Press Integration

> Status: Draft — integration strategy for Printing Press CLI ecosystem
> Priority: High — unlocks finance, work intelligence, and utility integrations with zero Nexus code changes
> Depends on: MCPManager (M2), governance (M2), intent-based tool filtering (M2)
>
> **Design principle:** Security, safety, and governance are foundational — not afterthoughts. Every external tool runs in a sandboxed container with scoped credentials and full audit trail. This is the same philosophy as Presidium governance (AGENTS.md decision #10: "designed in from day one, not bolted on").

---

## What Is Printing Press?

[Printing Press](https://printingpress.dev) is an open-source project that generates Go CLI tools and MCP servers from API specifications. Each API produces **two binaries**: `<api>-pp-cli` (command-line interface) and `<api>-pp-mcp` (MCP server, stdio transport).

| Component | Repository | Stars |
|---|---|---|
| CLI generator | [cli-printing-press](https://github.com/mvanhorn/cli-printing-press) | ~1.6K |
| API spec catalog | [printing-press-library](https://github.com/mvanhorn/printing-press-library) | ~920 |

**Key properties:**
- 82 production CLIs available, each wrapping a real-world API
- Dual binary: `<api>-pp-cli` for shell use, `<api>-pp-mcp` for MCP server (stdio)
- Install: `npx -y @mvanhorn/printing-press install <name>`
- Go binaries — fast, self-contained, no runtime dependencies
- Each MCP server includes local SQLite data layer (sync, search, sql operations)
- Community-maintained API specs, auto-generated code with full test coverage

---

## Why This Matters for Nexus

Printing Press solves a supply problem. Building or finding MCP servers for every service is slow. Printing Press provides **82 ready-made MCP servers** covering finance, project management, travel, weather, sports, food, and more.

### Zero Code Changes Required

Nexus's existing architecture already handles this:

```
Printing Press CLI (Go binary, inside Docker container)
    ↓ sandboxed by
Docker (non-root, read-only rootfs, scoped credentials, network isolation)
    ↓ exposed via
HTTP transport (stdio-to-HTTP bridge inside container)
    ↓ connects via
MCPManager (auto-discovers tools, same as any MCP sidecar)
    ↓ governed by
PolicyEngine (trust scores, approval flow, audit trail)
    ↓ filtered by
IntentClassifier (tool groups, token savings)
    ↓ called by
ConversationManager (tool-use loop)
```

MCPManager connects to MCP servers over HTTP. A containerized PP CLI is just another MCP sidecar — identical to how Google Workspace MCP, web search, and Playwright already run. The sandbox, governance, trust, intent filtering, and tool-use loop all apply automatically.

**Integration effort: Dockerfile + docker-compose entry + config.yaml entry. No Nexus code changes.**

---

## Available CLIs (Relevant to Nexus)

### Tier 1: Immediate Value

CLIs that directly serve existing Nexus use cases or planned extensions.

| CLI | MCP Binary | API | Nexus Use Case | Extension |
|---|---|---|---|---|
| `yahoo-finance` | `yahoo-finance-pp-mcp` | Yahoo Finance | Gold/stock prices, historical data, watchlists | nexus-finance |
| `linear` | `linear-pp-mcp` | Linear | Issue tracking, sprint status, assignments (~28 tools) | nexus-work |
| `jira` | *(CLI only, no MCP yet)* | Jira | Issue tracking (alternative to Linear) | nexus-work |
| `slack` | `slack-pp-mcp` | Slack | Channel history, user lookup, message search | nexus-work |
| `notion` | `notion-pp-mcp` | Notion | Docs, databases, knowledge base | nexus-work |
| `figma` | `figma-pp-mcp` | Figma | Design files, comments, components | nexus-work |

### Tier 2: Personal Utility

CLIs that add personal assistant capabilities.

| CLI | MCP Binary | Nexus Use Case |
|---|---|---|
| `weather-goat` | `weather-goat-pp-mcp` | "What's the weather in Bangalore?" |
| `flight-goat` | `flight-goat-pp-mcp` | Flight tracking, price alerts |
| `espn` | `espn-pp-mcp` | Sports scores, schedules |
| `recipe` | `recipe-pp-mcp` | Meal planning, cooking |
| `airbnb` | `airbnb-pp-mcp` | Travel planning |
| `imdb` | `imdb-pp-mcp` | Movie/show recommendations |

### Tier 3: Infrastructure

CLIs that could enhance Nexus's own operations.

| CLI | MCP Binary | Nexus Use Case |
|---|---|---|
| `github` | `github-pp-mcp` | PR tracking, issue management (complement to GitHub MCP) |
| `docker` | `docker-pp-mcp` | Container management for homelab |
| `cloudflare` | `cloudflare-pp-mcp` | DNS, tunnel management |

---

## Integration Architecture

### Sandbox-First Principle

**Every external tool runs in a Docker container.** No exceptions, no "optional for production."

This is not a deployment convenience — it is a security boundary. Printing Press CLIs are community-maintained, auto-generated Go binaries that call external APIs. Running them as bare host processes would give them:
- Full filesystem access (config files, credentials, user data)
- Network access to internal services (database, AgentGateway, other MCP servers)
- Ability to read environment variables containing secrets

Containerization provides **defense in depth** alongside Presidium governance:

| Layer | What it prevents |
|---|---|
| **Container sandbox** | Filesystem access, network lateral movement, host escape |
| **Scoped credentials** | Only the API keys the tool needs, nothing else |
| **Network isolation** | Container only reaches its target API, not internal services |
| **PolicyEngine** | Every tool call evaluated against policy before execution |
| **TrustStore** | Per-tool-category trust scores gate autonomous vs approval-required |
| **Audit trail** | Every tool call logged to JSONL sink for forensic review |

Governance without isolation is incomplete. Isolation without governance is blind. Nexus requires both.

### How a Printing Press CLI Becomes a Nexus Tool

```
1. Build container image:
   $ docker build -f docker/pp-yahoo-finance.Dockerfile -t pp-yahoo-finance .

2. Add to docker-compose.yaml:
   pp-yahoo-finance:
     image: pp-yahoo-finance
     environment:
       - YAHOO_API_KEY=${YAHOO_API_KEY}
     networks: [nexus-net]
     profiles: [finance]
     restart: unless-stopped

3. Configure in config.yaml:
   mcp:
     servers:
       - name: yahoo-finance
         transport: streamable-http
         url: "http://pp-yahoo-finance:8080/mcp"
         tool_group: finance
         enabled: true

4. MCPManager auto-connects on startup:
   → Discovers tools: get_quote, get_historical, search_symbols, ...
   → Registers in tool registry with tool_group "finance"
   → Available to ConversationManager

5. User asks: "What's the gold price?"
   → IntentClassifier: tool_groups=["finance"]
   → MCPManager returns yahoo-finance tools
   → PolicyEngine.evaluate() → approved (trust 0.7, read-only)
   → LLM calls get_quote(symbol="GC=F")
   → Audit sink logs the call
   → Result rendered to user
```

### Container Image Pattern

Each PP CLI gets a minimal container image. Multi-stage build keeps the image small (~20MB):

```dockerfile
# docker/pp-yahoo-finance.Dockerfile
FROM node:20-slim AS builder
RUN npx -y @mvanhorn/printing-press install yahoo-finance

FROM debian:bookworm-slim
RUN useradd --system --no-create-home ppuser
COPY --from=builder /root/.printing-press/bin/yahoo-finance-pp-mcp /usr/local/bin/
USER ppuser
ENTRYPOINT ["yahoo-finance-pp-mcp"]
```

**Security hardening:**
- Non-root user (`ppuser`) inside the container
- No shell, no package manager in the final stage
- Read-only root filesystem (via `read_only: true` in compose)
- Only the MCP binary, nothing else

### Docker Compose Layout

```yaml
# docker-compose.yaml (additions)
services:
  pp-yahoo-finance:
    build:
      context: .
      dockerfile: docker/pp-yahoo-finance.Dockerfile
    container_name: pp-yahoo-finance
    restart: unless-stopped
    read_only: true
    environment:
      - YAHOO_API_KEY=${YAHOO_API_KEY}
    networks:
      - nexus-net
    profiles:
      - finance

  pp-linear:
    build:
      context: .
      dockerfile: docker/pp-linear.Dockerfile
    container_name: pp-linear
    restart: unless-stopped
    read_only: true
    environment:
      - LINEAR_API_KEY=${LINEAR_API_KEY}
    networks:
      - nexus-net
    profiles:
      - work

  pp-weather-goat:
    build:
      context: .
      dockerfile: docker/pp-weather-goat.Dockerfile
    container_name: pp-weather-goat
    restart: unless-stopped
    read_only: true
    networks:
      - nexus-net
    profiles:
      - utility
```

### Config Schema

PP MCP servers are configured identically to all other MCP servers — as HTTP sidecars:

```yaml
# config.yaml
mcp:
  servers:
    # Google Workspace (existing Docker sidecar)
    - name: google
      transport: streamable-http
      url: "http://mcp-google:8000/mcp"
      tool_group: google
      enabled: true

    # Printing Press MCP servers (Docker sidecars, same pattern)
    - name: yahoo-finance
      transport: streamable-http
      url: "http://pp-yahoo-finance:8080/mcp"
      tool_group: finance
      enabled: true

    - name: linear
      transport: streamable-http
      url: "http://pp-linear:8080/mcp"
      tool_group: work
      enabled: true

    - name: weather
      transport: streamable-http
      url: "http://pp-weather-goat:8080/mcp"
      tool_group: utility
      enabled: true
```

> **Note:** PP MCP binaries natively support stdio transport. Inside the container, they run as stdio processes. The container exposes them as HTTP endpoints to the Docker network. If a PP CLI doesn't natively serve HTTP, a thin stdio-to-HTTP bridge (e.g., `supergateway` or `mcp-proxy`) wraps it. This keeps the security boundary clean: Nexus never spawns external processes on the host.

### Multi-CLI Container (Alternative)

For simpler setups, a single container can bundle multiple PP CLIs behind separate ports or a multiplexing proxy:

```dockerfile
# docker/pp-bundle.Dockerfile
FROM node:20-slim AS builder
RUN npx -y @mvanhorn/printing-press install yahoo-finance weather-goat espn

FROM debian:bookworm-slim
RUN useradd --system --no-create-home ppuser
COPY --from=builder /root/.printing-press/bin/*-pp-mcp /usr/local/bin/
USER ppuser
# Supervisor or entrypoint script runs each MCP on a different port
```

Trade-off: simpler to manage, but a vulnerability in one CLI affects the bundle. Prefer per-CLI containers for Tier 1 (finance, work) and bundles for Tier 2 (utility, entertainment).

---

## Security & Governance

Security and governance are not a section bolted onto this design — they are the reason the architecture looks the way it does. Every decision above (container isolation, scoped credentials, HTTP-only transport) exists because external tools are untrusted code calling external APIs on behalf of the user.

### Defense in Depth

Three independent layers, each sufficient to prevent a class of harm:

```
Layer 1: Container Sandbox (infrastructure)
├── Filesystem isolation — no access to host config, credentials, user data
├── Network isolation — container only reaches its target API + nexus-net
├── Read-only rootfs — no persistent modifications inside container
├── Non-root user — limits container-escape impact
└── No host process spawning — Nexus never executes external binaries on host

Layer 2: Presidium Governance (application)
├── PolicyEngine — every tool call evaluated against policy before execution
├── TrustStore — per-tool-category trust scores gate autonomy
├── Approval flow — write operations require user confirmation
├── SSRF protection — URL arguments validated against allowlists
└── Credential scoping — each container gets only its required API keys

Layer 3: Audit & Observability (forensic)
├── JSONL audit sink — every tool call logged with arguments and result
├── OTEL metrics — call latency, error rates, token usage per tool
├── Dashboard — real-time tool health, trust scores, recent activity
└── Retention — audit logs retained for configurable period
```

A compromised PP CLI inside its container cannot read Nexus credentials (Layer 1), cannot execute unapproved actions (Layer 2), and its activity is fully recorded (Layer 3).

### Trust Bootstrapping

New PP tools start with conservative trust. Trust is earned through observed behavior, never assumed:

| Tool category | Initial trust | Behavior | Rationale |
|---|---|---|---|
| Read-only data (quotes, weather, sports) | 0.7 | Autonomous after first few uses | Low risk — returns public data |
| Search/lookup (Linear issues, Jira search) | 0.6 | Autonomous after pattern established | Medium risk — accesses private work data |
| Write operations (send message, create issue) | 0.3 | Requires user approval initially | High risk — takes actions on user's behalf |
| Credential-bearing operations | 0.2 | Always requires approval | Critical risk — uses API keys to mutate external state |

### Credential Scoping

Each PP container receives **only** the API keys it needs. No container has access to another container's credentials or to Nexus's own secrets:

```yaml
# .env — centralized secret storage
YAHOO_API_KEY=...
LINEAR_API_KEY=...
SLACK_BOT_TOKEN=...
ANTHROPIC_API_KEY=...       # Nexus-only, never exposed to PP containers

# docker-compose.yaml — each container gets only its key
pp-yahoo-finance:
  environment:
    - YAHOO_API_KEY=${YAHOO_API_KEY}
    # Cannot see LINEAR_API_KEY, SLACK_BOT_TOKEN, ANTHROPIC_API_KEY

pp-linear:
  environment:
    - LINEAR_API_KEY=${LINEAR_API_KEY}
    # Cannot see YAHOO_API_KEY, SLACK_BOT_TOKEN, ANTHROPIC_API_KEY
```

This is not optional hardening — it is the default configuration. A PP CLI that doesn't need an API key gets no environment variables at all.

---

## Compound Queries: Local Data Mirroring

The real power emerges when PP tools feed data into local storage for compound queries.

### Pattern: Fetch → Store → Query

```
1. Scheduler fetches gold prices every hour via pp-yahoo-finance
2. Prices stored in SQLite (work_signals or dedicated finance table)
3. User asks "Gold trend this week" → local query, no API call
4. User asks "Should I buy gold?" → local data + web search + LLM synthesis
```

### Why Local Mirrors Matter

| Without local mirror | With local mirror |
|---|---|
| Every query = API call | Most queries = local SQLite (50ms) |
| Rate limited (Yahoo: 100/day free) | Unlimited local queries |
| No cross-source correlation | JOIN gold prices with news sentiment |
| No historical trend without API support | Full history in local DB |

### Implementation Path

1. **Phase 1**: Direct tool calls (PP CLI → MCP → LLM response). Works immediately.
2. **Phase 2**: Scheduler-driven data collection into `work_signals` table. Enables compound queries.
3. **Phase 3**: Extension-specific tables (e.g., `finance_prices`) with materialized views for dashboards.

This is **not** a Printing Press concern — it's the normal Nexus data flow. PP CLIs are just another source.

---

## Rollout Strategy

### Phase 1: Validation (1-2 CLIs)

Build container images for `yahoo-finance` and `weather-goat`. Verify:
- Container builds successfully, runs as non-root, read-only rootfs
- Stdio-to-HTTP bridge works inside container
- MCPManager connects via HTTP, discovers tools
- Tool discovery populates tool registry
- Intent filtering routes correctly
- Governance applies: trust scores, policy check, audit logging
- Credential scoping: container only sees its own API key
- End-to-end: "What's the gold price?" returns a real answer through the full stack

**Exit criteria:** Two PP CLIs working end-to-end in containers with full governance and audit trail.

### Phase 2: Work Intelligence CLIs

Install `linear` (has full MCP server). Integrate with nexus-work extension:
- Issue tracking tools (~28 tools including sync, search, sql) available to work-morning-briefing skill
- Cross-signal queries: "What's Sarah working on?" resolves across Slack + Linear
- Action items from Linear surface in `/actions` command
- Jira: CLI-only for now (no MCP binary yet). Monitor for MCP support in future releases.

### Phase 3: Broad Catalog

Install remaining Tier 1 and Tier 2 CLIs based on user needs. Each is config-only.

### Phase 4: Community Extensions

Document PP CLI integration pattern so community can add their own. Extension authors specify PP CLIs in `extension.yaml`:

```yaml
# nexus-finance/extension.yaml
printing_press:
  - yahoo-finance
  - crypto             # if/when available
```

Extension loader installs PP CLIs during `on_load()`.

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| **Malicious or compromised CLI** | Data exfiltration, credential theft | Container sandbox (no host access), scoped credentials (only its own API key), network isolation, audit trail. Defense in depth — no single layer failure is fatal. |
| **PP CLI quality varies** | Bad API mapping → wrong data | Validate Tier 1 CLIs before depending on them. Fall back to dedicated MCP servers for critical paths. |
| **Supply chain attack** (compromised npm/Go binary) | Trojanized CLI in container | Pin image digests, build from source in CI, scan images. Container limits blast radius even if binary is compromised. |
| **PP project abandoned** | No updates, broken APIs | CLIs are self-contained Go binaries. Pin versions. Worst case: fork and maintain. |
| **API key leakage** | Credential exposed in logs or error messages | Scoped credentials per container. Audit sink redacts sensitive values. API keys never in config.yaml — always `${ENV_VAR}` references. |
| **Rate limits** | Free tiers are limited | Local data mirroring (Phase 2) reduces API calls 10-50x. |
| **Container overhead** | Memory/CPU per container | Minimal Go binaries (~20MB image). Profiles control which containers start. Tier 2/3 can share a bundle container. |

---

## Relationship to Existing Architecture

| Component | Role |
|---|---|
| **Docker** | Sandbox boundary — every PP CLI runs in its own container with scoped credentials |
| **MCPManager** | Connects to PP containers via HTTP, discovers tools |
| **PolicyEngine** | Governs PP tool calls identically to all other tools |
| **TrustStore** | Per-tool-category trust for PP tools, conservative defaults |
| **IntentClassifier** | Routes to PP tool groups (finance, work, utility) |
| **Audit sink** | Every PP tool call logged with arguments and results |
| **SchedulerAgent** | Periodic data collection from PP containers into local storage |
| **MemoryAgent** | Stores mirrored data for compound queries |
| **Extension system** | Extensions can declare PP CLI dependencies |
| **config.yaml** | PP containers configured alongside other MCP servers |

**No new components needed.** Printing Press is a supply-side solution — more tools available to the existing architecture. The security model (container sandbox + Presidium governance + audit) applies uniformly without special cases.

---

## Open Questions

1. **Stdio-to-HTTP bridge**: PP CLIs natively speak stdio MCP. Inside the container, we need a bridge to expose HTTP. Options: `supergateway`, `mcp-proxy`, or a custom entrypoint script. Which is lightest and most reliable?
2. **Multi-CLI container vs per-CLI**: Per-CLI containers are more secure (blast radius isolation) but use more resources. Recommendation: per-CLI for Tier 1 (finance, work), bundled for Tier 2/3 (utility, entertainment). Confirm this trade-off.
3. **CLI version pinning**: How to pin PP CLI versions in Dockerfiles? `npx` always gets latest. Need a lockfile, version argument, or pinned Go binary download.
4. **API key discovery**: Some PP CLIs need API keys, others don't. How to document which keys each CLI needs? A `pp-requirements.yaml` manifest per container?
5. **Tool namespace collisions**: If `slack-pp-mcp` and the existing Slack MCP server both expose `search_messages`, which wins? MCPManager needs server-prefixed tool names or priority ordering.
6. **Image scanning**: Should PP container images be scanned in CI (e.g., Trivy, Grype) before deployment? (Recommended: yes, as part of M6 security audit.)
