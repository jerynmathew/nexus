# Nexus Documentation

> The reliable personal AI assistant — self-hosted, crash-resilient, governed.

This guide walks you through the documentation in the order that makes sense — from "what is this?" to "how do I build on it?"

---

## Start Here

| Document | What you'll learn |
|---|---|
| [Product Requirements](vision/prd.md) | What Nexus does, who it's for, the 12 core features (F1–F12) |
| [Milestone Plan](vision/milestones.md) | M1–M6 roadmap with exit criteria. M1–M3 complete, M4+ planned |
| [Competitive Analysis](research/competitive-analysis.md) | How Nexus compares to OpenClaw, Hermes, Nanobot and others |

## Architecture

How the system is built and why each decision was made.

| Document | What you'll learn |
|---|---|
| [Architecture Overview](architecture/overview.md) | Supervision tree, message flows, startup sequence, Civitas integration points |
| [Memory Architecture](architecture/memory.md) | Three-layer memory (session, persistent, skill), FTS5 search, Dream consolidation |
| [Multi-Tenant Model](architecture/multi-tenant.md) | Tenant isolation, profiles, persona-per-profile, workspace accounts |

![Architecture Overview](assets/readme-architecture.svg)

## Design

Detailed design for each major component. Read these when you want to understand *how* a specific part works.

| Document | Component | Key concepts |
|---|---|---|
| [Conversation Manager](design/conversation.md) | `ConversationManager` | Session lifecycle, tool-use loop, skill execution, governance hooks |
| [Transport](design/transport.md) | `BaseTransport` | Protocol abstraction, InboundMessage, Telegram/CLI implementations |
| [Persona System](design/persona.md) | `PersonaLoader` | SOUL.md, USER.md, prompt assembly, persona builder |
| [Scheduler](design/scheduler.md) | `SchedulerAgent` | Cron engine, skill triggers, active hours |
| [Integrations](design/integrations.md) | `MCPManager` | MCP-first model, tool filtering, custom agents (exception path) |
| [Extensions](design/extensions.md) | `NexusExtension` | Composable plugin system, pip + directory distribution |
| [Work Assistant](design/work-assistant.md) | `nexus-work` | Action tracking, delegation, meeting prep, priority engine |
| [Work Intelligence](design/work-intelligence.md) | Signal layer | Cross-signal awareness, people resolution, synthesis |
| [Finance](design/finance.md) | `nexus-finance` | Gold/stocks analysis, charts, buy/sell recommendations |
| [Channel Monitoring](design/channel-monitoring.md) | Transports | Passive reading, summarization, proactive alerts |

## Implementation Plans

Detailed task breakdowns with progress tracking. These document every decision and trade-off made during development.

| Plan | Milestone | Tasks | Status |
|---|---|---|---|
| [M1 Implementation](plans/m1-implementation.md) | Foundation | 30 tasks | ✅ Complete |
| [M2 Wave A](plans/m2-wave-a-implementation.md) | MCP + Google + Skills + Governance | 19 tasks | ✅ Complete |
| [M2 Wave B](plans/m2-wave-b-implementation.md) | Dashboard + Content Viewer + Compression | 8 tasks | ✅ Complete |
| [M3 Wave A](plans/m3-wave-a-implementation.md) | Trust Arc + Heartbeat + Search + Persona | 13 tasks | ✅ Complete |
| [M3 Wave B](plans/m3-wave-b-implementation.md) | STT + Vision + Documents + Video | 8 tasks | ✅ Complete |
| [M4](plans/m4-implementation.md) | Resilience + Browser + Checkpoints + Discord + Slack | 14 tasks | ✅ Complete |

## Reviews

| Document | What it covers |
|---|---|
| [Codebase Review](reviews/codebase-review-2026-05-09.md) | Security audit, code quality, dependency analysis. 12 issues found and fixed. |

## Architecture Diagrams

All diagrams are in `docs/assets/` as rich SVGs:

| Diagram | Shows |
|---|---|
| [Architecture Overview](assets/readme-architecture.svg) | Supervision tree, agents, external services |
| [M2 Architecture](assets/m2-architecture.svg) | MCP + governance + skills data flow |
| [M2 Wave B Architecture](assets/m2-wave-b-architecture.svg) | Dashboard + content viewer + compression |
| [Supervision Tree](assets/supervision-tree.svg) | Agent hierarchy and restart strategies |
| [Message Flow](assets/message-flow.svg) | Request path from Telegram to LLM to MCP |
| [Memory Architecture](assets/memory-architecture.svg) | Three-layer memory model |
| [Multi-Tenant Model](assets/multi-tenant-model.svg) | Tenant, profile, persona relationships |
| [System Architecture](assets/system-architecture.svg) | Full system overview |

## Reading Order

**If you're evaluating Nexus:**
PRD → Competitive Analysis → Architecture Overview → README quickstart

**If you're contributing:**
README → CONTRIBUTING.md → AGENTS.md → Architecture Overview → relevant Design doc

**If you're extending Nexus (adding integrations):**
Integrations design → Transport design → CONTRIBUTING.md

**If you're curious about decisions:**
Implementation plans (M1 → M2A → M2B → M3A → M3B) — each documents the decision process
