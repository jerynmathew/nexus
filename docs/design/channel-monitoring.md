# Design: Channel Monitoring

> Status: Draft — design document, not yet planned for implementation
> Applies to: Discord, Slack (and future Matrix/Teams transports)

---

## Problem

Currently Nexus only responds when directly addressed (DMs or @mentions). It has no awareness of what's happening in channels. Users want:

- "What happened in #engineering today?"
- "Summarize the discussion in #design from this morning"
- "Alert me if anyone mentions the deployment"
- "What action items came out of the #standup channel?"

---

## Capability Levels

### Level 1: On-Demand Summary (lowest effort)
User explicitly asks "summarize #channel". Nexus fetches recent history via Discord/Slack API, sends to LLM for summary. No persistent storage.

### Level 2: Indexed History
Nexus passively reads configured channels, stores messages in MemoryAgent. Enables search: "find messages about the API migration in #backend". Requires ongoing storage.

### Level 3: Proactive Monitoring
Nexus watches for patterns (keywords, sentiment, action items) and proactively alerts the user. "Sarah mentioned the deadline was moved to Friday in #project-alpha."

---

## Architecture

### Transport Changes
- Remove the `if not is_dm and not is_mention: return` filter for monitored channels
- Add `monitored_channels` config per transport
- Messages from monitored channels stored but NOT responded to automatically
- Only DMs and mentions trigger ConversationManager

### Storage
- New `channel_messages` table in MemoryAgent (or extend `messages`)
- Fields: channel_id, channel_name, author, content, timestamp, transport
- FTS5 index for search
- Retention policy: configurable (default 7 days, then summarize and discard)

### Summarization Skill
```yaml
name: channel-summary
description: Summarize recent activity in a channel
execution: sequential
tool_groups: []
```

The skill queries MemoryAgent for channel messages, sends to LLM for summarization.

### Proactive Alerts (Level 3)
- Keyword watchlist per tenant (configurable via Telegram)
- Heartbeat skill extended to check channel messages for matches
- Alert delivered via primary transport (Telegram) even if source is Discord/Slack

---

## Privacy & Governance

### Concerns
- Reading all channel messages is a significant privacy expansion
- Users in monitored channels may not know Nexus is reading
- Stored messages could contain sensitive information
- Cross-channel data leakage between tenants

### Mitigations
- **Opt-in only**: channels must be explicitly configured for monitoring
- **Visibility**: Nexus announces presence in monitored channels (configurable)
- **Retention limits**: messages auto-deleted after configurable period
- **Tenant isolation**: channel data namespaced by tenant_id
- **Audit**: all channel reads logged to audit sink
- **Read-only default**: monitoring doesn't enable Nexus to post in channels (separate permission)

---

## Open Questions

1. Should channel monitoring be per-tenant or per-workspace?
2. How to handle threads vs top-level messages?
3. Should Nexus join channels as a visible member or use a service account?
4. Rate limiting: how often to poll for new messages? (Slack has rate limits)
5. Should summaries be cached or generated fresh each time?
6. How to handle private/restricted channels?

---

## Implementation Estimate

| Level | Effort | Dependencies |
|---|---|---|
| Level 1 (on-demand) | Low | Discord/Slack API history fetch |
| Level 2 (indexed) | Medium | MemoryAgent schema, FTS5, retention |
| Level 3 (proactive) | High | Heartbeat extension, keyword matching, cross-transport alerts |

Recommendation: ship Level 1 first (on-demand summary), then Level 2 if there's demand.
