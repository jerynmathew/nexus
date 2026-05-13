from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import uuid
from pathlib import Path
from typing import Any

from civitas.messages import Message
from civitas.process import AgentProcess

from nexus.agents.compressor import ContextCompressor
from nexus.agents.intent import Intent, RegexClassifier
from nexus.config import DashboardConfig
from nexus.dashboard.views import ContentStore
from nexus.extensions import CommandHandler, SignalHandler
from nexus.governance.audit import AuditEntry, AuditSink
from nexus.governance.policy import PolicyDecision, PolicyEngine
from nexus.governance.trust import TrustStore, tool_category
from nexus.llm.client import LLMClient, LLMResponse
from nexus.mcp.manager import MCPManager
from nexus.media.handler import MediaHandler
from nexus.models.session import Session
from nexus.models.tenant import TenantContext
from nexus.persona.loader import PersonaLoader
from nexus.ratelimit import RateLimiter
from nexus.skills.manager import SkillManager
from nexus.skills.parser import Skill

logger = logging.getLogger(__name__)

_MAX_TOOL_ITERATIONS = 5
_LONG_RESPONSE_THRESHOLD = 2000


class ConversationManager(AgentProcess):
    def __init__(
        self,
        name: str,
        llm_base_url: str = "http://localhost:4000",
        llm_api_key: str = "",
        llm_model: str = "claude-sonnet-4-20250514",
        llm_cheap_model: str = "claude-haiku-4-20250414",
        llm_max_tokens: int = 4096,
        personas_dir: str = "personas",
        users_dir: str = "data/users",
        skills_dir: str = "skills",
        audit_path: str = "data/audit.jsonl",
        **kwargs: Any,
    ) -> None:
        super().__init__(name, **kwargs)
        self._llm_base_url = llm_base_url
        self._llm_api_key = llm_api_key
        self._llm_model = llm_model
        self._llm_cheap_model = llm_cheap_model
        self._llm_max_tokens = llm_max_tokens
        self._personas_dir = personas_dir
        self._users_dir = users_dir
        self._skills_dir = skills_dir
        self._audit_path = audit_path

        self._llm: LLMClient | None = None
        self._persona_loader: PersonaLoader | None = None
        self._classifier = RegexClassifier()
        self._mcp: MCPManager | None = None
        self._policy = PolicyEngine()
        self._audit = AuditSink(audit_path)
        self._trust = TrustStore()
        self._skill_manager: SkillManager | None = None
        self._compressor = ContextCompressor()
        self._content_store: ContentStore | None = None
        self._dashboard_config: DashboardConfig | None = None
        self._media_handler: MediaHandler | None = None
        self._sessions: dict[str, Session] = {}
        self._pending_approvals: dict[str, dict[str, Any]] = {}
        self._transport: Any = None
        self._ext_commands: dict[str, CommandHandler] = {}
        self._ext_signal_handlers: dict[str, list[SignalHandler]] = {}
        self._nexus_context: Any = None
        self._rate_limiter = RateLimiter()

    async def on_start(self) -> None:
        self._llm = LLMClient(
            base_url=self._llm_base_url,
            api_key=self._llm_api_key,
            default_model=self._llm_model,
            cheap_model=self._llm_cheap_model,
        )
        self._persona_loader = PersonaLoader(
            personas_dir=Path(self._personas_dir),
            users_dir=Path(self._users_dir),
        )
        self._skill_manager = SkillManager(Path(self._skills_dir))
        self._mcp = MCPManager()

    async def on_stop(self) -> None:
        if self._llm:
            await self._llm.close()
            self._llm = None
        if self._mcp:
            await self._mcp.close()
            self._mcp = None

    def set_transport(self, transport: Any) -> None:
        self._transport = transport

    def set_mcp_manager(self, mcp: MCPManager) -> None:
        self._mcp = mcp

    def set_content_store(
        self,
        store: ContentStore,
        config: DashboardConfig,
    ) -> None:
        self._content_store = store
        self._dashboard_config = config

    def set_media_handler(self, handler: MediaHandler) -> None:
        self._media_handler = handler

    def register_ext_commands(
        self,
        commands: dict[str, CommandHandler],
        nexus_context: Any = None,
    ) -> None:
        self._ext_commands.update(commands)
        if nexus_context is not None:
            self._nexus_context = nexus_context

    def register_ext_signal_handlers(self, handlers: dict[str, list[SignalHandler]]) -> None:
        for event_type, handler_list in handlers.items():
            self._ext_signal_handlers.setdefault(event_type, []).extend(handler_list)

    async def handle(self, message: Message) -> Message | None:
        action = message.payload.get("action")
        handler = self._get_action_handler(action)
        if handler:
            result: Message | None = await handler(message)
            return result
        logger.warning("[%s] Unknown action: %s", self.name, action)
        return None

    def _get_action_handler(
        self,
        action: str | None,
    ) -> Any | None:
        handlers: dict[str, Any] = {
            "inbound_message": self._handle_inbound,
            "execute_skill": self._handle_skill_trigger,
            "callback": self._handle_transport_callback,
            "command": self._handle_command,
            "mcp_health_check": self._handle_mcp_health,
            "status": self._handle_status,
        }
        return handlers.get(action or "")

    async def _handle_mcp_health(self, message: Message) -> Message | None:
        await self._report_mcp_health()
        return None

    async def _handle_status(self, message: Message) -> Message | None:
        return self.reply(
            {
                "status": "running",
                "active_sessions": len(self._sessions),
            }
        )

    async def _handle_inbound(self, message: Message) -> Message | None:
        payload = message.payload
        tenant_id = payload.get("tenant_id")
        text = payload.get("text", "")
        channel_id = payload.get("channel_id", "")
        media_type = payload.get("media_type")

        if not tenant_id:
            return None

        if not self._rate_limiter.check(tenant_id):
            remaining = self._rate_limiter.remaining(tenant_id)
            logger.warning("Rate limited tenant %s (%d remaining)", tenant_id, remaining)
            await self._send_reply(
                channel_id, "You're sending messages too fast. Please wait a moment."
            )
            return None

        tenant = await self._resolve_tenant(tenant_id)
        if tenant is None:
            await self._send_reply(channel_id, "Sorry, you're not authorized.")
            return None

        if media_type and self._media_handler:
            text = await self._process_media(payload, text)

        intent = await self._classifier.classify(text, tenant)
        session = await self._get_or_create_session(tenant)

        if intent.target_service and not tenant.check_action_permission(
            intent.target_service,
            intent.action or "read",
        ):
            await self._send_reply(
                channel_id,
                f"You don't have permission for {intent.target_service}.",
            )
            return None

        await self._send_typing(channel_id)

        try:
            response_text = await self._llm_respond(session, tenant, text, intent)
        except Exception as exc:
            logger.error("[%s] LLM call failed: %s", self.name, exc)
            response_text = "Sorry, I'm having trouble connecting right now. Try again in a moment."

        session.add_message("user", text)
        session.add_message("assistant", response_text)
        await self._persist_message(session.session_id, "user", text)
        await self._persist_message(session.session_id, "assistant", response_text)
        await self._checkpoint_session(session)
        await self._send_response_with_viewer(channel_id, response_text)
        await self._report_activity(tenant_id, text)
        await self._fire_signal_handlers("inbound_message", payload)
        return None

    async def _resolve_tenant(self, tenant_id: str) -> TenantContext | None:
        try:
            result = await self.ask(
                "memory",
                {
                    "action": "resolve_tenant",
                    "transport": "_direct",
                    "transport_user_id": tenant_id,
                },
            )
            if result.payload.get("tenant_id"):
                persona_result = await self.ask(
                    "memory",
                    {
                        "action": "get_tenant_persona",
                        "tenant_id": result.payload["tenant_id"],
                    },
                )
                return TenantContext(
                    tenant_id=result.payload["tenant_id"],
                    name=result.payload.get("name", tenant_id),
                    role=result.payload.get("role", "user"),
                    timezone=result.payload.get("timezone", "UTC"),
                    persona_name=persona_result.payload.get("persona_name", "default"),
                )
        except Exception:
            logger.debug(
                "[%s] Tenant resolution via memory failed for %s",
                self.name,
                tenant_id,
            )
        return TenantContext(tenant_id=tenant_id, name=tenant_id, role="admin")

    async def _get_or_create_session(self, tenant: TenantContext) -> Session:
        if tenant.tenant_id in self._sessions:
            return self._sessions[tenant.tenant_id]

        try:
            result = await self.ask(
                "memory",
                {
                    "action": "get_active_session",
                    "tenant_id": tenant.tenant_id,
                },
            )
            if result.payload.get("session_id"):
                checkpoint = result.payload.get("checkpoint")
                session = (
                    Session.from_dict(checkpoint)
                    if checkpoint
                    else Session(
                        session_id=result.payload["session_id"],
                        tenant_id=tenant.tenant_id,
                    )
                )
                self._sessions[tenant.tenant_id] = session
                return session
        except Exception:
            logger.debug("[%s] Session restore failed for %s", self.name, tenant.tenant_id)

        session_id = str(uuid.uuid4())
        try:
            await self.ask(
                "memory",
                {
                    "action": "create_session",
                    "tenant_id": tenant.tenant_id,
                    "session_id": session_id,
                },
            )
        except Exception:
            logger.debug("[%s] Session creation in memory failed", self.name)

        session = Session(session_id=session_id, tenant_id=tenant.tenant_id)
        self._sessions[tenant.tenant_id] = session
        return session

    async def _llm_respond(
        self,
        session: Session,
        tenant: TenantContext,
        text: str,
        intent: Intent,
    ) -> str:
        if not self._llm or not self._persona_loader:
            return "I'm not fully initialized yet. Please try again in a moment."

        system_prompt = await self._build_system_prompt(tenant, intent)
        messages = self._build_messages(session, text)

        if self._llm and self._compressor.needs_compression(messages):
            messages = await self._compressor.compress(messages, self._llm)
            logger.info("[%s] Context compressed for %s", self.name, tenant.tenant_id)

        tools = self._get_tools_for_intent(intent)
        response = await self._tool_use_loop(messages, system_prompt, tools, tenant)
        return response.content

    async def _build_system_prompt(self, tenant: TenantContext, intent: Intent) -> str:
        if not self._persona_loader:
            return ""

        parts: list[str] = [
            self._persona_loader.build_system_identity(
                persona_name=tenant.persona_for_profile(),
                tenant_id=tenant.tenant_id,
                tenant_name=tenant.name,
                timezone=tenant.timezone,
                role=tenant.role,
            ),
        ]

        try:
            memories_result = await self.ask(
                "memory",
                {
                    "action": "search",
                    "tenant_id": tenant.tenant_id,
                    "query": intent.original_text,
                    "limit": 10,
                },
            )
            results = memories_result.payload.get("results", [])
            if results:
                memory_lines = [f"- {r['key']}: {r['value']}" for r in results]
                parts.append("# Relevant Memories\n\n" + "\n".join(memory_lines))
        except Exception:
            pass

        if self._skill_manager:
            summary = self._skill_manager.build_summary()
            if summary:
                parts.append("# Available Skills\n\n" + summary)

        capabilities = self._build_capabilities_section()
        if capabilities:
            parts.append(capabilities)

        return "\n\n---\n\n".join(parts)

    def _build_capabilities_section(self) -> str:
        lines: list[str] = ["# Available Capabilities"]

        if self._mcp:
            tools = self._mcp.all_tool_schemas()
            if tools:
                lines.append(f"\nYou have {len(tools)} tools available via MCP.")
            else:
                lines.append("\nNo MCP tools currently connected.")
        else:
            lines.append(
                "\nNo MCP connection. You cannot access email, calendar, or external services.",
            )

        if self._media_handler:
            if self._media_handler.has_vision:
                lines.append("You can analyze images sent by the user.")
        else:
            lines.append("Voice and image processing are not available.")

        return "\n".join(lines)

    def _build_messages(self, session: Session, current_text: str) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        for msg in session.messages[-20:]:
            messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": current_text})
        return messages

    def _get_tools_for_intent(self, intent: Intent) -> list[dict[str, Any]] | None:
        if not self._mcp:
            return None
        if intent.tool_groups:
            tools = self._mcp.filter_tools(intent.tool_groups)
            if tools:
                logger.info(
                    "[%s] Filtered %d tools for groups %s",
                    self.name,
                    len(tools),
                    intent.tool_groups,
                )
                return tools
        all_tools = self._mcp.all_tool_schemas()
        return all_tools if all_tools else None

    async def _tool_use_loop(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str,
        tools: list[dict[str, Any]] | None,
        tenant: TenantContext,
    ) -> LLMResponse:
        if not self._llm:
            return LLMResponse(content="LLM client not initialized.")

        response: LLMResponse | None = None

        for _i in range(_MAX_TOOL_ITERATIONS):
            response = await self._llm.chat(
                messages=messages,
                system=system_prompt,
                tools=tools,
                max_tokens=self._llm_max_tokens,
            )

            if not response.tool_calls:
                break

            for tc in response.tool_calls:
                tool_result = await self._execute_tool_with_governance(
                    tc.name,
                    tc.input,
                    tenant,
                )
                messages.append(
                    {
                        "role": "assistant",
                        "content": response.content or "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.name,
                                    "arguments": json.dumps(tc.input),
                                },
                            }
                        ],
                    }
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": tool_result,
                    }
                )

        if response is None:
            return LLMResponse(content="I couldn't complete that request.")
        return response

    async def _execute_tool_with_governance(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        tenant: TenantContext,
    ) -> str:
        category = tool_category(tool_name)
        trust_score = self._trust.get_score(tenant.tenant_id, category)
        decision = self._policy.check(tool_name, arguments, trust_score=trust_score)

        self._audit.log(
            AuditEntry(
                agent=self.name,
                tenant_id=tenant.tenant_id,
                tool_name=tool_name,
                arguments_summary=AuditSink.summarize_arguments(arguments),
                decision=decision.value,
                detail=f"trust={trust_score:.2f}",
            )
        )

        if decision == PolicyDecision.DENY:
            self._trust.update_score(tenant.tenant_id, category, -0.15)
            return f"Action '{tool_name}' is not allowed (trust: {trust_score:.2f})."

        if decision == PolicyDecision.REQUIRE_APPROVAL:
            logger.info("[%s] Tool '%s' requires approval", self.name, tool_name)

        if not self._mcp:
            return f"Tool '{tool_name}' is not available (no MCP connection)."

        return await self._mcp.call_tool(tool_name, arguments)

    async def _handle_skill_trigger(self, message: Message) -> Message | None:
        skill_name = message.payload.get("skill_name")
        tenant_id = message.payload.get("tenant_id")

        if not skill_name or not tenant_id or not self._skill_manager:
            return None

        skill = self._skill_manager.get(skill_name)
        if not skill:
            logger.warning("[%s] Skill '%s' not found", self.name, skill_name)
            return None

        tenant = await self._resolve_tenant(tenant_id)
        if tenant is None:
            return None

        channel_id = message.payload.get("channel_id", "")
        await self._execute_skill(skill, tenant, channel_id)
        return None

    async def _execute_skill(
        self,
        skill: Skill,
        tenant: TenantContext,
        channel_id: str,
    ) -> None:
        if not self._llm:
            return

        tools = self._get_tools_for_intent(
            Intent(tool_groups=skill.tool_groups, original_text=skill.name),
        )
        model = self._llm.resolve_model(task="SKILL_EXEC", skill_model=skill.model)

        if skill.execution == "parallel" and skill.sections:
            await self._execute_skill_parallel(skill, tenant, channel_id, tools, model)
        else:
            await self._execute_skill_sequential(skill, tenant, channel_id, tools, model)

    async def _execute_skill_parallel(
        self,
        skill: Skill,
        tenant: TenantContext,
        channel_id: str,
        tools: list[dict[str, Any]] | None,
        model: str,
    ) -> None:
        if not self._llm:
            return

        results: dict[str, str] = {}

        llm = self._llm

        async def run_section(
            section_name: str,
            section_content: str,
            section_timeout: int,
        ) -> None:
            try:
                async with asyncio.timeout(section_timeout):
                    resp = await llm.chat(
                        messages=[{"role": "user", "content": section_content}],
                        model=model,
                        tools=tools,
                    )
                    results[section_name] = resp.content
            except TimeoutError:
                results[section_name] = f"⚠ {section_name}: timed out"
            except Exception as exc:
                results[section_name] = f"⚠ {section_name}: unavailable ({exc})"

        async with asyncio.TaskGroup() as tg:
            for section in skill.sections:
                tg.create_task(
                    run_section(section.name, section.content, section.timeout),
                )

        for section in skill.sections:
            content = results.get(section.name, f"⚠ {section.name}: no result")
            await self._send_reply(channel_id, f"**{section.name}**\n\n{content}")

    async def _execute_skill_sequential(
        self,
        skill: Skill,
        tenant: TenantContext,
        channel_id: str,
        tools: list[dict[str, Any]] | None,
        model: str,
    ) -> None:
        if not self._llm:
            return

        resp = await self._llm.chat(
            messages=[{"role": "user", "content": skill.content}],
            model=model,
            tools=tools,
        )
        if resp.content.strip() == "HEARTBEAT_OK":
            logger.info("[%s] Heartbeat: nothing actionable", self.name)
            return
        await self._send_response_with_viewer(channel_id, resp.content)

    async def _handle_transport_callback(self, message: Message) -> Message | None:
        callback_data = message.payload.get("callback_data", "")
        tenant_id = message.payload.get("tenant_id", "")
        channel_id = message.payload.get("channel_id", "")

        if callback_data.startswith("approve:"):
            approval_id = callback_data.removeprefix("approve:")
            pending = self._pending_approvals.pop(approval_id, None)
            if pending:
                t_name = pending.get("tool_name", "")
                category = tool_category(t_name)
                self._trust.update_score(tenant_id, category, +0.05)
                self._audit.log(
                    AuditEntry(
                        agent=self.name,
                        tenant_id=tenant_id,
                        tool_name=t_name,
                        decision="APPROVED",
                    )
                )
                score = self._trust.get_score(tenant_id, category)
                await self._send_reply(
                    channel_id,
                    f"✅ Approved. ({category} trust: {score:.2f})",
                )
            return None

        if callback_data.startswith("reject:"):
            approval_id = callback_data.removeprefix("reject:")
            pending = self._pending_approvals.pop(approval_id, None)
            if pending:
                t_name = pending.get("tool_name", "")
                category = tool_category(t_name)
                self._trust.update_score(tenant_id, category, -0.10)
                self._audit.log(
                    AuditEntry(
                        agent=self.name,
                        tenant_id=tenant_id,
                        tool_name=t_name,
                        decision="REJECTED",
                    )
                )
                score = self._trust.get_score(tenant_id, category)
                await self._send_reply(
                    channel_id,
                    f"❌ Rejected. ({category} trust: {score:.2f})",
                )
            return None

        logger.warning("[%s] Unknown callback: %s", self.name, callback_data)
        return None

    async def _handle_command(self, message: Message) -> Message | None:
        payload = message.payload
        command = payload.get("command", "")
        args = payload.get("args", "")
        tenant_id = payload.get("tenant_id", "")
        channel_id = payload.get("channel_id", "")

        if command == "status":
            status_text = await self._build_status_report(tenant_id)
            await self._send_reply(channel_id, status_text)
            return None

        if command == "checkpoint":
            await self._handle_checkpoint(tenant_id, channel_id, args)
            return None

        if command == "rollback":
            await self._handle_rollback(tenant_id, channel_id, args)
            return None

        ext_handler = self._ext_commands.get(command)
        if ext_handler:
            await ext_handler(
                command=command,
                args=args,
                tenant_id=tenant_id,
                channel_id=channel_id,
                send_reply=self._send_reply,
                nexus_context=self._nexus_context,
            )
            return None

        await self._send_reply(channel_id, f"Unknown command: /{command}")
        return None

    async def _build_status_report(self, tenant_id: str) -> str:
        lines: list[str] = ["**Nexus Status**\n"]

        try:
            health = await self.ask("dashboard", {"action": "get_health"})
            h = health.payload
            lines.append(f"Health: {h.get('status', 'unknown')}")
            lines.append(f"Agents: {h.get('agent_count', 0)}")
            lines.append(f"Uptime: {int(h.get('uptime_seconds', 0)) // 60}m")
        except Exception:
            lines.append("Health: unavailable")

        if self._mcp:
            mcp_health = await self._mcp.health_check()
            for name, healthy in mcp_health.items():
                status = "connected" if healthy else "disconnected"
                lines.append(f"MCP {name}: {status}")
            lines.append(f"Tools: {len(self._mcp.all_tool_schemas())}")

        trust_scores = self._trust.get_all_scores(tenant_id)
        if trust_scores:
            lines.append("\n**Trust:**")
            for cat, score in sorted(trust_scores.items()):
                bar = "█" * int(score * 10) + "░" * (10 - int(score * 10))
                lines.append(f"  {cat}: {bar} {score:.2f}")

        lines.append(f"\nSessions: {len(self._sessions)}")
        lines.append(f"STT: {'enabled' if self._media_handler else 'disabled'}")

        return "\n".join(lines)

    async def _handle_checkpoint(
        self,
        tenant_id: str,
        channel_id: str,
        label: str,
    ) -> None:
        session = self._sessions.get(tenant_id)
        if not session:
            await self._send_reply(channel_id, "No active session to checkpoint.")
            return

        checkpoint_label = label.strip() or f"checkpoint-{len(session.messages)}"
        try:
            await self.send(
                "memory",
                {
                    "action": "config_set",
                    "tenant_id": tenant_id,
                    "namespace": "checkpoints",
                    "key": checkpoint_label,
                    "value": json.dumps(session.to_dict()),
                },
            )
            await self._send_reply(
                channel_id,
                f"✅ Checkpoint saved: `{checkpoint_label}`",
            )
        except Exception:
            await self._send_reply(channel_id, "Failed to save checkpoint.")
        return

    async def _handle_rollback(
        self,
        tenant_id: str,
        channel_id: str,
        label: str,
    ) -> None:
        label = label.strip()
        if not label:
            try:
                result = await self.ask(
                    "memory",
                    {
                        "action": "config_get_all",
                        "tenant_id": tenant_id,
                    },
                )
                checkpoints = result.payload.get("configs", {}).get("checkpoints", {})
                if not checkpoints:
                    await self._send_reply(channel_id, "No checkpoints available.")
                    return
                names = "\n".join(f"  `{k}`" for k in checkpoints)
                await self._send_reply(
                    channel_id,
                    f"Available checkpoints:\n{names}\n\nUse: /rollback <name>",
                )
            except Exception:
                await self._send_reply(channel_id, "Failed to list checkpoints.")
            return

        try:
            result = await self.ask(
                "memory",
                {
                    "action": "config_get",
                    "tenant_id": tenant_id,
                    "namespace": "checkpoints",
                    "key": label,
                },
            )
            value = result.payload.get("value")
            if not value:
                await self._send_reply(channel_id, f"Checkpoint `{label}` not found.")
                return

            session_data = json.loads(value)
            restored = Session.from_dict(session_data)
            self._sessions[tenant_id] = restored
            await self._checkpoint_session(restored)
            await self._send_reply(
                channel_id,
                f"✅ Rolled back to: `{label}`",
            )
        except Exception:
            await self._send_reply(channel_id, "Failed to rollback.")
        return

    async def _report_mcp_health(self) -> None:
        if not self._mcp:
            return
        with contextlib.suppress(Exception):
            health = await self._mcp.health_check()
            for name, healthy in health.items():
                await self.cast(
                    "dashboard",
                    {
                        "action": "mcp_status",
                        "server": name,
                        "connected": healthy,
                        "tool_count": len(self._mcp.filter_tools([name])),
                    },
                )

    async def _persist_message(self, session_id: str, role: str, content: str) -> None:
        try:
            await self.send(
                "memory",
                {
                    "action": "save_message",
                    "session_id": session_id,
                    "role": role,
                    "content": content,
                },
            )
        except Exception:
            logger.debug("[%s] Failed to persist message", self.name)

    async def _checkpoint_session(self, session: Session) -> None:
        try:
            await self.send(
                "memory",
                {
                    "action": "checkpoint_session",
                    "session_id": session.session_id,
                    "checkpoint": session.to_dict(),
                },
            )
        except Exception:
            logger.debug("[%s] Failed to checkpoint session", self.name)

    async def _send_reply(self, channel_id: str, text: str) -> None:
        if self._transport and hasattr(self._transport, "send_text"):
            try:
                await self._transport.send_text(channel_id, text)
            except Exception:
                logger.debug("[%s] Failed to send reply via transport", self.name)

    async def _send_response_with_viewer(
        self,
        channel_id: str,
        response_text: str,
    ) -> None:
        if (
            len(response_text) > _LONG_RESPONSE_THRESHOLD
            and self._content_store
            and self._dashboard_config
        ):
            view_id = self._content_store.store(response_text)
            host = self._dashboard_config.host
            port = self._dashboard_config.port
            view_url = f"http://{host}:{port}/view/{view_id}"
            tldr = response_text[:300].rsplit(" ", 1)[0] + "..."
            await self._send_reply(
                channel_id,
                f"{tldr}\n\nSee full details → {view_url}",
            )
        else:
            await self._send_reply(channel_id, response_text)

    async def _send_typing(self, channel_id: str) -> None:
        if self._transport and hasattr(self._transport, "send_typing"):
            with contextlib.suppress(Exception):
                await self._transport.send_typing(channel_id)

    async def _process_media(self, payload: dict[str, Any], text: str) -> str:
        if not self._media_handler:
            return text

        media_type = payload.get("media_type", "")
        media_bytes = payload.get("_media_bytes", b"")

        if media_type == "voice" and media_bytes:
            transcription = await self._media_handler.process_voice(media_bytes)
            logger.info("[%s] Voice transcribed: %s", self.name, transcription[:80])
            return transcription

        if media_type == "photo" and media_bytes:
            caption = payload.get("media_caption", "") or text
            description = await self._media_handler.process_image(media_bytes, caption)
            return f"{caption}\n\n[Image analysis: {description}]" if caption else description

        if media_type == "document" and media_bytes:
            filename = payload.get("metadata", {}).get("filename", "document")
            doc_text = await self._media_handler.process_document(media_bytes, filename)
            prefix = text or f"Document: {filename}"
            return f"{prefix}\n\n{doc_text[:10_000]}"

        if media_type == "video" and media_bytes:
            transcription, frames = await self._media_handler.process_video(media_bytes)
            parts = [text] if text else []
            if transcription:
                parts.append(f"[Video audio: {transcription}]")
            if frames and self._media_handler.has_vision:
                desc = await self._media_handler.process_image(frames[0])
                parts.append(f"[Video frame: {desc}]")
            return "\n\n".join(parts) if parts else "[Video received]"

        return text

    async def _fire_signal_handlers(self, event_type: str, payload: dict[str, Any]) -> None:
        handlers = self._ext_signal_handlers.get(event_type, [])
        for handler in handlers:
            try:
                await handler(payload)
            except Exception:
                logger.debug("[%s] Signal handler failed for %s", self.name, event_type)

    async def _report_activity(self, tenant_id: str, text: str) -> None:
        with contextlib.suppress(Exception):
            await self.cast(
                "dashboard",
                {
                    "action": "activity",
                    "agent": self.name,
                    "type": "inbound",
                    "detail": f"{tenant_id}: {text[:80]}",
                },
            )
