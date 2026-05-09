HANDOFF CONTEXT
===============

USER REQUESTS (AS-IS)
---------------------
- "civitas-io. You are helping me onboard to the civitas-io open source project."
- "One of the largest known usecase of Agentic wfs/apps / LLM is coding agents. Can this civitas and presidium offer anything there as a harness?"
- "I want to try and evaluate building the personal assistant example."
- "The scope is bigger. Go thru /Users/jeryn/workspace/projects/m1.8-personal-assistant. It has a more elaborate scope, but was designed with a much earlier avatar of civitas in mind."
- "Lets go with nexus. One more thing. I had a personality for my version of the agent - Called Dross."
- "Create a repo. use jerynmathew user account on GH. DO NOT Push to remote yet. we will follow a llm-wiki guideline as always."
- "1. Single first. Multi tenant later. 2. Anthropic first. But some LLM router interface is needed. Not a big fan of litellm, agentgateway single binary deployment looks attractive. 3. Yes. definitely. No assumptions, research APIs and interfaces first. 4. Pull fresh civitas."
- "Are you going to make a detailed plan/todo first? I prefer that with progress tracking in it. Please note, no code is complete without test code. Focus on testing feature first - not just unit test cases."

GOAL
----
Write a detailed M1 implementation plan with task breakdown, test strategy, and progress tracking, then begin implementing Nexus M1 (Foundation: "It talks, it remembers, it recovers") on current Civitas APIs.

WORK COMPLETED
--------------
- I onboarded to the civitas-io ecosystem by reading AGENTS.md, PRD, architecture, design docs from python-civitas, presidium, presidium-examples, and context repos
- I created the governed coding agent example in presidium-examples (branch: example/governed-coding-agent, committed)
- I designed the eval framework + DeepEval integration for presidium (committed to main, not pushed)
- I wrote ADR-002 (language choice for Presidium) in civitas-io/context (committed AND pushed to remote)
- I added IDEA-01 (searchable ToolRegistry) to context/known-issues.md (committed, not pushed)
- I created the Nexus repo from scratch at /Users/jeryn/workspace/projects/nexus with 16 commits:
  - Phase 1 (Vision): AGENTS.md, PRD (12 features F1-F12), competitive analysis (OpenClaw/Hermes/Nanobot/NanoClaw/IronClaw), milestone plan (M1-M6), default persona
  - Phase 2 (Architecture): overview with supervision tree, multi-tenant model, three-layer memory with skill execution engine, 4 SVG diagrams
  - Phase 2.5 (Design): 5 design docs (conversation, transport, persona, scheduler, integrations)
  - Gap analysis commit: added context compression, heartbeat, risk-based approval, native apps/animated avatar from competitor analysis
- I verified ALL Civitas API signatures from actual source code (process.py, genserver.py, supervisor.py, runtime.py, messages.py, gateway/core.py)
- I researched AgentGateway as LLM routing alternative to LiteLLM — Rust single binary, OpenAI-compatible proxy, native failover + MCP gateway

CURRENT STATE
-------------
- Nexus repo: 16 commits, 29 files, all documentation complete, NO implementation code yet
- All repos clean (no uncommitted changes)
- python-civitas cloned fresh at /Users/jeryn/workspace/projects/python-civitas/
- Nexus NOT pushed to any remote yet (no GitHub repo created)
- presidium: 3 unpushed commits (eval framework redesign)
- presidium-examples: 1 unpushed commit on branch example/governed-coding-agent
- context: 1 unpushed commit (IDEA-01 searchable ToolRegistry)

PENDING TASKS
-------------
- Write detailed M1 implementation plan with task breakdown and test strategy
- Update AGENTS.md key decision: replace ModelRouter(AgentProcess) with AgentGateway sidecar
- Create GitHub repo (jerynmathew/nexus) and push
- Implement M1.1 through M1.8 (Foundation milestone)
- Push unpushed commits in presidium, presidium-examples, context repos (when user approves)

KEY FILES
---------
- nexus/AGENTS.md - Project reference, 14 key decisions, 7 anti-patterns, repo layout
- nexus/docs/vision/prd.md - PRD with 12 features (F1-F12), resolved questions, architecture
- nexus/docs/vision/milestones.md - M1-M6 milestone plan with exit criteria
- nexus/docs/architecture/overview.md - Supervision tree, message flows, Civitas integration points
- nexus/docs/architecture/memory.md - Three-layer memory + skill execution engine with parallel support
- nexus/docs/design/conversation.md - ConversationManager: session lifecycle, tool-use loop, governance hooks
- nexus/docs/design/integrations.md - MCP manager, tool filtering, custom agents, governance parity
- nexus/docs/design/transport.md - BaseTransport protocol with media handling
- python-civitas/civitas/process.py - AgentProcess API (verified: handle, send, ask, reply, checkpoint)
- python-civitas/civitas/genserver.py - GenServer API (verified: handle_call, handle_cast, handle_info, send_after)

IMPORTANT DECISIONS
-------------------
- Skills + MCP are the norm, custom agents are the exception (decision #14)
- Morning briefing is a skill (SKILL.md), not hardcoded agents — skills support parallel execution via asyncio.TaskGroup
- AgentGateway (Rust single binary) replaces custom ModelRouter — ConversationManager talks to http://localhost:4000 via OpenAI-compatible client
- Anthropic as primary LLM, with AgentGateway providing failover to OpenAI/Gemini (free tier) and local LLMs
- Single-tenant first, multi-tenant model designed in from day one
- FTS5 for memory search (zero-dependency), vector search as optional future extra
- Context compression essential for daily-driver use (M2.6)
- Risk-based tool approval in governance (low/medium/high classification + hardline blocklist)
- Proactive heartbeat as a default skill, not hardcoded agent
- Skill persistence: filesystem (primary) + SQLite (backup) + optional git export
- Persona: SOUL.md is per-persona (shared), USER.md is per-tenant (private), neither git-tracked at runtime
- ToolRegistryServer should be a GenServer service, not a library call (IDEA-01 in context repo)

EXPLICIT CONSTRAINTS
--------------------
- "no code is complete without test code. Focus on testing feature first - not just unit test cases."
- "simplicity is king here. Custom agents are the exception, not the norm."
- "DO NOT Push to remote yet"
- "Im not a big fan of litellm, agentgateway single binary deployment looks attractive"
- "Single first. Multi tenant later"
- "Anthropic first"
- "No assumptions, research APIs and interfaces first"
- Civitas conventions: uv, ruff, mypy strict, pytest-asyncio, 85% coverage, Google docstrings

CONTEXT FOR CONTINUATION
------------------------
- The user (Jeryn) is the creator of civitas-io. He built Vigil (predecessor to Nexus) on an earlier version of Civitas called "Agency". Vigil reached M4.4 with full functionality.
- Nexus is a fresh start on current Civitas + Presidium governance, incorporating lessons from Vigil (22 bugs found and fixed) and competitive analysis of OpenClaw (370K stars), Hermes (138K), Nanobot (42K), NanoClaw (29K), IronClaw (12K).
- AgentGateway changes the M1 architecture: instead of a ModelRouter(AgentProcess), we use AgentGateway as a Docker sidecar. The AGENTS.md key decision #12 needs updating.
- The M1 build order should be: scaffolding → persona → memory → tenant → transport → conversation manager → supervision → docker. ConversationManager (M1.6) should be split into 4 sub-tasks.
- GenServer note: self.llm and self.tools are None on GenServer — it explicitly doesn't inject LLM providers. Use it for DashboardServer and ToolRegistryServer only.
- Topology YAML uses lowercase strategy strings ("one_for_one" not "ONE_FOR_ONE")
- The user wants the "Dross" persona for the assistant (witty, direct, opinionated)
- M6 includes animated avatar + voice-first interaction ("Dross mode") — low priority but scoped
- Four repos to track: nexus (main work), presidium (eval docs), presidium-examples (coding agent), context (ADRs + ideas)

CIVITAS API SIGNATURES (VERIFIED FROM SOURCE)
----------------------------------------------
- AgentProcess.__init__(name, mailbox_size=1000, max_retries=3, shutdown_timeout=30.0)
- handle(self, message: Message) -> Message | None
- on_start(self) -> None, on_stop(self) -> None, on_error(self, error: Exception, message: Message) -> ErrorAction
- send(self, recipient: str, payload: dict, message_type: str = "message") -> None
- ask(self, recipient: str, payload: dict, message_type: str = "message", timeout: float = 30.0) -> Message
- broadcast(self, pattern: str, payload: dict) -> None
- reply(self, payload: dict) -> Message [NOT async — returns Message directly]
- checkpoint(self) -> None [saves self.state to StateStore]
- Injected attrs: self.llm (ModelProvider|None), self.tools (ToolRegistry|None), self.store (StateStore|None), self.state (dict), self.name (str)
- GenServer: subclasses AgentProcess, override init() not on_start(), handle_call(payload, from_) -> dict, handle_cast(payload) -> None, handle_info(payload) -> None, send_after(delay_ms, payload)
- GenServer: self.llm and self.tools are explicitly None — no LLM injection
- Supervisor(name, children, strategy="ONE_FOR_ONE", max_restarts=3, restart_window=60.0, backoff="CONSTANT", backoff_base=1.0, backoff_max=60.0)
- Runtime(supervisor, transport="in_process", model_provider=None, tool_registry=None, state_store=None, ...)
- Runtime.from_config(path, agent_classes=None) — resolves dotted paths or explicit class map
- HTTPGateway(name, GatewayConfig(port=8080)) — subclasses AgentProcess
- Message dataclass: id, type, sender, recipient, payload, correlation_id, reply_to, timestamp, trace_id, span_id, parent_span_id, attempt, ttl, priority
- Topology YAML: strategy lowercase ("one_for_one"), children as list of {agent: {name, type}} or {supervisor: {...}}

AGENTGATEWAY RESEARCH
---------------------
- Repository: github.com/agentgateway/agentgateway (Apache 2.0, Linux Foundation project)
- Rust single binary (~52MB), <100ms startup, ~50MB memory
- OpenAI-compatible proxy on port 4000, built-in UI on port 15000
- Supports: OpenAI, Anthropic, Gemini, Vertex, Bedrock, Azure, Ollama, vLLM, llama.cpp, LM Studio
- Native failover with health checks + eviction (unhealthy backend evicted for configurable duration)
- Per-request model selection via headers or body-based CEL expressions
- Rate limiting: local (per-instance) and remote (distributed via Ratelimit service)
- Token counting + cost tracking via OTEL
- Native MCP gateway: stdio, HTTP, SSE transports, tool federation, OAuth auth
- Docker: docker run cr.agentgateway.dev/agentgateway:v1.2.0-alpha.2
- Config: YAML with $ENV_VAR substitution
- Replaces need for custom ModelRouter(AgentProcess) — simpler, more capable, production-grade
