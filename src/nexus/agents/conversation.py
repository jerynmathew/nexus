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
from nexus.governance.audit import AuditEntry, AuditSink
from nexus.governance.policy import PolicyDecision, PolicyEngine
from nexus.llm.client import LLMClient, LLMResponse
from nexus.mcp.manager import MCPManager
from nexus.models.session import Session
from nexus.models.tenant import TenantContext
from nexus.persona.loader import PersonaLoader
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
        self._skill_manager: SkillManager | None = None
        self._compressor = ContextCompressor()
        self._content_store: ContentStore | None = None
        self._dashboard_config: DashboardConfig | None = None
        self._sessions: dict[str, Session] = {}
        self._pending_approvals: dict[str, dict[str, Any]] = {}
        self._transport: Any = None

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

    async def handle(self, message: Message) -> Message | None:
        action = message.payload.get("action")

        if action == "inbound_message":
            return await self._handle_inbound(message)
        if action == "execute_skill":
            return await self._handle_skill_trigger(message)
        if action == "callback":
            return await self._handle_transport_callback(message)
        if action == "status":
            return self.reply(
                {
                    "status": "running",
                    "active_sessions": len(self._sessions),
                }
            )

        logger.warning("[%s] Unknown action: %s", self.name, action)
        return None

    async def _handle_inbound(self, message: Message) -> Message | None:
        payload = message.payload
        tenant_id = payload.get("tenant_id")
        text = payload.get("text", "")
        channel_id = payload.get("channel_id", "")

        if not tenant_id:
            return None

        tenant = await self._resolve_tenant(tenant_id)
        if tenant is None:
            await self._send_reply(channel_id, "Sorry, you're not authorized.")
            return None

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
                persona_name=tenant.persona_name,
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

        return "\n\n---\n\n".join(parts)

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
        decision = self._policy.check(tool_name, arguments)

        self._audit.log(
            AuditEntry(
                agent=self.name,
                tenant_id=tenant.tenant_id,
                tool_name=tool_name,
                arguments_summary=AuditSink.summarize_arguments(arguments),
                decision=decision.value,
            )
        )

        if decision == PolicyDecision.DENY:
            return f"Action '{tool_name}' is not allowed by policy."

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
        model = self._llm.model_for_task("SKILL_EXEC")

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
        await self._send_reply(channel_id, resp.content)

    async def _handle_transport_callback(self, message: Message) -> Message | None:
        callback_data = message.payload.get("callback_data", "")
        tenant_id = message.payload.get("tenant_id", "")
        channel_id = message.payload.get("channel_id", "")

        if callback_data.startswith("approve:"):
            approval_id = callback_data.removeprefix("approve:")
            pending = self._pending_approvals.pop(approval_id, None)
            if pending:
                self._audit.log(
                    AuditEntry(
                        agent=self.name,
                        tenant_id=tenant_id,
                        tool_name=pending.get("tool_name", ""),
                        decision="APPROVED",
                    )
                )
                await self._send_reply(channel_id, "✅ Approved.")
            return None

        if callback_data.startswith("reject:"):
            approval_id = callback_data.removeprefix("reject:")
            pending = self._pending_approvals.pop(approval_id, None)
            if pending:
                self._audit.log(
                    AuditEntry(
                        agent=self.name,
                        tenant_id=tenant_id,
                        tool_name=pending.get("tool_name", ""),
                        decision="REJECTED",
                    )
                )
                await self._send_reply(channel_id, "❌ Rejected.")
            return None

        logger.warning("[%s] Unknown callback: %s", self.name, callback_data)
        return None

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
