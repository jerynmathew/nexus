from __future__ import annotations

import json
import logging
import re
from typing import Any

from nexus.governance.audit import AuditEntry, AuditSink
from nexus.governance.policy import PolicyDecision, PolicyEngine
from nexus.governance.trust import TrustStore, tool_category
from nexus.llm.client import LLMClient, LLMResponse
from nexus.mcp.manager import MCPManager
from nexus.models.tenant import TenantContext

logger = logging.getLogger(__name__)

_MAX_TOOL_ITERATIONS = 5
_ACTION_URL_PATTERN = re.compile(r"https?://[^\s\"\])<>]{20,}", re.IGNORECASE)
_ACTION_URL_KEYWORDS = {"oauth", "authorize", "auth", "login", "callback", "consent"}


def _extract_action_urls(tool_result: str) -> list[str]:
    urls = _ACTION_URL_PATTERN.findall(tool_result)
    return [url for url in urls if any(kw in url.lower() for kw in _ACTION_URL_KEYWORDS)]


class ToolExecutor:
    def __init__(
        self,
        llm: LLMClient,
        mcp: MCPManager | None,
        policy: PolicyEngine,
        trust: TrustStore,
        audit: AuditSink,
        max_tokens: int = 4096,
    ) -> None:
        self._llm = llm
        self._mcp = mcp
        self._policy = policy
        self._trust = trust
        self._audit = audit
        self._max_tokens = max_tokens

    async def execute(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str,
        tools: list[dict[str, Any]] | None,
        tenant: TenantContext,
    ) -> LLMResponse:
        response: LLMResponse | None = None
        captured_urls: list[str] = []

        for _i in range(_MAX_TOOL_ITERATIONS):
            response = await self._llm.chat(
                messages=messages,
                system=system_prompt,
                tools=tools,
                max_tokens=self._max_tokens,
            )

            if not response.tool_calls:
                break

            for tc in response.tool_calls:
                tool_result = await self._run_with_governance(
                    tc.name,
                    tc.input,
                    tenant,
                )
                captured_urls.extend(_extract_action_urls(tool_result))
                assistant_msg: dict[str, Any] = {
                    "role": "assistant",
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
                if response.content:
                    assistant_msg["content"] = response.content
                messages.append(assistant_msg)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": tool_result,
                    }
                )

        if response is None:
            return LLMResponse(content="I couldn't complete that request.")

        if response.tool_calls and not response.content:
            last_tool_results = [
                m["content"] for m in messages if m.get("role") == "tool" and m.get("content")
            ]
            if last_tool_results:
                fallback = last_tool_results[-1][:2000]
                response = LLMResponse(
                    content=f"Here's what I found:\n\n{fallback}",
                    model=response.model,
                )

        if captured_urls and not any(url in response.content for url in captured_urls):
            suffix = "\n\n".join(f"🔗 {url}" for url in captured_urls)
            return LLMResponse(
                content=f"{response.content}\n\n{suffix}",
                model=response.model,
                tokens_in=response.tokens_in,
                tokens_out=response.tokens_out,
                tool_calls=response.tool_calls,
            )
        return response

    async def _run_with_governance(
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
                agent="conversation",
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
            logger.info("Tool '%s' requires approval", tool_name)

        if not self._mcp:
            return f"Tool '{tool_name}' is not available (no MCP connection)."

        return await self._mcp.call_tool(tool_name, arguments)
