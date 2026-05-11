HANDOFF CONTEXT
===============

GOAL
----
Continue Nexus development. M1 through M3 complete and pushed to GitHub. Next: M4 (breadth) or further polish.

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

CURRENT STATE
-------------
- 75+ commits on main, pushed to GitHub
- 179 tests, all passing in ~2 seconds
- 40 source files, 27 test files
- CI: lint ✅ typecheck ✅ test ✅ docker ✅

PENDING TASKS
-------------
### M4 — Breadth (not started)
- Discord, Slack transports
- Homelab agents (Jellyfin, Paperless, etc.)
- Financial tracking, browser automation (Playwright MCP)
- Session checkpoints + rollback

### M5 — Polish (not started)
- Full Presidium governance (when packages ship)
- Production hardening, webhook mode, rate limiting
- Documentation, quickstart guide, demo video

### M6 — Presence (not started)
- PWA web app, Android app
- TTS implementation (Qwen3-TTS/CosyVoice, needs GPU)
- Animated avatar, voice-first ("Dross mode")

KEY FILES
---------
- AGENTS.md — project reference, key decisions, anti-patterns
- README.md — product overview, quickstart, architecture SVG
- CONTRIBUTING.md — code standards, PR checklist
- LICENSE — Apache 2.0
- docs/plans/ — M1, M2A, M2B, M3A, M3B implementation plans
- docs/reviews/ — security + quality audit
- config.example.yaml — documented config template
- .env.template — credential scaffolding
