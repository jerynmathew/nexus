from __future__ import annotations

import json

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
