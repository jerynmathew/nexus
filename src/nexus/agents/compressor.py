from __future__ import annotations

import logging
from typing import Any

from nexus.llm.client import LLMClient

logger = logging.getLogger(__name__)

_CHARS_PER_TOKEN = 4
_SUMMARY_MARKER = "[conversation summary]"
_PRUNED_TOOL_MARKER = "[tool result summarized]"

_SUMMARIZE_PROMPT = (
    "Summarize the following conversation concisely. "
    "Preserve key facts, decisions, and context the user would need "
    "if the conversation continued. Be brief but complete."
)


class ContextCompressor:
    def __init__(
        self,
        max_context_tokens: int = 200_000,
        threshold: float = 0.5,
        tail_size: int = 20,
    ) -> None:
        self._max_tokens = max_context_tokens
        self._threshold = threshold
        self._tail_size = tail_size

    def needs_compression(self, messages: list[dict[str, Any]]) -> bool:
        token_estimate = self._estimate_tokens(messages)
        return token_estimate > self._max_tokens * self._threshold

    async def compress(
        self,
        messages: list[dict[str, Any]],
        llm: LLMClient,
    ) -> list[dict[str, Any]]:
        if not self.needs_compression(messages):
            return messages

        pruned = self._prune_old_tool_results(messages)

        if not self.needs_compression(pruned):
            return pruned

        tail_start = max(0, len(pruned) - self._tail_size)
        head, tail = pruned[:tail_start], pruned[tail_start:]

        if not head:
            return messages

        existing_summary = self._extract_existing_summary(head)
        to_summarize = self._collect_for_summary(head)

        summary_text = await self._generate_summary(
            to_summarize,
            existing_summary,
            llm,
        )

        summary_message = {
            "role": "system",
            "content": f"{_SUMMARY_MARKER}\n{summary_text}",
        }

        return [summary_message, *tail]

    def _prune_old_tool_results(
        self,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        tail_start = max(0, len(messages) - self._tail_size)
        result: list[dict[str, Any]] = []

        for i, msg in enumerate(messages):
            if i < tail_start and msg.get("role") == "tool":
                content = msg.get("content", "")
                if len(content) > 200:
                    result.append(
                        {
                            **msg,
                            "content": f"{_PRUNED_TOOL_MARKER}: {content[:100]}...",
                        }
                    )
                    continue
            result.append(msg)

        return result

    @staticmethod
    def _extract_existing_summary(head: list[dict[str, Any]]) -> str | None:
        for msg in head:
            content = str(msg.get("content", ""))
            if _SUMMARY_MARKER in content:
                return content.removeprefix(_SUMMARY_MARKER).strip()
        return None

    @staticmethod
    def _collect_for_summary(head: list[dict[str, Any]]) -> str:
        parts: list[str] = []
        for msg in head:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if _SUMMARY_MARKER in content:
                continue
            if content:
                parts.append(f"{role}: {content[:500]}")
        return "\n".join(parts)

    @staticmethod
    async def _generate_summary(
        conversation_text: str,
        existing_summary: str | None,
        llm: LLMClient,
    ) -> str:
        prompt = _SUMMARIZE_PROMPT
        if existing_summary:
            prompt += (
                f"\n\nPrevious summary to update:\n{existing_summary}"
                f"\n\nNew messages to incorporate:\n{conversation_text}"
            )
        else:
            prompt += f"\n\nConversation:\n{conversation_text}"

        model = llm.model_for_task("SUMMARIZE")
        response = await llm.chat(
            messages=[{"role": "user", "content": prompt}],
            model=model,
            max_tokens=1024,
        )
        return response.content

    @staticmethod
    def _estimate_tokens(messages: list[dict[str, Any]]) -> int:
        total_chars = sum(
            len(msg.get("content", "")) + len(msg.get("role", "")) for msg in messages
        )
        return total_chars // _CHARS_PER_TOKEN
