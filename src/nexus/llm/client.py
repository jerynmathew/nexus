from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    input: dict[str, Any]


@dataclass(frozen=True)
class LLMResponse:
    content: str
    model: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    tool_calls: list[ToolCall] = field(default_factory=list)


class LLMClient:
    def __init__(
        self,
        base_url: str = "http://localhost:4000",
        api_key: str = "",
        default_model: str = "claude-sonnet-4-20250514",
        timeout: float = 120.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._default_model = default_model
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers=headers,
            timeout=timeout,
        )

    async def chat(
        self,
        messages: list[dict[str, Any]],
        model: str | None = None,
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        model = model or self._default_model

        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
        }

        if system:
            body["messages"] = [{"role": "system", "content": system}, *messages]

        if tools:
            body["tools"] = tools

        try:
            resp = await self._client.post("/v1/chat/completions", json=body)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                logger.warning("LLM rate limited (429), retry after backoff")
            raise
        except httpx.ConnectError:
            logger.error("Cannot connect to LLM gateway at %s", self._base_url)
            raise

        data = resp.json()
        return self._parse_response(data, model)

    def _parse_response(self, data: dict[str, Any], model: str) -> LLMResponse:
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})

        content = message.get("content") or ""

        tool_calls: list[ToolCall] = []
        raw_tool_calls = message.get("tool_calls", [])
        for tc in raw_tool_calls:
            func = tc.get("function", {})
            import json

            try:
                args = json.loads(func.get("arguments", "{}"))
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(
                ToolCall(
                    id=tc.get("id", ""),
                    name=func.get("name", ""),
                    input=args,
                )
            )

        usage = data.get("usage", {})

        return LLMResponse(
            content=content,
            model=model,
            tokens_in=usage.get("prompt_tokens", 0),
            tokens_out=usage.get("completion_tokens", 0),
            tool_calls=tool_calls,
        )

    async def close(self) -> None:
        await self._client.aclose()
