# M6 Implementation Plan — Production: "It's ready for others to use"

> Version: 1.0
> Created: 2026-05-11
> Status: Review
> Depends on: M4 complete

---

## Scope

M6 hardens Nexus for production use and community adoption. Security first, then infrastructure, then documentation.

| Phase | What ships |
|---|---|
| **1. Security Audit** | Prompt injection defense, credential review, dependency audit, SSRF hardening |
| **2. Production Hardening** | Rate limiting, webhook mode, structured logging, health checks, graceful shutdown |
| **3. Governance Hardening** | YAML policy engine, signed audit entries, credential scoping |
| **4. Documentation** | Quickstart, extension guide, integration guide, transport guide, demo script, API docs |

## Key Decisions

| # | Decision | Rationale |
|---|---|---|
| 1 | Harden existing governance (not wait for Presidium) | Presidium timeline uncertain. Our PolicyEngine works. Make it production-grade. |
| 2 | Full hardening pass (all 7 items) | OSS project needs to be secure, observable, and resilient before promotion. |
| 3 | Full documentation (all 6 items) | Community adoption requires comprehensive docs. Extensions need a dev guide. |
| 4 | Security first | Audit before promoting. Fix before documenting. |

---

## Task Breakdown

### Phase 1: Security Audit

#### T6.1.1 — Prompt injection defense
- [ ] System prompt isolation: user input never interpreted as system instructions
- [ ] Input sanitization: strip control characters, limit message length
- [ ] Tool call validation: verify tool names match registered tools, arguments match schema
- [ ] Output filtering: prevent LLM from leaking system prompt content
- [ ] Test: craft adversarial inputs, verify no prompt leakage or unauthorized tool calls
- **Tests:**
  - [ ] "Ignore previous instructions" → no behavior change
  - [ ] Extremely long input → truncated gracefully
  - [ ] Tool name injection → rejected

#### T6.1.2 — Credential handling review
- [ ] Verify no credentials in logs (audit log redacts, but check all logger calls)
- [ ] Verify .env and config.yaml in .gitignore (already done ✅)
- [ ] Verify no hardcoded secrets in source (already audited ✅)
- [ ] API keys in memory: verify they're not serialized in session checkpoints
- [ ] Review Docker credential handling (env vars, not bind-mounted files)
- **Tests:**
  - [ ] Session checkpoint does not contain API keys
  - [ ] Audit log does not contain credential values

#### T6.1.3 — Dependency security audit
- [ ] Run `pip-audit` against all dependencies
- [ ] Check for known CVEs in current versions
- [ ] Verify no typosquatting risk (all well-known packages)
- [ ] Add `pip-audit` to CI pipeline
- [ ] Document dependency provenance in SECURITY.md
- **Tests:**
  - [ ] pip-audit returns no critical vulnerabilities

#### T6.1.4 — SSRF hardening review
- [ ] Review all outbound HTTP calls (httpx, MCP, AgentGateway)
- [ ] Verify private IP blocking in PolicyEngine (already done ✅)
- [ ] Add DNS rebinding protection (resolve hostname, check IP before connecting)
- [ ] Review content viewer: verify view IDs can't access arbitrary files (already validated ✅)
- **Tests:**
  - [ ] Navigation to 127.0.0.1 → blocked
  - [ ] DNS rebinding attempt → blocked

### Phase 2: Production Hardening

#### T6.2.1 — Rate limiting
- [ ] Per-tenant rate limiter (configurable requests per minute)
- [ ] Rate limit in ConversationManager before processing
- [ ] Reject with clear message: "Rate limited. Try again in N seconds."
- [ ] Config: `rate_limit.requests_per_minute` (default: 30)
- **Tests:**
  - [ ] Burst of requests → rate limited after threshold
  - [ ] Different tenants → independent limits

#### T6.2.2 — Webhook mode for Telegram
- [ ] Alternative to polling: Telegram sends updates to a webhook URL
- [ ] Config: `telegram.mode: webhook` (default: polling)
- [ ] Webhook handler in HTTPGateway or standalone
- [ ] SSL required for webhooks (document self-signed cert option)
- **Tests:**
  - [ ] Webhook receives update → processes correctly

#### T6.2.3 — Structured JSON logging
- [ ] Replace `logging.basicConfig` with structured JSON formatter
- [ ] Log format: `{"timestamp", "level", "logger", "message", "context"}`
- [ ] Context fields: tenant_id, session_id, agent_name (where available)
- [ ] Config: `logging.format: json` (default: text for dev, json for production)
- [ ] Log rotation: configurable max size and backup count
- **Tests:**
  - [ ] JSON log output is valid JSON per line
  - [ ] Context fields present in structured logs

#### T6.2.4 — Health checks
- [ ] `/healthz` endpoint on dashboard gateway (already has `/api/health`)
- [ ] Kubernetes-compatible: returns 200 when healthy, 503 when degraded
- [ ] Readiness vs liveness: `/readyz` (all agents running) vs `/healthz` (process alive)
- [ ] Docker HEALTHCHECK uses `/healthz` instead of Python import
- **Tests:**
  - [ ] /healthz returns 200 when all agents running
  - [ ] /healthz returns 503 when agent crashed

#### T6.2.5 — Graceful shutdown improvements
- [ ] On SIGTERM: drain active conversations (finish current LLM call, don't start new)
- [ ] Checkpoint all active sessions before stopping agents
- [ ] Close MCP connections cleanly
- [ ] Timeout: force stop after 30 seconds
- [ ] Already partially done (Ctrl+C works ✅)
- **Tests:**
  - [ ] Shutdown preserves active session state
  - [ ] MCP connections closed without errors

### Phase 3: Governance Hardening

#### T6.3.1 — YAML policy configuration
- [ ] Replace hardcoded read/write prefixes with configurable YAML rules
- [ ] Policy file: `policies.yaml` or inline in `config.yaml`
- [ ] Rule format: `{pattern: "send_*", decision: REQUIRE_APPROVAL, trust_override: true}`
- [ ] Support: exact match, glob patterns, regex
- [ ] Hot reload: policy changes without restart
- **Tests:**
  - [ ] Custom policy rule applied correctly
  - [ ] Default rules work when no custom policy

#### T6.3.2 — Signed audit entries
- [ ] HMAC signature on each audit entry (prevents tampering)
- [ ] Signing key from config or auto-generated
- [ ] Verification: `nexus audit verify` CLI command
- **Tests:**
  - [ ] Audit entry has valid signature
  - [ ] Tampered entry detected by verify

#### T6.3.3 — Credential scoping
- [ ] Per-extension credential isolation
- [ ] Extensions can only access credentials they declared in extension.yaml
- [ ] Nexus core credentials not accessible to extensions
- **Tests:**
  - [ ] Extension cannot access undeclared credentials

### Phase 4: Documentation

#### T6.4.1 — Quickstart guide
- [ ] `docs/guides/quickstart.md` — step-by-step with commands
- [ ] Prerequisites checklist
- [ ] Clone → install → configure → run → first message (< 15 min)
- [ ] Troubleshooting section (common errors)

#### T6.4.2 — Extension development guide
- [ ] `docs/guides/extensions.md` — how to build a nexus extension
- [ ] Skill-only extension tutorial (5 min)
- [ ] Code extension tutorial (30 min)
- [ ] NexusContext API reference
- [ ] Testing extensions
- [ ] Publishing to PyPI

#### T6.4.3 — Adding integrations guide
- [ ] `docs/guides/integrations.md` — how to add a new MCP sidecar
- [ ] Find/evaluate an MCP server
- [ ] Docker compose configuration
- [ ] Config.yaml MCP entry
- [ ] Intent patterns (optional)
- [ ] Testing the integration

#### T6.4.4 — Adding transports guide
- [ ] `docs/guides/transports.md` — how to add a new messaging platform
- [ ] BaseTransport protocol implementation
- [ ] Message handler patterns
- [ ] Tenant resolution
- [ ] Testing

#### T6.4.5 — Demo script
- [ ] `docs/guides/demo.md` — scripted walkthrough for presentations
- [ ] Scenarios: crash recovery, trust arc, cross-transport, meeting prep, voice input
- [ ] Expected outputs at each step

#### T6.4.6 — API documentation
- [ ] mkdocs or Sphinx setup
- [ ] Auto-generated from docstrings
- [ ] Hosted on GitHub Pages or ReadTheDocs
- [ ] Covers: config models, extension API, transport protocol

#### T6.4.7 — SECURITY.md
- [ ] Security policy: how to report vulnerabilities
- [ ] Supported versions
- [ ] Dependency provenance
- [ ] Threat model summary

---

## Build Order

```
T6.1.1 Prompt injection ──── T6.1.2 Credential review
    │                              │
    └── T6.1.3 Dependency audit ───┘
              │
              └── T6.1.4 SSRF review
                        │
T6.2.1 Rate limiting ── T6.2.2 Webhook ── T6.2.3 Logging
    │                                           │
    └── T6.2.4 Health checks ── T6.2.5 Shutdown
                                    │
T6.3.1 YAML policies ── T6.3.2 Signed audit ── T6.3.3 Credential scoping
                                                    │
T6.4.1 Quickstart ── T6.4.2 Extensions ── T6.4.3 Integrations
    │
    ├── T6.4.4 Transports ── T6.4.5 Demo ── T6.4.6 API docs
    │
    └── T6.4.7 SECURITY.md
```

---

## Progress Tracking

| Phase | Task | Status | Notes |
|---|---|---|---|
| 1 | T6.1.1 Prompt injection | ⬜ Not started | |
| 1 | T6.1.2 Credential review | ⬜ Not started | |
| 1 | T6.1.3 Dependency audit | ⬜ Not started | |
| 1 | T6.1.4 SSRF review | ⬜ Not started | |
| 2 | T6.2.1 Rate limiting | ⬜ Not started | |
| 2 | T6.2.2 Webhook mode | ⬜ Not started | |
| 2 | T6.2.3 Structured logging | ⬜ Not started | |
| 2 | T6.2.4 Health checks | ⬜ Not started | |
| 2 | T6.2.5 Graceful shutdown | ⬜ Not started | |
| 3 | T6.3.1 YAML policies | ⬜ Not started | |
| 3 | T6.3.2 Signed audit | ⬜ Not started | |
| 3 | T6.3.3 Credential scoping | ⬜ Not started | |
| 4 | T6.4.1 Quickstart | ⬜ Not started | |
| 4 | T6.4.2 Extension guide | ⬜ Not started | |
| 4 | T6.4.3 Integration guide | ⬜ Not started | |
| 4 | T6.4.4 Transport guide | ⬜ Not started | |
| 4 | T6.4.5 Demo script | ⬜ Not started | |
| 4 | T6.4.6 API docs | ⬜ Not started | |
| 4 | T6.4.7 SECURITY.md | ⬜ Not started | |
