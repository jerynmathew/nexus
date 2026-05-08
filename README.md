# Nexus

> The reliable personal AI assistant — built on [Civitas](https://github.com/civitas-io/python-civitas), governed by [Presidium](https://github.com/civitas-io/presidium).

**Status:** Pre-alpha. Documentation-first phase.

---

Nexus is a self-hosted personal AI assistant that manages your email, calendar, messages, and services — and recovers from failures automatically, because it's the only personal assistant with OTP-style supervision trees.

Built on Civitas (the Python agent runtime) and governed by Presidium (runtime policy enforcement), Nexus demonstrates what a **reliable, governed, multi-tenant** personal AI assistant looks like.

## Why Nexus

Every personal AI assistant in the market shares the same weakness: when something crashes, everything stops. A Gmail API timeout takes down your calendar. A malformed email crashes the whole bot. You wake up to silence instead of your morning briefing.

Nexus is different because Civitas is different. Each integration runs as an independent supervised agent. When Gmail crashes, the supervisor restarts it with backoff — your calendar keeps running, your briefing arrives with the data that's available, and the Gmail agent is back before you notice.

**No other personal AI assistant can do this.**

## Documentation

| Document | Status |
|---|---|
| [Product Requirements](docs/vision/prd.md) | Draft |
| [Competitive Analysis](docs/research/competitive-analysis.md) | Draft |
| [Milestone Plan](docs/vision/milestones.md) | Draft |

## License

Apache 2.0
