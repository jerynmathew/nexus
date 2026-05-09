from __future__ import annotations

from unittest.mock import AsyncMock

from nexus.agents.compressor import ContextCompressor
from nexus.llm.client import LLMResponse


def _make_messages(count: int, content_size: int = 100) -> list[dict]:
    return [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"msg{i} " + "x" * content_size}
        for i in range(count)
    ]


class TestNeedsCompression:
    def test_short_conversation(self) -> None:
        comp = ContextCompressor(max_context_tokens=100_000)
        messages = _make_messages(5)
        assert not comp.needs_compression(messages)

    def test_long_conversation(self) -> None:
        comp = ContextCompressor(max_context_tokens=1000, threshold=0.5)
        messages = _make_messages(50, content_size=200)
        assert comp.needs_compression(messages)


class TestCompress:
    async def test_short_no_compression(self) -> None:
        comp = ContextCompressor(max_context_tokens=100_000)
        messages = _make_messages(5)
        llm = AsyncMock()

        result = await comp.compress(messages, llm)
        assert result == messages
        llm.chat.assert_not_called()

    async def test_long_compresses(self) -> None:
        comp = ContextCompressor(max_context_tokens=1000, threshold=0.5, tail_size=5)
        messages = _make_messages(50, content_size=200)

        llm = AsyncMock()
        llm.chat.return_value = LLMResponse(content="Summary of conversation.")
        llm.model_for_task.return_value = "haiku"

        result = await comp.compress(messages, llm)

        assert len(result) < len(messages)
        assert result[0]["role"] == "system"
        assert "Summary" in result[0]["content"]
        assert len(result) == 6

    async def test_tail_preserved(self) -> None:
        comp = ContextCompressor(max_context_tokens=1000, threshold=0.5, tail_size=10)
        messages = _make_messages(50, content_size=200)

        llm = AsyncMock()
        llm.chat.return_value = LLMResponse(content="Summary.")
        llm.model_for_task.return_value = "haiku"

        result = await comp.compress(messages, llm)

        tail_contents = [m["content"] for m in result[1:]]
        original_tail = [m["content"] for m in messages[-10:]]
        assert tail_contents == original_tail

    async def test_tool_results_pruned(self) -> None:
        comp = ContextCompressor(max_context_tokens=500, threshold=0.5, tail_size=3)
        messages = [
            {"role": "user", "content": "query"},
            {"role": "tool", "content": "x" * 500},
            {"role": "assistant", "content": "response"},
            {"role": "user", "content": "thanks"},
            {"role": "assistant", "content": "welcome"},
        ]

        pruned = comp._prune_old_tool_results(messages)
        assert "[tool result summarized]" in pruned[1]["content"]
        assert len(pruned[1]["content"]) < 500


class TestTokenEstimate:
    def test_estimate(self) -> None:
        messages = [{"role": "user", "content": "a" * 400}]
        assert ContextCompressor._estimate_tokens(messages) == 101
