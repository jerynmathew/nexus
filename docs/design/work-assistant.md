# Design: Work Assistant — Chief of Staff as Software

> Status: Draft — core product design
> Priority: Highest — this is why Nexus exists
> Target: M5 milestone (replaces original M5 "Polish" scope)

---

## The Problem

You're a staff engineer and acting manager. You wear multiple hats:
- IC work (architecture, code review, technical decisions)
- Management work (1:1s, unblocking, delegation, hiring)
- Cross-team coordination (dependencies, alignment, escalation)
- Strategic work (roadmap, tech debt, process improvement)

Every day, commitments are made in emails, Slack threads, meetings, and PRs. You're the single point of failure for decisions that affect multiple teams. Dropping the ball has rippling consequences.

No human can track all of this manually. Current tools (calendars, task apps, email clients) are passive — they store information but don't synthesize, prioritize, or follow up.

**Nexus must be your chief of staff** — actively managing your workload, not just answering questions.

---

## What "Chief of Staff" Means in Practice

### Morning: Structured Day Start

Not "5 unread emails." Instead:

```
Good morning. Here's your day:

⚡ URGENT (do first):
  - Sarah's PR #234 is blocked on your review (opened 2 days ago, she asked in Slack yesterday)
  - API migration deadline is tomorrow — deployment checklist doc needs your sign-off
  - Budget approval email from VP needs response by EOD

📅 TODAY'S MEETINGS:
  09:30 — Standup (#backend team)
      Context: Test failures discussed yesterday, Sarah has a fix pending
  11:00 — 1:1 with Raj
      Context: He mentioned feeling overwhelmed in last 1:1. Performance review due next week.
      Suggested topics: workload, performance review prep
  14:00 — Architecture review
      Context: 3 open comments on the RFC doc. Two from you (unresolved).
      Pre-read: Architecture RFC v2 (last updated yesterday)

📋 YOUR COMMITMENTS (from this week):
  ✅ Review Sarah's PR — due today (from Monday standup)
  ⏳ Write the migration runbook — due Thursday (from team planning)
  ⏳ Share feedback on Raj's design doc — due Friday (from 1:1)
  ❌ OVERDUE: Reply to infra team about capacity planning (promised Tuesday)

👥 DELEGATION TRACKER:
  Raj: Working on cache redesign (due Friday, no update since Tuesday)
  Priya: Onboarding doc (due next Monday, shared draft yesterday — looks on track)
  Alex: Load test setup (due Wednesday, asked for help in #backend yesterday — may be blocked)

💬 OVERNIGHT ACTIVITY:
  #backend: Discussion about retry logic — Alex and Sarah disagreed, no resolution
  #incidents: P2 alert for payment service latency, resolved by on-call
  Email: 3 new threads, 2 are FYI newsletters, 1 from product about Q3 priorities
```

### During Day: Contextual Intelligence

**Before each meeting:**
Nexus proactively sends a brief 2 minutes before:
```
📅 1:1 with Raj in 2 min

Since last 1:1:
- He completed the API endpoint migration (merged 3 PRs)
- He asked about TypeScript adoption in #backend (seems interested)
- His Jira tickets are on track except the cache redesign (no update in 3 days)

Open items from last 1:1:
- You promised to review his design doc (not done yet)
- He wanted to shadow the architecture review (you said you'd add him)

Suggested agenda:
1. Cache redesign status (may be stuck)
2. Performance review prep (due next week)
3. TypeScript adoption interest (career development opportunity)
```

**After each meeting:**
Nexus asks:
```
📝 Post-meeting capture for: 1:1 with Raj

Any action items to track?
(reply with bullet points, or say "nothing new")
```

And tracks whatever you reply.

**Throughout the day:**
- "Raj just pushed an update to the cache redesign PR" → tracks against your delegation
- "Sarah mentioned in #backend that she's blocked on your review" → nudge
- "The VP replied to your budget email — needs a number by 3pm" → escalate priority

### Evening: Day Wrap

```
📊 Day Summary:

Completed:
  ✅ Reviewed Sarah's PR #234
  ✅ 1:1 with Raj (action items captured)
  ✅ Replied to VP budget email

Still open:
  ⏳ Migration runbook (due Thursday)
  ❌ Infra team reply (now 2 days overdue — should you delegate this?)
  ⏳ Raj's design doc feedback (due Friday)

Tomorrow's first meeting: 09:00 Team standup
  Prep needed? (Nexus will send context at 08:45)
```

---

## System Architecture

### Core Components

```
┌──────────────────────────────────────────────┐
│              Work State Engine               │
│                                              │
│  ┌────────────┐  ┌──────────┐  ┌─────────┐ │
│  │ Action Item │  │ People   │  │ Meeting │ │
│  │ Tracker    │  │ Graph    │  │ Context │ │
│  └────────────┘  └──────────┘  └─────────┘ │
│  ┌────────────┐  ┌──────────┐              │
│  │ Delegation │  │ Priority │              │
│  │ Tracker    │  │ Engine   │              │
│  └────────────┘  └──────────┘              │
└──────────────────────────────────────────────┘
         ▲              ▲              ▲
         │              │              │
    ┌────┘      ┌───────┘      ┌──────┘
    │           │              │
┌───┴───┐  ┌───┴───┐  ┌───────┴──────┐
│Signals│  │ Skills │  │ConversationMgr│
│(L1)   │  │(SKILL) │  │(queries)     │
└───────┘  └───────┘  └──────────────┘
```

### Work State: Persistent, Not Ephemeral

Unlike conversation sessions (ephemeral, 30-min TTL), work state is **persistent and evolving**:

```sql
-- Action items extracted from all signals
CREATE TABLE work_actions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id   TEXT NOT NULL,
    title       TEXT NOT NULL,
    description TEXT,
    status      TEXT NOT NULL DEFAULT 'open',    -- open, in_progress, done, overdue
    priority    TEXT DEFAULT 'medium',           -- critical, high, medium, low
    due_date    TEXT,                            -- ISO date or NULL
    source      TEXT NOT NULL,                   -- "email", "slack", "meeting", "manual"
    source_ref  TEXT,                            -- message ID, thread URL, etc.
    assigned_to TEXT,                            -- person (self or delegate)
    assigned_by TEXT,                            -- who created this commitment
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    reminder_sent BOOLEAN DEFAULT FALSE
);

-- Delegation tracking
CREATE TABLE work_delegations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id   TEXT NOT NULL,
    delegated_to TEXT NOT NULL,                  -- person name (resolved via people graph)
    task        TEXT NOT NULL,
    status      TEXT DEFAULT 'assigned',         -- assigned, in_progress, review, done, stale
    due_date    TEXT,
    last_update TIMESTAMP,                       -- last signal from this person about this task
    source      TEXT,                            -- where delegation was made
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Meeting context (pre/post)
CREATE TABLE work_meetings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id   TEXT NOT NULL,
    event_id    TEXT,                            -- Google Calendar event ID
    title       TEXT NOT NULL,
    attendees   TEXT,                            -- JSON array of person IDs
    prep_sent   BOOLEAN DEFAULT FALSE,
    notes       TEXT,                            -- post-meeting notes
    action_items TEXT,                           -- JSON array of action IDs
    meeting_date TEXT
);
```

### Skills for Work Intelligence

| Skill | Trigger | What it does |
|---|---|---|
| `work-morning-briefing` | Cron 07:00 (work profile) | Full structured day start as described above |
| `work-meeting-prep` | 2 min before each meeting | Context brief for upcoming meeting |
| `work-meeting-capture` | After each meeting ends | Prompt for action items, store notes |
| `work-evening-wrap` | Cron 18:00 | Day summary, open items, tomorrow preview |
| `work-action-extract` | On every inbound signal | LLM scans for commitments/action items |
| `work-delegation-check` | Heartbeat (every 30 min) | Check for stale delegations, missing updates |
| `work-priority-rerank` | On new urgent signal | Re-evaluate priority queue |

### Profile-Aware Briefing

The work briefing is a completely different beast from personal briefing. This is where **profiles** matter:

```yaml
# Work profile morning briefing
name: work-morning-briefing
description: Structured day start for staff engineer + manager role
execution: parallel
timeout_per_section: 45
tool_groups: [google, search]
schedule: "0 7 * * 1-5"  # Weekdays only
active_hours_only: true
profile: work  # Only triggers for work profile

sections:
  - urgent_triage
  - todays_meetings
  - commitments
  - delegation_tracker
  - overnight_activity
```

```yaml
# Personal profile morning briefing
name: personal-morning-briefing
execution: parallel
schedule: "0 8 * * *"  # Every day
profile: personal

sections:
  - weather
  - personal_calendar
  - personal_emails
  - news_headlines
```

### Action Item Extraction

Every signal (email, Slack message, meeting note) is scanned for commitments:

```
Signal: Email from Sarah
"Can you review PR #234 by tomorrow? The feature freeze is Wednesday."

→ Action extracted:
  title: "Review Sarah's PR #234"
  due_date: "tomorrow"
  priority: "high" (deadline mentioned)
  assigned_to: "self"
  assigned_by: "Sarah"
  source: "email"
  source_ref: "msg_id_xyz"
```

This runs as a lightweight LLM call (Haiku) on every inbound work signal. The prompt:

```
Extract action items from this message. For each action item, identify:
- What needs to be done
- Who is responsible (the reader, or someone else being delegated to)
- When it's due (if mentioned)
- How urgent it is

If no action items, respond with "NONE".
```

### Delegation Intelligence

When you say "Raj, can you handle the cache redesign by Friday?" in Slack or email, Nexus:

1. Detects this as a delegation (you → Raj, task, deadline)
2. Creates a `work_delegations` entry
3. Monitors signals from Raj about this topic
4. If no update by Wednesday (2 days before deadline): "Raj hasn't updated on the cache redesign. Due Friday. Should I check in?"
5. If Raj asks for help in #backend: "Raj seems blocked on the cache redesign (asked about eviction policy in #backend). Due Friday."

### Priority Engine

Not all action items are equal. Priority is determined by:

| Factor | Weight | Example |
|---|---|---|
| Explicit deadline | High | "by EOD", "before Wednesday" |
| Requester seniority | Medium | VP request > peer request |
| Blocking others | High | "blocked on your review" |
| Overdue duration | Increases | 1 day overdue > just due |
| Dependencies | Medium | Blocks downstream work |
| Your stated priorities | High | Items you marked as important |

Priority re-ranks automatically when new signals arrive. "Sarah mentioned in Slack that she's blocked" → PR review priority goes from medium to high.

---

## Implementation Phases

### Phase 1: Action Item Tracking
- `work_actions` table in MemoryAgent
- Action extraction from emails and Slack messages (LLM scan)
- Manual action creation: "remind me to review Sarah's PR by tomorrow"
- `/actions` command: list open action items sorted by priority
- Morning briefing includes action items section
- **This alone is transformative.**

### Phase 2: Meeting Intelligence
- `work_meetings` table
- Pre-meeting context (2 min before, uses calendar + signals)
- Post-meeting capture prompt
- Meeting action items linked to calendar events
- Enhanced 1:1 prep with last-meeting context

### Phase 3: Delegation Tracking
- `work_delegations` table
- Delegation detection from outbound messages
- Stale delegation alerts (heartbeat checks)
- Delegation status in morning briefing

### Phase 4: Priority Engine
- Multi-factor priority scoring
- Auto-rerank on new signals
- "What should I do next?" → prioritized action list
- Urgency escalation (overdue items get louder)

### Phase 5: Full Day Orchestration
- Structured day start (morning briefing as designed above)
- Pre-meeting briefs throughout the day
- Evening wrap with day summary
- Next-day preview

---

## Relationship to Existing Architecture

| Component | Enhancement |
|---|---|
| **Profiles** | Work profile triggers work skills, personal profile triggers personal skills |
| **Morning briefing** | Replaced with profile-aware version (work vs personal) |
| **Heartbeat** | Enhanced with delegation checking, action item reminders |
| **MemoryAgent** | New tables: work_actions, work_delegations, work_meetings |
| **ConversationManager** | New commands: /actions, /delegate, /commitments |
| **Skills** | New work-specific skills (meeting-prep, action-extract, evening-wrap) |
| **Trust** | Work actions governed by same trust system |

---

## Open Questions

1. **Meeting notes**: How to capture? Voice transcription? Manual text? Integration with Google Meet/Zoom transcript?
2. **Calendar integration depth**: Can we detect meeting type (1:1, standup, review) automatically?
3. **Multi-org**: Staff engineers often work across teams with different Slack workspaces. How to handle?
4. **Delegation ethics**: Should Nexus nudge your reports? Or only nudge you to follow up?
5. **Priority override**: Can you manually override auto-priority? "This is actually low priority, stop reminding me."
6. **Context window**: All this context is token-heavy. How to stay under budget?
