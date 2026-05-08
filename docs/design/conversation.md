# Design: ConversationManager

> The central routing agent — transport handling, sessions, LLM calls, skill execution, governance.

**Status:** Draft
**Module:** `src/nexus/agents/conversation.py`
**Type:** `AgentProcess`
**Supervisor:** root (ONE_FOR_ALL)

---

## Responsibility

ConversationManager is the only agent that touches user-facing I/O. It owns:

- Receiving `InboundMessage` from transports
- Tenant resolution and permission checking
- Intent classification (via IntentClassifier protocol)
- Session management (stateful multi-turn conversations)
- LLM calls (via ModelRouter)
- MCP tool-use loop
- Skill execution (sequential and parallel)
- Persona + user context injection into system prompt
- Governance hooks (policy check, trust update, audit)
- Dispatching replies back via `reply_transport`

It does **not** own: LLM provider selection (ModelRouter), memory persistence (MemoryAgent), cron scheduling (SchedulerAgent), or dashboard state (DashboardServer).

---

## Message Handling

```python
class ConversationManager(AgentProcess):

    async def handle(self, message: Message) -> Message | None:
        action = message.payload.get("action")

        if action == "inbound_message":
            return await self._handle_inbound(message)
        elif action == "execute_skill":
            return await self._handle_skill_trigger(message)
        elif action == "callback":
            return await self._handle_transport_callback(message)
        else:
            logger.warning("Unknown action: %s", action)
            return None
```

Three entry points:
1. **`inbound_message`** — user sent a message via transport (Telegram, etc.)
2. **`execute_skill`** — SchedulerAgent triggered a scheduled skill
3. **`callback`** — user tapped an inline button (approve/reject/edit)

---

## Inbound Message Flow

```python
async def _handle_inbound(self, message: Message) -> None:
    inbound = InboundMessage.from_payload(message.payload)

    # 1. Resolve tenant
    tenant = await self._resolve_tenant(inbound)
    if tenant is None:
        await inbound.reply_transport.send_text(
            inbound.channel_id, "Sorry, you're not authorized."
        )
        return

    # 2. Check rate limit
    if not self._check_rate_limit(tenant):
        return

    # 3. Classify intent
    intent = await self._classify(inbound.text, tenant)

    # 4. Load or create session
    session = await self._get_or_create_session(tenant, inbound)

    # 5. Check permissions
    if intent.target_service and not self._check_permission(tenant, intent):
        await self._reply(inbound, f"You don't have permission for {intent.target_service}.")
        return

    # 6. Execute
    if intent.is_skill_request:
        await self._execute_skill_by_name(intent.skill_name, tenant, inbound)
    else:
        await self._llm_respond(session, tenant, inbound, intent)

    # 7. Persist
    await self._persist_messages(tenant, inbound.text, response_text)
    await self._checkpoint_session(session)
```

---

## Session Lifecycle

```
Created (first message, no active session)
    │
    ▼
Active (messages appended, context loaded per LLM call)
    │
    ├── each turn: checkpointed to MemoryAgent (survives crash)
    │
    ▼
Idle timeout (30 min, configurable)
    │
    ▼
Expired → Dream consolidation (async):
    ├── LLM summarizes full history
    ├── Summary → conversations table
    ├── Facts extracted → memories table
    └── Session status → completed
```

```python
@dataclass
class Session:
    session_id: str
    tenant_id: str
    messages: list[dict]          # conversation history
    status: str                   # active | expired | completed
    started_at: float
    last_activity: float

    def to_dict(self) -> dict: ...

    @classmethod
    def from_dict(cls, data: dict) -> Session: ...
```

**Deferred restore:** Sessions are NOT restored in `on_start()` (MessageBus not ready). On first message per tenant, ConversationManager checks MemoryAgent for an active session and restores if found.

---

## Intent Classification

```python
class Intent(BaseModel, frozen=True):
    target_service: str | None     # "gmail", "calendar", None (general)
    action: str | None             # "read", "create", "send", None
    skill_name: str | None         # "morning-briefing", None
    is_stateful: bool              # multi-turn conversation needed?
    is_skill_request: bool         # explicitly requesting a skill?
    tool_groups: list[str]         # MCP tool groups to load
    confidence: float              # 0.0-1.0

class IntentClassifier(Protocol):
    async def classify(self, text: str, tenant: TenantContext) -> Intent: ...
```

**Implementations:**

| Classifier | When | Cost | Accuracy |
|---|---|---|---|
| `RegexClassifier` | M1 | Zero | ~80% for explicit keywords |
| `LLMClassifier` | M2+ | ~$0.001/call (Haiku) | ~95% zero-shot |
| `HybridClassifier` | M3+ | Zero for obvious, Haiku for ambiguous | ~98% |

Regex handles "check my email", "what's on my calendar". Misses fall through to LLM path — still works, just costs more tokens (full tool schema sent).

---

## LLM Response Flow

```python
async def _llm_respond(
    self, session: Session, tenant: TenantContext,
    inbound: InboundMessage, intent: Intent,
) -> str:
    # 1. Build system prompt
    system = await self._build_system_prompt(tenant, intent)

    # 2. Filter MCP tools by intent
    tools = self._mcp.filter_tools(intent.tool_groups) if intent.tool_groups else self._mcp.all_tools

    # 3. Build message history
    messages = self._build_messages(session, inbound.text)

    # 4. Get model for this task type
    model = await self.ask("llm_router", {"action": "select", "task": "CONVERSE"})

    # 5. Tool-use loop
    response = await self._tool_use_loop(messages, tools, model, tenant)

    # 6. Governance: check for approval-required actions
    if self._requires_approval(response):
        await self._request_approval(inbound, response, tenant)
        return  # wait for callback

    # 7. Reply
    await self._reply(inbound, response.content)
    return response.content
```

---

## Tool-Use Loop

```python
async def _tool_use_loop(
    self, messages: list, tools: list, model: str,
    tenant: TenantContext, max_iterations: int = 5,
) -> LLMResponse:
    response = None

    for i in range(max_iterations):
        response = await self._llm_chat(model, messages, tools)

        if not response.tool_calls:
            break

        for tc in response.tool_calls:
            # Governance: policy check before execution
            policy = await self._check_policy(tenant, tc.name, tc.input)
            if policy.decision == "DENY":
                tool_result = f"Denied by policy: {policy.reason}"
                await self._audit("tool_denied", tenant, tc, policy)
            elif policy.decision == "REQUIRE_APPROVAL":
                # Defer — will be handled by approval flow
                return self._pending_approval_response(tc, policy)
            else:
                tool_result = await self._mcp.call_tool(tc.name, tc.input)
                await self._audit("tool_executed", tenant, tc)

            messages.append({"role": "tool", "tool_call_id": tc.id, "content": str(tool_result)})

        messages.append({"role": "assistant", "content": response.content, "tool_calls": response.tool_calls})

    if response is None:
        return LLMResponse(content="I couldn't complete that request.")

    return response
```

**Key behaviors:**
- Max 5 iterations (prevent infinite tool loops)
- Policy check before every tool call (Presidium governance hook)
- DENY → tool call blocked, result substituted with denial reason
- REQUIRE_APPROVAL → conversation paused, user prompted via transport inline buttons
- ALLOW → tool call executes via MCP
- Every tool call audited (agent, tool, input, policy decision)

---

## Skill Execution

```python
async def _execute_skill(self, skill: Skill, tenant: TenantContext,
                          inbound: InboundMessage | None = None) -> None:
    tools = self._mcp.filter_tools(skill.tool_groups)
    reply_fn = self._reply_to(inbound) if inbound else self._send_to_tenant(tenant)

    if skill.execution == "parallel" and skill.sections:
        results: dict[str, str] = {}
        async with asyncio.TaskGroup() as tg:
            for section in skill.sections:
                tg.create_task(
                    self._execute_section(section, tenant, tools, results)
                )
        for section_name in skill.section_order:
            content = results.get(section_name, f"⚠ {section_name}: no result")
            await reply_fn(content)
    else:
        response = await self._tool_use_loop(
            messages=[{"role": "user", "content": skill.full_prompt}],
            tools=tools,
            model=await self._get_model("SKILL_EXEC"),
            tenant=tenant,
        )
        await reply_fn(response.content)

async def _execute_section(
    self, section: SkillSection, tenant: TenantContext,
    tools: list, results: dict[str, str],
) -> None:
    try:
        async with asyncio.timeout(section.timeout):
            response = await self._tool_use_loop(
                messages=[{"role": "user", "content": section.content}],
                tools=tools,
                model=await self._get_model("SKILL_EXEC"),
                tenant=tenant,
            )
            results[section.name] = response.content
    except TimeoutError:
        results[section.name] = f"⚠ {section.name}: timed out"
    except Exception as exc:
        results[section.name] = f"⚠ {section.name}: unavailable ({exc})"
```

---

## Governance Integration Points

| Hook | Where | What happens |
|---|---|---|
| **Permission check** | `_handle_inbound`, after intent classification | Verifies tenant has `{service}.{level}` permission |
| **Policy check** | `_tool_use_loop`, before each tool call | Evaluates ALLOW/DENY/REQUIRE_APPROVAL |
| **Approval flow** | `_tool_use_loop`, on REQUIRE_APPROVAL | Pauses execution, sends inline buttons to transport |
| **Approval callback** | `_handle_transport_callback` | Resumes tool call if approved, logs denial if rejected |
| **Trust update** | `_handle_transport_callback`, after approval/rejection | +delta on approve, -delta on reject |
| **Audit entry** | `_tool_use_loop`, after every tool call or denial | Agent, tool, input, policy decision, timestamp |
| **Intent declaration** | `_llm_respond`, at start of task | Declares scope — undeclared tool calls trigger alert |

---

## System Prompt Assembly

```python
async def _build_system_prompt(self, tenant: TenantContext, intent: Intent) -> str:
    parts = []

    # 1. Persona identity (SOUL.md)
    parts.append(await self._load_persona(tenant.persona_name))

    # 2. User context (USER.md)
    user_md = await self._load_user_context(tenant)
    if user_md:
        parts.append(f"# About the user\n\n{user_md}")

    # 3. Relevant memories (FTS5 search)
    memories = await self.ask("memory", {
        "action": "search", "tenant_id": tenant.tenant_id,
        "query": intent.original_text, "limit": 10,
    })
    if memories.payload.get("results"):
        parts.append(self._format_memories(memories.payload["results"]))

    # 4. Relevant skills (on-demand)
    if intent.skill_name:
        skill_content = self._skills.load_skill(intent.skill_name)
        parts.append(f"# Active Skill\n\n{skill_content}")
    else:
        skills_index = self._skills.build_skills_summary()
        if skills_index:
            parts.append(f"# Available Skills\n\n{skills_index}")

    # 5. Account/profile hints
    account_hints = self._build_account_hints(tenant)
    if account_hints:
        parts.append(account_hints)

    # 6. Recent session history (last N messages)
    # Handled in _build_messages(), not in system prompt

    return "\n\n---\n\n".join(parts)
```

**Token budget:** System prompt targets ~4K tokens max. If the combined parts exceed this, oldest memories and least-relevant skills are truncated.

---

## Alternatives Considered

1. **LLM calls in each integration agent** — Rejected. Duplicated prompt engineering, harder cost control, inconsistent persona. ConversationManager as single LLM caller is a deliberate design choice from Vigil.

2. **Session state in MemoryAgent only** — Rejected for latency. In-memory cache with periodic checkpoint gives sub-ms session access. Pure DB would add ~5ms per message.

3. **Separate SkillExecutor agent** — Considered but rejected for simplicity. Skills run inside ConversationManager's context — they need the same LLM, MCP, persona, and governance hooks. A separate agent would duplicate all of this.

4. **Transport-specific handlers in ConversationManager** — Rejected. Transport abstraction (`BaseTransport` + `InboundMessage`) ensures ConversationManager never imports telegram-specific code.
