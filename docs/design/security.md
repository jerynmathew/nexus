# Security Audit: Nexus

> Status: Completed — 2026-05-13
> Scope: Prompt injection defense, credential handling, transport security

---

## Prompt Injection Defense

### System Prompt Isolation

ConversationManager's `_llm_respond()` constructs messages with clear role separation:
- System prompt (persona + user context) is always `role: "system"`
- User input is always `role: "user"`
- Tool results are always `role: "tool"`

The LLM provider (AgentGateway) handles role-based message formatting per model.

### Mitigations Implemented

1. **Input sanitization**: transport handlers escape user input before processing. Telegram transport uses `html.escape()` for outbound messages.
2. **Tool call governance**: every MCP tool call goes through `PolicyEngine.evaluate()` before execution. High-risk tools require explicit user approval via transport inline buttons.
3. **Trust-gated autonomy**: actions that modify state require trust > 0.8 for autonomous execution. New tenants start at 0.5 (approval required).
4. **Audit trail**: all tool calls, policy decisions, and trust score changes are logged to `data/audit.jsonl`.
5. **Hardline blocklist**: destructive patterns (`rm -rf /`, fork bombs, `dd` to block devices) are always denied, no override possible.

### Remaining Risks

- **Indirect injection**: malicious content in emails/documents could influence LLM behavior. Mitigated by tool governance (LLM can't execute high-risk actions without approval).
- **Context window poisoning**: very long inputs could push system prompt out of context. Mitigated by ContextCompressor (M2.6).

---

## Credential Handling

### Secrets Never in Config Files

| Secret | Storage | Access |
|---|---|---|
| API keys (LLM, MCP) | Environment variables (`${ENV_VAR}`) | Config loader substitutes at startup |
| Telegram bot token | Environment variable | Passed to transport constructor |
| Zerodha API key/secret | Environment variable | Passed to container via docker-compose |
| OAuth tokens | Nexus DB (encrypted column planned) | Per-tenant, never logged |
| Audit trail | JSONL file | Append-only, no secrets logged |

### Container Isolation

Per AGENTS.md decision #15, all external tools run in Docker containers with:
- Scoped credentials (only the env vars they need)
- Network isolation (nexus-net only)
- Read-only rootfs (`read_only: true`)
- Non-root user
- No host process spawning

### Audit Trail Security

- `AuditSink` writes JSONL entries with: agent, action, policy decision, timestamp
- Sensitive fields (API keys, tokens) are never included in audit entries
- `GovernanceConfig.audit_path` defaults to `data/audit.jsonl`

---

## Transport Security

### Telegram

- Tenant resolution: only `allowed_user_ids` can interact
- Unknown users get "not authorized" response
- Bot token validated at startup
- Webhook mode (M6.2): requires HTTPS URL, bot token as URL path

### Discord / Slack

- Same tenant resolution pattern
- DM + mention-only response (doesn't respond in public channels unless mentioned)
- Bot tokens via environment variables

### Web Dashboard

- No authentication on dashboard endpoints (assumes LAN/Tailscale access)
- ContentStore views expire after configurable TTL (default 24h)
- View IDs are random hex — no sequential enumeration

---

## Rate Limiting

- `RateLimiter` in ConversationManager: sliding window per tenant (30 req/60s default)
- Prevents abuse from any single tenant
- Remaining quota visible in rate limit rejection message

---

## Recommendations for Production Deployment

1. **Run behind reverse proxy** (Caddy/nginx) with HTTPS termination
2. **Use webhook mode** for Telegram (avoids polling overhead, requires HTTPS)
3. **Enable JSON logging** (`NEXUS_JSON_LOGS=true`) for log aggregation
4. **Restrict dashboard access** via network policy or reverse proxy auth
5. **Rotate API keys** periodically — Zerodha tokens expire daily, LLM keys should rotate monthly
6. **Monitor audit trail** for policy violations and trust score anomalies
