from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

from nexus_work.signals import extract_actions_from_signal, store_signal


class TestStoreSignal:
    async def test_stores_signal(self) -> None:
        ctx = AsyncMock()
        ctx.send_to_memory = AsyncMock(return_value={"status": "ok"})

        signal_id = await store_signal(
            ctx,
            tenant_id="t1",
            source="slack",
            event_type="message",
            title="Test message",
            body="Hello world",
            author="Sarah",
        )
        assert signal_id.startswith("slack_")
        ctx.send_to_memory.assert_called_once()


class TestExtractActions:
    async def test_no_llm(self) -> None:
        ctx = AsyncMock()
        ctx.llm = None
        count = await extract_actions_from_signal(ctx, "t1", "hello", "slack")
        assert count == 0

    async def test_no_actions_found(self) -> None:
        ctx = AsyncMock()
        llm = AsyncMock()
        llm.chat = AsyncMock(return_value=MagicMock(content="[]"))
        ctx.llm = llm
        count = await extract_actions_from_signal(ctx, "t1", "nice weather today", "slack")
        assert count == 0

    async def test_extracts_self_action(self) -> None:
        ctx = AsyncMock()
        llm = AsyncMock()
        items = [{"title": "Review PR #234", "assigned_to": "self", "priority": "high"}]
        llm.chat = AsyncMock(return_value=MagicMock(content=json.dumps(items)))
        ctx.llm = llm
        ctx.send_to_memory = AsyncMock(return_value={"status": "ok"})

        count = await extract_actions_from_signal(
            ctx, "t1", "Can you review PR #234?", "email", author="Sarah"
        )
        assert count == 1
        call = ctx.send_to_memory.call_args
        assert "work_actions" in call[0][1]["sql"]

    async def test_extracts_delegation(self) -> None:
        ctx = AsyncMock()
        llm = AsyncMock()
        items = [{"title": "Cache redesign", "assigned_to": "Raj", "priority": "medium"}]
        llm.chat = AsyncMock(return_value=MagicMock(content=json.dumps(items)))
        ctx.llm = llm
        ctx.send_to_memory = AsyncMock(return_value={"status": "ok"})

        count = await extract_actions_from_signal(
            ctx, "t1", "Raj, can you handle the cache redesign?", "slack"
        )
        assert count == 1
        call = ctx.send_to_memory.call_args
        assert "work_delegations" in call[0][1]["sql"]

    async def test_llm_failure(self) -> None:
        ctx = AsyncMock()
        llm = AsyncMock()
        llm.chat = AsyncMock(side_effect=Exception("timeout"))
        ctx.llm = llm

        count = await extract_actions_from_signal(ctx, "t1", "review this", "email")
        assert count == 0

    async def test_invalid_json_response(self) -> None:
        ctx = AsyncMock()
        llm = AsyncMock()
        llm.chat = AsyncMock(return_value=MagicMock(content="not json"))
        ctx.llm = llm

        count = await extract_actions_from_signal(ctx, "t1", "review this", "email")
        assert count == 0
