from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from nexus.llm.client import LLMClient


class TestLLMClient:
    async def test_parse_simple_response(self) -> None:
        client = LLMClient(base_url="http://localhost:9999")

        data = {
            "choices": [
                {
                    "message": {
                        "content": "Hello! How can I help?",
                    }
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 8},
        }

        result = client._parse_response(data, "test-model")
        assert result.content == "Hello! How can I help?"
        assert result.tokens_in == 10
        assert result.tokens_out == 8
        assert result.tool_calls == []

        await client.close()

    async def test_parse_tool_call_response(self) -> None:
        client = LLMClient(base_url="http://localhost:9999")

        data = {
            "choices": [
                {
                    "message": {
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call_123",
                                "function": {
                                    "name": "get_weather",
                                    "arguments": json.dumps({"city": "London"}),
                                },
                            }
                        ],
                    }
                }
            ],
            "usage": {"prompt_tokens": 15, "completion_tokens": 20},
        }

        result = client._parse_response(data, "test-model")
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "get_weather"
        assert result.tool_calls[0].input == {"city": "London"}
        assert result.tool_calls[0].id == "call_123"

        await client.close()

    async def test_parse_empty_choices(self) -> None:
        client = LLMClient(base_url="http://localhost:9999")
        data: dict = {"choices": [{}], "usage": {}}
        result = client._parse_response(data, "test-model")
        assert result.content == ""
        assert result.tool_calls == []
        await client.close()

    def test_model_for_task_classify(self) -> None:
        client = LLMClient(base_url="http://localhost:9999", cheap_model="haiku")
        assert client.model_for_task("CLASSIFY") == "haiku"

    def test_model_for_task_default(self) -> None:
        client = LLMClient(base_url="http://localhost:9999", default_model="sonnet")
        assert client.model_for_task("CONVERSE") == "sonnet"

    async def test_chat_with_system(self) -> None:
        client = LLMClient(base_url="http://localhost:9999")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "hi"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 3},
        }
        mock_resp.raise_for_status = MagicMock()
        client._client.post = AsyncMock(return_value=mock_resp)
        result = await client.chat(
            messages=[{"role": "user", "content": "hi"}],
            system="You are helpful.",
        )
        assert result.content == "hi"
        body = client._client.post.call_args.kwargs["json"]
        assert body["messages"][0]["role"] == "system"
        await client.close()

    async def test_chat_with_tools(self) -> None:
        client = LLMClient(base_url="http://localhost:9999")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "ok"}}],
            "usage": {},
        }
        mock_resp.raise_for_status = MagicMock()
        client._client.post = AsyncMock(return_value=mock_resp)
        tools = [{"type": "function", "function": {"name": "t"}}]
        result = await client.chat(
            messages=[{"role": "user", "content": "hi"}],
            tools=tools,
        )
        assert result.content == "ok"
        body = client._client.post.call_args.kwargs["json"]
        assert "tools" in body
        await client.close()

    async def test_chat_rate_limit(self) -> None:
        client = LLMClient(base_url="http://localhost:9999")
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "rate limited", request=MagicMock(), response=mock_resp
        )
        client._client.post = AsyncMock(return_value=mock_resp)
        with pytest.raises(httpx.HTTPStatusError):
            await client.chat(messages=[{"role": "user", "content": "hi"}])
        await client.close()

    async def test_chat_connect_error(self) -> None:
        client = LLMClient(base_url="http://localhost:9999")
        client._client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
        with pytest.raises(httpx.ConnectError):
            await client.chat(messages=[{"role": "user", "content": "hi"}])
        await client.close()

    async def test_parse_malformed_arguments(self) -> None:
        client = LLMClient(base_url="http://localhost:9999")
        data = {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "function": {
                                    "name": "test",
                                    "arguments": "not-json",
                                },
                            }
                        ],
                    }
                }
            ],
            "usage": {},
        }
        result = client._parse_response(data, "test-model")
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].input == {}
        await client.close()
