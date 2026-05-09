from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any

from civitas.messages import Message
from civitas.process import AgentProcess

from nexus.agents.intent import Intent, RegexClassifier
from nexus.llm.client import LLMClient, LLMResponse
from nexus.models.session import Session
from nexus.models.tenant import TenantContext
from nexus.persona.loader import PersonaLoader

logger = logging.getLogger(__name__)

_MAX_TOOL_ITERATIONS = 5


class ConversationManager(AgentProcess):
    def __init__(
        self,
        name: str,
        llm_base_url: str = "http://localhost:4000",
        llm_api_key: str = "",
        llm_model: str = "claude-sonnet-4-20250514",
        llm_max_tokens: int = 4096,
        personas_dir: str = "personas",
        users_dir: str = "data/users",
        **kwargs: Any,
    ) -> None:
        super().__init__(name, **kwargs)
        self._llm_base_url = llm_base_url
        self._llm_api_key = llm_api_key
        self._llm_model = llm_model
        self._llm_max_tokens = llm_max_tokens
        self._personas_dir = personas_dir
        self._users_dir = users_dir

        self._llm: LLMClient | None = None
        self._persona_loader: PersonaLoader | None = None
        self._classifier = RegexClassifier()
        self._sessions: dict[str, Session] = {}
        self._state_loaded = False
        self._transport: Any = None

    async def on_start(self) -> None:
        self._llm = LLMClient(
            base_url=self._llm_base_url,
            api_key=self._llm_api_key,
            default_model=self._llm_model,
        )
        self._persona_loader = PersonaLoader(
            personas_dir=Path(self._personas_dir),
            users_dir=Path(self._users_dir),
        )
        self._state_loaded = False

    async def on_stop(self) -> None:
        if self._llm:
            await self._llm.close()
            self._llm = None

    def set_transport(self, transport: Any) -> None:
        self._transport = transport

    async def handle(self, message: Message) -> Message | None:
        action = message.payload.get("action")

        if action == "inbound_message":
            return await self._handle_inbound(message)
        elif action == "execute_skill":
            return await self._handle_skill_trigger(message)
        elif action == "callback":
            return await self._handle_transport_callback(message)
        elif action == "status":
            return self.reply(
                {
                    "status": "running",
                    "active_sessions": len(self._sessions),
                }
            )
        else:
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
            intent.target_service, intent.action or "read"
        ):
            await self._send_reply(
                channel_id, f"You don't have permission for {intent.target_service}."
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

        await self._send_reply(channel_id, response_text)

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
            logger.debug("[%s] Tenant resolution via memory failed for %s", self.name, tenant_id)

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
                if checkpoint:
                    session = Session.from_dict(checkpoint)
                else:
                    session = Session(
                        session_id=result.payload["session_id"],
                        tenant_id=tenant.tenant_id,
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

        response = await self._tool_use_loop(messages, system_prompt)

        return response.content

    async def _build_system_prompt(self, tenant: TenantContext, intent: Intent) -> str:
        if not self._persona_loader:
            return ""

        parts: list[str] = []

        parts.append(
            self._persona_loader.build_system_identity(
                persona_name=tenant.persona_name,
                tenant_id=tenant.tenant_id,
                tenant_name=tenant.name,
                timezone=tenant.timezone,
                role=tenant.role,
            )
        )

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

        return "\n\n---\n\n".join(parts)

    def _build_messages(self, session: Session, current_text: str) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []

        for msg in session.messages[-20:]:
            messages.append({"role": msg["role"], "content": msg["content"]})

        messages.append({"role": "user", "content": current_text})
        return messages

    async def _tool_use_loop(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str,
        tools: list[dict[str, Any]] | None = None,
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
                tool_result = f"Tool '{tc.name}' is not available yet."
                messages.append(
                    {
                        "role": "assistant",
                        "content": response.content or "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "function": {
                                    "name": tc.name,
                                    "arguments": str(tc.input),
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

    async def _send_typing(self, channel_id: str) -> None:
        if self._transport and hasattr(self._transport, "send_typing"):
            try:
                await self._transport.send_typing(channel_id)
            except Exception:
                pass

    async def _handle_skill_trigger(self, message: Message) -> Message | None:
        logger.info("[%s] Skill execution not yet implemented", self.name)
        return None

    async def _handle_transport_callback(self, message: Message) -> Message | None:
        logger.info("[%s] Transport callbacks not yet implemented", self.name)
        return None
