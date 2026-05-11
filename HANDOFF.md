HANDOFF CONTEXT
===============

GOAL
----
Continue Nexus development. M1 through M4 complete. Next: build extension system (M5.0) then nexus-work extension.

WORK COMPLETED
--------------
### M1 — Foundation ✅
- Civitas supervision tree (4 agents: memory, conversation_manager, scheduler, dashboard)
- Telegram transport (polling), CLI transport (dev)
- Persona system (SOUL.md + USER.md), Dross persona, profile-based multi-persona
- LLMClient → AgentGateway (:4000) → Anthropic
- Session checkpointing, tenant seeding, FTS5 memory search
- Config system, CLI (nexus run/setup/version/setup-google/setup-persona/personas)
- Dockerfile, docker-compose, GitHub Actions CI, pre-commit hooks

### M2 Wave A — Daily Driver ✅
- MCPManager using official `mcp` Python SDK (sse/streamable-http/stdio)
- Google Workspace MCP sidecar (Gmail, Calendar, Tasks — live, OAuth complete)
- Tool-use loop, task-based model routing (Haiku/Sonnet)
- Governance: PolicyEngine, JSONL audit, approval flow
- Skill system: SKILL.md parser, SkillManager, morning briefing, heartbeat
- SchedulerAgent: real cron engine, Telegram rich formatting (markdown→HTML)

### M2 Wave B — Web Surface ✅
- Web dashboard at :8080 (topology diagram, agent health, activity feed)
- Content viewer (/view/<id> — TL;DR + link on Telegram for long responses)
- Context compression (4-phase, triggers at 50% context window)

### M3 Wave A — Trust & Intelligence ✅
- Web search (open-websearch MCP sidecar, no API keys)
- Proactive heartbeat (SKILL.md, active hours, HEARTBEAT_OK suppression)
- Trust-gated autonomy (per-tool-category scores, threshold logic, dashboard display)
- Persona builder (nexus setup-persona CLI), profile-based personas

### M3 Wave B — Media ✅
- MediaHandler protocol with pluggable STT/TTS/Vision backends
- WhisperSTT (faster-whisper, CPU), ClaudeVision (via AgentGateway)
- Document parser (text/PDF), video frame extraction (ffmpeg)
- Telegram: voice, photo, document, video handlers
- TTS interface defined (ready for Qwen3-TTS/CosyVoice when GPU available)

### OSS Readiness ✅
- README, CONTRIBUTING.md, LICENSE (Apache 2.0)
- Architecture SVG diagrams (no ASCII art)
- Codebase review: 12 issues found and fixed
- Dependencies pinned with ~= operator, uv.lock tracked
- Pushed to https://github.com/jerynmathew/nexus — CI green

### M4 — Breadth ✅
- Discord + Slack transports (cross-transport continuity)
- Resilience: /status command, dynamic system prompt, MCP health monitoring
- Browser automation: Playwright MCP sidecar, SSRF protection
- Session checkpoints: /checkpoint and /rollback commands

CURRENT STATE
-------------
- 87 commits on main, pushed to GitHub
- 179 tests, all passing in ~2 seconds
- 42 source files, 27 test files
- CI: lint ✅ typecheck ✅ test ✅ docker ✅

PENDING TASKS
-------------
### M5 — Extensions + Work Intelligence (designed, not started)
- Extension system: NexusExtension protocol, NexusContext API, discovery
- nexus-work extension: action tracking, delegation, meeting prep, priority engine
- See: docs/design/extensions.md, docs/design/work-assistant.md

### M6 — Production (not started)
- Full Presidium governance (when packages ship)
- Production hardening, webhook mode, rate limiting

### M7 — Presence (not started)
- PWA web app, Android app
- TTS with voice cloning (Qwen3-TTS/CosyVoice, needs GPU)
- Animated avatar, voice-first ("Dross mode")

### Design Docs (completed, not yet implemented)
- docs/design/extensions.md — composable plugin architecture
- docs/design/work-assistant.md — chief of staff as software
- docs/design/work-intelligence.md — cross-signal work awareness
- docs/design/finance.md — gold/stocks analysis
- docs/design/channel-monitoring.md — passive channel reading

KEY FILES
---------
- AGENTS.md — project reference, key decisions, anti-patterns
- README.md — product overview, quickstart, architecture SVG
- CONTRIBUTING.md — code standards, PR checklist
- LICENSE — Apache 2.0
- docs/index.md — documentation walkthrough
- docs/plans/ — M1, M2A, M2B, M3A, M3B, M4 implementation plans
- docs/design/ — extension architecture, work assistant, finance, channel monitoring
- docs/reviews/ — security + quality audit
