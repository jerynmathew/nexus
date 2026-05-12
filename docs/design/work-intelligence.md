# Design: Work Intelligence

> Status: Draft — architectural design for cross-signal work awareness
> Priority: Major feature — spans M5+ milestones
> Depends on: M4 complete (Discord, Slack transports, MCP infrastructure)

---

## Vision

Nexus currently handles point queries: "check my email", "what's on my calendar." Each query operates on a single data source in isolation.

Work intelligence transforms Nexus from a **reactive tool caller** into a **context-aware work partner** that maintains continuous awareness across all your work signals and synthesizes them into actionable intelligence.

The end state: "Prepare me for my 2pm meeting with Sarah" pulls the relevant email thread, the Slack discussion where she raised concerns, the doc she shared yesterday, and the PR she opened this morning — without you specifying any of that.

---

## Architecture: Three Layers

### Layer 1: Signal Collection

Inputs from every work surface, normalized into a common event stream.

| Signal | Source | Status | Event types |
|---|---|---|---|
| Email | Gmail MCP | ✅ Have | new_email, reply, thread_update |
| Calendar | Google Calendar MCP | ✅ Have | event_created, event_updated, upcoming_event |
| Tasks | Google Tasks MCP | ✅ Have | task_created, task_completed, task_overdue |
| Slack | Slack transport + API | ✅ Transport built | channel_message, thread_reply, mention, reaction |
| Slack (extended) | `slack-pp-mcp` ([Printing Press](printing-press.md)) | Available | channel_history, user_lookup, message_search |
| Discord | Discord transport + API | ✅ Transport built | channel_message, mention, reaction |
| Documents | Google Drive/Docs MCP | Available in MCP server | doc_shared, doc_edited, comment_added |
| Issues (Linear) | `linear-pp-mcp` ([Printing Press](printing-press.md)) | Available | issue_created, issue_updated, sprint_status, assignment |
| Issues (Jira) | Jira MCP (or `jira-pp-cli` when MCP ships) | Planned | issue_created, issue_updated, sprint_status |
| Code | GitHub MCP / `github-pp-mcp` | Available | pr_opened, pr_reviewed, issue_assigned, commit_pushed |
| Design | `figma-pp-mcp` ([Printing Press](printing-press.md)) | Available | comment_added, file_updated |
| Docs (Notion) | `notion-pp-mcp` ([Printing Press](printing-press.md)) | Available | page_edited, comment_added, database_updated |
| Web | open-websearch MCP | ✅ Have | search_result (on-demand only) |

#### Signal Event Schema

```python
@dataclass(frozen=True)
class WorkSignal:
    signal_id: str               # unique ID
    source: str                  # "gmail", "slack", "github"
    event_type: str              # "new_email", "channel_message", "pr_opened"
    timestamp: float             # unix epoch
    tenant_id: str               # which user this belongs to

    # Content
    title: str                   # subject line, channel name, PR title
    body: str                    # message content (truncated for storage)
    url: str | None              # link to original (email link, Slack permalink, PR URL)

    # People
    author: str                  # who created this signal
    author_email: str | None     # for cross-signal resolution
    mentioned: list[str]         # people mentioned in the content

    # Context
    channel: str | None          # Slack channel, Discord channel, email thread
    project: str | None          # inferred or tagged project
    priority: str                # "high", "medium", "low" (inferred)

    # Metadata
    raw_metadata: dict[str, Any] # source-specific data
```

#### Collection Strategy

| Strategy | How | When |
|---|---|---|
| **Push (real-time)** | Transport handlers fire signals as messages arrive | Slack/Discord (already receiving messages) |
| **Pull (periodic)** | Scheduler queries MCP tools for recent changes | Email, Calendar, GitHub (poll every 5 min) |
| **On-demand** | User asks → fetch → create signals | Web search, specific doc lookup |

### Layer 2: Context Graph

A lightweight entity resolution and relationship layer. Not a full knowledge graph — just enough to connect signals across sources.

#### Entities

| Entity | How resolved | Storage |
|---|---|---|
| **People** | Email address matching, display name fuzzy match | `work_people` table |
| **Projects** | Channel name, email subject prefix, GitHub repo | `work_projects` table |
| **Topics** | LLM-extracted keywords from signals | FTS5 index on signals |

#### People Resolution

```
"Sarah Chen" in email (sarah.chen@company.com)
  = "Sarah C" in Slack (@sarah.c)
  = "sarahchen" on GitHub
  = Contact "Sarah Chen" in Google Contacts
```

Resolution approach:
1. **Exact match**: email address appears in multiple sources
2. **Fuzzy match**: display name similarity (Levenshtein distance)
3. **LLM-assisted**: "Is 'Sarah C' in Slack the same as 'Sarah Chen' in email?" (asked once, cached)

Storage:
```sql
CREATE TABLE work_people (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id   TEXT NOT NULL,
    canonical_name TEXT NOT NULL,
    emails      TEXT,  -- JSON array
    slack_id    TEXT,
    discord_id  TEXT,
    github_username TEXT,
    relationship TEXT,  -- "manager", "teammate", "stakeholder", "external"
    last_seen   TIMESTAMP
);
```

#### Project/Topic Inference

Signals are tagged with projects either:
- **Explicitly**: Slack channel name → project (e.g., #project-nexus → "nexus")
- **By convention**: email subject prefix → project (e.g., "[Nexus] ..." → "nexus")
- **By LLM**: periodic clustering of recent signals by topic

### Layer 3: Synthesis

The intelligence layer that answers questions by combining signals from Layer 1 through the graph in Layer 2.

#### Query Types

**1. Meeting Prep**
```
User: "Prepare me for my 2pm meeting with Sarah"
→ Calendar: find the 2pm event, get attendees
→ People: resolve "Sarah" → Sarah Chen → email, Slack, GitHub
→ Signals: recent emails with Sarah, Slack messages in shared channels,
           PRs she opened, docs she shared
→ Synthesize: "Here's what you need to know:
   - She emailed about the API migration deadline (Tuesday)
   - In #backend she asked about the test failures on PR #234
   - She shared the architecture doc v2 yesterday, you haven't opened it"
```

**2. Catch-Up**
```
User: "What happened while I was in my meeting?" (or "while I was away")
→ Time range: last 2 hours (or since last active)
→ Signals: all signals in time range, sorted by priority
→ Filter: only signals relevant to user (their channels, their projects, mentions)
→ Synthesize: grouped by project/topic, most important first
```

**3. Person Context**
```
User: "What's Sarah working on?"
→ People: resolve Sarah
→ Signals: her recent activity across all channels
→ Synthesize: current projects, recent discussions, open items
```

**4. Project Status**
```
User: "Status of the API migration"
→ Project: resolve "API migration" → channels, repos, threads
→ Signals: recent activity tagged to this project
→ Synthesize: timeline, blockers, recent decisions, who's doing what
```

**5. Enhanced Morning Briefing**
The existing morning-briefing skill becomes much richer:
```
Instead of:
  📧 5 unread emails
  📅 3 meetings today

Now:
  📧 Sarah replied to the API migration thread — she needs your review by EOD
  📅 2pm: 1:1 with Sarah — she raised concerns about test coverage in #backend
  💬 Discussion in #design about the new dashboard — 3 people waiting for your input
  🔀 PR #234 has 2 approvals, needs yours to merge
  ⚡ Action items from yesterday: you promised to review the architecture doc (not done)
```

#### Synthesis Architecture

The synthesis layer doesn't need a dedicated agent. It's a **skill** that uses existing tools:

```yaml
name: work-context
description: Build cross-signal work context for a query
execution: sequential
tool_groups: [google, search]
```

The skill instructs the LLM to:
1. Identify what information is needed (people, projects, time range)
2. Query MemoryAgent for relevant signals
3. Resolve people across sources
4. Synthesize a coherent answer

For complex queries (meeting prep), the ConversationManager's tool-use loop naturally orchestrates multiple MCP calls.

---

## Implementation Phases

### Phase 1: Signal Storage + On-Demand Channel Summary
- Add `work_signals` table to MemoryAgent
- Slack/Discord transports store messages from monitored channels
- "Summarize #channel" queries stored signals → LLM summary
- **Effort: Medium. Delivers immediate value.**

### Phase 2: Periodic Signal Collection
- Scheduler pulls recent email/calendar/task changes every 5 minutes
- Normalizes into WorkSignal format
- Stores with FTS5 indexing
- "What happened today?" works across all signals
- **Effort: Medium. Expands signal coverage.**

### Phase 3: People Resolution
- `work_people` table with cross-source identity mapping
- Email-based exact matching
- LLM-assisted fuzzy matching (asked once, cached)
- "What's Sarah working on?" resolves across sources
- **Effort: Medium. Enables person-centric queries.**

### Phase 4: Enhanced Morning Briefing
- Morning briefing skill rewritten to use cross-signal context
- Action item tracking across signals
- Meeting prep as a first-class capability
- **Effort: Low (once phases 1-3 exist). Highest user-visible impact.**

### Phase 5: Proactive Intelligence
- Heartbeat extended with cross-signal awareness
- Priority inference (urgent email + mentioned in Slack = high priority)
- Keyword watchlists
- "You haven't responded to Sarah's email from 3 hours ago, and she just asked about it in Slack"
- **Effort: High. Requires good signal coverage and people resolution.**

---

## Data Model

```sql
-- Work signals from all sources
CREATE TABLE work_signals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id   TEXT NOT NULL,
    signal_id   TEXT UNIQUE NOT NULL,
    source      TEXT NOT NULL,           -- "gmail", "slack", "discord", "github"
    event_type  TEXT NOT NULL,
    timestamp   TIMESTAMP NOT NULL,
    title       TEXT NOT NULL,
    body        TEXT,
    url         TEXT,
    author      TEXT,
    author_email TEXT,
    channel     TEXT,
    project     TEXT,
    priority    TEXT DEFAULT 'medium',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE VIRTUAL TABLE work_signals_fts USING fts5(
    title, body, author,
    content='work_signals',
    content_rowid='id'
);

-- Cross-source people resolution
CREATE TABLE work_people (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id       TEXT NOT NULL,
    canonical_name  TEXT NOT NULL,
    emails          TEXT,               -- JSON array
    slack_id        TEXT,
    discord_id      TEXT,
    github_username TEXT,
    relationship    TEXT,
    last_seen       TIMESTAMP,
    UNIQUE(tenant_id, canonical_name)
);
```

---

## Privacy & Governance

| Concern | Mitigation |
|---|---|
| Channel messages stored | Opt-in per channel, retention limits (default 7 days) |
| Email content indexed | Already governed by existing Gmail MCP trust |
| Cross-source identity linking | Per-tenant, never shared between tenants |
| Proactive alerts about others | Only surfaces activity in user's channels/projects |
| Data retention | Configurable. Summarize + discard after retention period. |
| Audit | All signal reads/writes logged to existing audit sink |

---

## Relationship to Existing Architecture

| Component | Role in Work Intelligence |
|---|---|
| **MCPManager** | Fetches signals from email, calendar, docs, GitHub, Linear, Notion, Figma |
| **Printing Press CLIs** | Supply MCP servers for Linear, Slack, GitHub, Notion, Figma — see [integration design](printing-press.md) |
| **MemoryAgent** | Stores work_signals and work_people tables |
| **SchedulerAgent** | Periodic signal collection (pull strategy) |
| **ConversationManager** | Synthesis queries (meeting prep, catch-up, status) |
| **Skills** | work-context, channel-summary, meeting-prep as SKILL.md files |
| **Heartbeat** | Enhanced with cross-signal priority detection |
| **Trust system** | Governs what synthesis Nexus can do autonomously |

No new agents needed. The existing architecture handles this through skills + MCP tools + MemoryAgent storage. Printing Press CLIs dramatically expand signal coverage with zero code changes — each `<api>-pp-mcp` binary is just another MCP server that MCPManager auto-discovers.

---

## Open Questions

1. **Signal volume**: How many signals per day? Storage/query performance at scale?
2. **LLM cost**: Cross-signal synthesis is token-heavy. Cache aggressively?
3. **Privacy in multi-tenant**: Tenant A and Tenant B share a Slack workspace — how to handle?
4. **Accuracy**: People resolution will have false positives. How to handle corrections?
5. **GitHub integration**: Use `github-pp-mcp` ([Printing Press](printing-press.md)) or a dedicated GitHub MCP server? PP provides broad coverage; dedicated may offer deeper webhook integration. Personal repos vs org repos scoping TBD.
6. **Real-time vs batch**: Should synthesis be real-time or pre-computed on schedule?
