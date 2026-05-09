# M3 Wave A Implementation Plan — "It earns your trust"

> Version: 1.0
> Created: 2026-05-09
> Status: Review
> Depends on: M2 complete (Wave A + B)

---

## Scope

Wave A ships the trust arc, proactive intelligence, web search, and persona customization.

| Sub-milestone | What ships | Build order |
|---|---|---|
| **M3.3** Web Search | `open-websearch` MCP sidecar, search intent pattern | 1st |
| **M3.7** Proactive Heartbeat | SKILL.md with model-driven judgment, active hours | 2nd |
| **M3.2** Trust-Gated Autonomy | Per-tool-category trust scores, threshold logic, dashboard display | 3rd |
| **M3.5** Persona Builder | `nexus setup-persona` CLI | 4th |

## Key Decisions

| # | Decision | Rationale |
|---|---|---|
| 1 | Wave A/B split | Trust arc + heartbeat + search + persona first. Media + skill auto-creation + Presidium in Wave B. |
| 2 | `open-websearch` for web search | 953 stars, multi-engine (Bing/DDG/Startpage), no API keys, Docker, Apache 2.0 |
| 3 | Per-tool-category trust scores | gmail trust grows independently from calendar. Finest useful granularity. |
| 4 | Scheduler checks active hours | No LLM cost outside active hours. Zero tokens at night. |
| 5 | CLI-only persona builder | `nexus setup-persona`. Conversational rebuild deferred to Wave B. |

---

## Task Breakdown

### Phase 1: M3.3 — Web Search via MCP

> Add `open-websearch` as a Docker sidecar. "What's in the news?" works.

#### T3.3.1 — Docker compose for open-websearch
- [ ] Add `mcp-search` service to `docker-compose.yaml`
  - Image/build from `open-websearch` repo
  - MCP stdio transport via Docker exec, or HTTP mode if available
  - Profile: `search` (optional, like google profile)
  - Environment: `DEFAULT_SEARCH_ENGINE=duckduckgo`
- [ ] Update `.env.template` (no keys needed, but document the service)

#### T3.3.2 — Search intent pattern
- [ ] Add search patterns to RegexClassifier: "search for", "look up", "find", "what's in the news", "google"
- [ ] `tool_groups=["search", "web"]` for search intent
- [ ] Morning briefing SKILL.md: add optional headlines section using search tool
- **Tests:**
  - [ ] "search for flights to Tokyo" → search intent
  - [ ] "what's in the news" → search intent

#### T3.3.3 — Config + integration
- [ ] Add MCP server entry for search in `config.example.yaml`
- [ ] Verify: "search for latest news about AI" → MCP tool call → formatted results
- **Tests:**
  - [ ] Intent filtering returns search tools

**Phase 1 exit:** "What's in the news?" → web search → formatted summary on Telegram.

---

### Phase 2: M3.7 — Proactive Heartbeat

> Agent reviews context every 30 minutes and decides whether to notify. Silence is valid.

#### T3.7.1 — Heartbeat SKILL.md
- [ ] Create `skills/heartbeat/SKILL.md`:
  ```yaml
  name: heartbeat
  description: Proactive check-in — review context and decide whether to notify
  execution: sequential
  tool_groups: [google]
  schedule: "*/30 * * * *"
  ```
- [ ] Skill content instructs the LLM to:
  1. Review upcoming events (next 2 hours)
  2. Check for high-priority unread emails
  3. Check pending tasks due today
  4. Decide: is there anything actionable to tell the user?
  5. If yes → compose a brief notification
  6. If no → respond with exactly `HEARTBEAT_OK`

#### T3.7.2 — Active hours in SchedulerAgent
- [ ] Add `active_hours` config: `start_hour` (default 7), `end_hour` (default 22), `timezone`
- [ ] SchedulerAgent checks active hours before triggering any scheduled skill
- [ ] Skills can declare `active_hours_only: true` in frontmatter (heartbeat does, briefing doesn't)
- [ ] Add `active_hours_only` to SKILL.md parser
- **Tests:**
  - [ ] Skill with active_hours_only=true skipped outside active hours
  - [ ] Skill without the flag runs anytime

#### T3.7.3 — Heartbeat suppression in ConversationManager
- [ ] When skill execution returns `HEARTBEAT_OK`, don't send anything to transport
- [ ] Cooldown: don't trigger heartbeat within 15 minutes of last user interaction
- [ ] Log heartbeat decisions to activity feed
- **Tests:**
  - [ ] HEARTBEAT_OK → no message sent
  - [ ] Cooldown prevents back-to-back heartbeats

**Phase 2 exit:** Every 30 minutes during active hours, Nexus checks context and pings only when something is actionable. "You have a meeting in 30 minutes with Sarah."

---

### Phase 3: M3.2 — Trust-Gated Autonomy

> Trust scores per tool category. Actions earn or lose trust. High trust → autonomous.

#### T3.2.1 — Trust score store (`src/nexus/governance/trust.py`)
- [ ] `TrustStore` class:
  - `get_score(tenant_id: str, category: str) -> float` (default 0.5)
  - `update_score(tenant_id: str, category: str, delta: float) -> float`
  - `get_all_scores(tenant_id: str) -> dict[str, float]`
- [ ] Backed by MemoryAgent (`namespace="trust"`)
- [ ] Categories derived from tool name prefix: `gmail`, `calendar`, `tasks`, `search`, etc.
- [ ] Scores clamped to [0.0, 1.0]
- **Tests:**
  - [ ] Default score is 0.5
  - [ ] Positive delta increases score
  - [ ] Negative delta decreases score
  - [ ] Score clamped at boundaries

#### T3.2.2 — Trust thresholds in PolicyEngine
- [ ] `PolicyEngine.check()` accepts optional `trust_score: float`
- [ ] Threshold logic:
  - trust > 0.8 → ALLOW (autonomous for write actions)
  - 0.5 ≤ trust ≤ 0.8 → REQUIRE_APPROVAL
  - trust < 0.5 → DENY (advisory only, no execution even with approval)
- [ ] Read actions always ALLOW regardless of trust
- [ ] Configurable thresholds
- **Tests:**
  - [ ] High trust → write action auto-allowed
  - [ ] Medium trust → approval required
  - [ ] Low trust → denied
  - [ ] Read always allowed

#### T3.2.3 — Trust updates on approval/rejection
- [ ] On tool approval callback: `trust.update_score(tenant, category, +0.05)`
- [ ] On tool rejection callback: `trust.update_score(tenant, category, -0.1)`
- [ ] On policy deny: `trust.update_score(tenant, category, -0.15)`
- [ ] Asymmetric: trust is harder to build than to lose
- [ ] Log trust changes to audit sink
- **Tests:**
  - [ ] 5 approvals → trust rises from 0.5 to 0.75
  - [ ] 1 rejection → trust drops
  - [ ] Trust changes logged

#### T3.2.4 — Trust display in dashboard
- [ ] DashboardServer `get_trust` call: returns per-category trust scores for tenant
- [ ] Dashboard API: `GET /api/trust` → trust scores
- [ ] Dashboard HTML: trust section showing category scores as progress bars
- [ ] Color-coded: green (>0.8), yellow (0.5-0.8), red (<0.5)
- **Tests:**
  - [ ] Trust API returns scores
  - [ ] Dashboard HTML includes trust section

#### T3.2.5 — Wire trust into ConversationManager
- [ ] Before tool call: look up trust score for tool category
- [ ] Pass trust score to `PolicyEngine.check()`
- [ ] On high trust: execute without prompting (log to audit as "auto-approved")
- [ ] Show trust level in approval prompt: "Trust: 0.65 — [Approve] [Reject]"
- **Tests:**
  - [ ] Integration: approve 10 times → write action becomes autonomous
  - [ ] Reject → trust falls → more approvals required

**Phase 3 exit:** 5 approved email drafts → trust rises → low-stakes email actions become autonomous. Rejection → trust falls → approvals required again. Dashboard shows trust per category.

---

### Phase 4: M3.5 — Persona Builder CLI

> Interactive CLI to create new SOUL.md personas.

#### T3.5.1 — `nexus setup-persona` CLI command
- [ ] Interactive prompts:
  - Name (e.g., "Dross", "Friday")
  - Personality keywords (e.g., "witty, direct, helpful")
  - Formality level (casual / casual-professional / professional / formal)
  - Any specific quirks or rules
- [ ] Generate SOUL.md from template with user inputs
- [ ] Save to `personas/{name}.md`
- [ ] Option to set as default for a tenant
- **Tests:**
  - [ ] CLI produces valid SOUL.md file
  - [ ] Generated persona loads correctly via PersonaLoader
  - [ ] Name sanitized for filesystem

#### T3.5.2 — List and switch personas
- [ ] `nexus personas list` — show available personas
- [ ] `nexus personas set <name>` — set default persona for a tenant
- [ ] Reads from `personas/` directory
- **Tests:**
  - [ ] List shows all .md files in personas dir
  - [ ] Set updates tenant config

**Phase 4 exit:** `nexus setup-persona` creates a new persona interactively. `nexus personas list` shows available options.

---

## Wave A Exit Criteria

| Criterion | How to verify |
|---|---|
| "What's in the news?" → web search results | Telegram message → search tool call → results |
| Heartbeat pings only when actionable | Wait for 30-min tick during active hours |
| HEARTBEAT_OK → silence (no message) | Verify no message sent when nothing actionable |
| 5 approved email actions → gmail trust rises | Dashboard shows gmail trust > 0.75 |
| High trust → write action auto-approved | Trust > 0.8 → no approval prompt |
| Rejection → trust falls | Reject an action → dashboard shows lower trust |
| `nexus setup-persona` creates persona | CLI generates valid SOUL.md |
| Dashboard shows trust scores | Trust section with category progress bars |

---

## Build Order

```
T3.3.1 Docker compose (search)
    │
    ├── T3.3.2 Search intent pattern
    │
    └── T3.3.3 Config + integration
              │
T3.7.1 Heartbeat SKILL.md
    │
    ├── T3.7.2 Active hours in Scheduler
    │
    └── T3.7.3 Heartbeat suppression
              │
T3.2.1 Trust score store
    │
    ├── T3.2.2 Trust thresholds in PolicyEngine
    │
    ├── T3.2.3 Trust updates on approval/rejection
    │
    ├── T3.2.4 Trust display in dashboard
    │
    └── T3.2.5 Wire trust into ConversationManager
              │
T3.5.1 setup-persona CLI
    │
    └── T3.5.2 List + switch personas
```

---

## Progress Tracking

| Phase | Task | Status | Notes |
|---|---|---|---|
| 1 | T3.3.1 Docker compose (search) | ⬜ Not started | |
| 1 | T3.3.2 Search intent pattern | ⬜ Not started | |
| 1 | T3.3.3 Config + integration | ⬜ Not started | |
| 2 | T3.7.1 Heartbeat SKILL.md | ⬜ Not started | |
| 2 | T3.7.2 Active hours in Scheduler | ⬜ Not started | |
| 2 | T3.7.3 Heartbeat suppression | ⬜ Not started | |
| 3 | T3.2.1 Trust score store | ⬜ Not started | |
| 3 | T3.2.2 Trust thresholds | ⬜ Not started | |
| 3 | T3.2.3 Trust updates | ⬜ Not started | |
| 3 | T3.2.4 Trust display | ⬜ Not started | |
| 3 | T3.2.5 Wire trust | ⬜ Not started | |
| 4 | T3.5.1 setup-persona CLI | ⬜ Not started | |
| 4 | T3.5.2 List + switch | ⬜ Not started | |
