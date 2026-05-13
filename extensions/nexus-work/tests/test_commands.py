from __future__ import annotations

from unittest.mock import AsyncMock

from nexus_work.commands import (
    handle_actions,
    handle_delegate,
    handle_meetings,
    handle_next,
)


class TestHandleActions:
    async def test_no_context(self) -> None:
        reply = AsyncMock()
        await handle_actions(
            command="actions",
            args="",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
        )
        assert "unavailable" in reply.call_args[0][1]

    async def test_list_empty(self) -> None:
        reply = AsyncMock()
        ctx = AsyncMock()
        ctx.send_to_memory = AsyncMock(return_value={"rows": []})
        await handle_actions(
            command="actions",
            args="",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        assert "/actions add" in reply.call_args[0][1]

    async def test_list_with_items(self) -> None:
        reply = AsyncMock()
        ctx = AsyncMock()
        ctx.send_to_memory = AsyncMock(
            return_value={
                "rows": [
                    [1, "Review PR", "open", "high", "2026-05-14", "self"],
                    [2, "Write docs", "open", "medium", None, "self"],
                ],
            }
        )
        await handle_actions(
            command="actions",
            args="",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        sent = reply.call_args[0][1]
        assert "Review PR" in sent
        assert "Write docs" in sent

    async def test_add_no_text(self) -> None:
        reply = AsyncMock()
        ctx = AsyncMock()
        await handle_actions(
            command="actions",
            args="add",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        assert "Usage" in reply.call_args[0][1]

    async def test_add_success(self) -> None:
        reply = AsyncMock()
        ctx = AsyncMock()
        ctx.send_to_memory = AsyncMock(return_value={"status": "ok"})
        await handle_actions(
            command="actions",
            args="add Review Sarah's PR due=tomorrow priority=high",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        sent = reply.call_args[0][1]
        assert "Review Sarah's PR" in sent
        assert "high" in sent

    async def test_done_success(self) -> None:
        reply = AsyncMock()
        ctx = AsyncMock()
        ctx.send_to_memory = AsyncMock(return_value={"status": "ok"})
        await handle_actions(
            command="actions",
            args="done 1",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        assert "✅" in reply.call_args[0][1]

    async def test_done_invalid_id(self) -> None:
        reply = AsyncMock()
        ctx = AsyncMock()
        await handle_actions(
            command="actions",
            args="done abc",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        assert "Usage" in reply.call_args[0][1]

    async def test_all_includes_done(self) -> None:
        reply = AsyncMock()
        ctx = AsyncMock()
        ctx.send_to_memory = AsyncMock(
            return_value={
                "rows": [
                    [1, "Done task", "done", "low", None, "self"],
                ],
            }
        )
        await handle_actions(
            command="actions",
            args="all",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        sent = reply.call_args[0][1]
        assert "Done task" in sent


class TestHandleDelegate:
    async def test_no_context(self) -> None:
        reply = AsyncMock()
        await handle_delegate(
            command="delegate",
            args="",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
        )
        assert "unavailable" in reply.call_args[0][1]

    async def test_list_empty(self) -> None:
        reply = AsyncMock()
        ctx = AsyncMock()
        ctx.send_to_memory = AsyncMock(return_value={"rows": []})
        await handle_delegate(
            command="delegate",
            args="",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        assert "No active delegations" in reply.call_args[0][1]

    async def test_list_with_items(self) -> None:
        reply = AsyncMock()
        ctx = AsyncMock()
        ctx.send_to_memory = AsyncMock(
            return_value={
                "rows": [
                    [1, "Raj", "Cache redesign", "assigned", "2026-05-16", None],
                ],
            }
        )
        await handle_delegate(
            command="delegate",
            args="",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        sent = reply.call_args[0][1]
        assert "Raj" in sent
        assert "Cache redesign" in sent

    async def test_add_no_text(self) -> None:
        reply = AsyncMock()
        ctx = AsyncMock()
        await handle_delegate(
            command="delegate",
            args="add",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        assert "Usage" in reply.call_args[0][1]

    async def test_add_missing_task(self) -> None:
        reply = AsyncMock()
        ctx = AsyncMock()
        await handle_delegate(
            command="delegate",
            args="add Raj",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        assert "person and task" in reply.call_args[0][1]

    async def test_add_success(self) -> None:
        reply = AsyncMock()
        ctx = AsyncMock()
        ctx.send_to_memory = AsyncMock(return_value={"status": "ok"})
        await handle_delegate(
            command="delegate",
            args="add Raj Cache redesign due=Friday",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        sent = reply.call_args[0][1]
        assert "Raj" in sent
        assert "Cache redesign" in sent

    async def test_done_success(self) -> None:
        reply = AsyncMock()
        ctx = AsyncMock()
        ctx.send_to_memory = AsyncMock(return_value={"status": "ok"})
        await handle_delegate(
            command="delegate",
            args="done 1",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        assert "✅" in reply.call_args[0][1]


class TestHandleMeetings:
    async def test_no_context(self) -> None:
        reply = AsyncMock()
        await handle_meetings(
            command="meetings",
            args="",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
        )
        assert "unavailable" in reply.call_args[0][1]

    async def test_list_empty(self) -> None:
        reply = AsyncMock()
        ctx = AsyncMock()
        ctx.send_to_memory = AsyncMock(return_value={"rows": []})
        await handle_meetings(
            command="meetings",
            args="",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        assert "No meetings" in reply.call_args[0][1]

    async def test_list_with_items(self) -> None:
        reply = AsyncMock()
        ctx = AsyncMock()
        ctx.send_to_memory = AsyncMock(
            return_value={
                "rows": [
                    [1, "1:1 with Raj", "2026-05-14", '["Raj"]', None],
                ],
            }
        )
        await handle_meetings(
            command="meetings",
            args="",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        sent = reply.call_args[0][1]
        assert "1:1 with Raj" in sent
        assert "Raj" in sent

    async def test_add_no_text(self) -> None:
        reply = AsyncMock()
        ctx = AsyncMock()
        await handle_meetings(
            command="meetings",
            args="add",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        assert "Usage" in reply.call_args[0][1]

    async def test_add_success(self) -> None:
        reply = AsyncMock()
        ctx = AsyncMock()
        ctx.send_to_memory = AsyncMock(return_value={"status": "ok"})
        await handle_meetings(
            command="meetings",
            args="add Architecture review date=2026-05-14 attendees=Sarah,Raj",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        sent = reply.call_args[0][1]
        assert "Architecture review" in sent

    async def test_notes_success(self) -> None:
        reply = AsyncMock()
        ctx = AsyncMock()
        ctx.send_to_memory = AsyncMock(return_value={"status": "ok"})
        await handle_meetings(
            command="meetings",
            args="notes 1 Discussed cache strategy, Raj will prototype",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        assert "📝" in reply.call_args[0][1]

    async def test_notes_invalid(self) -> None:
        reply = AsyncMock()
        ctx = AsyncMock()
        await handle_meetings(
            command="meetings",
            args="notes",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        assert "Usage" in reply.call_args[0][1]


class TestHandleNext:
    async def test_no_context(self) -> None:
        reply = AsyncMock()
        await handle_next(
            command="next",
            args="",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
        )
        assert "unavailable" in reply.call_args[0][1]

    async def test_no_items(self) -> None:
        reply = AsyncMock()
        ctx = AsyncMock()
        ctx.send_to_memory = AsyncMock(return_value={"rows": []})
        await handle_next(
            command="next",
            args="",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        assert "clear" in reply.call_args[0][1]

    async def test_returns_top_priority(self) -> None:
        reply = AsyncMock()
        ctx = AsyncMock()
        ctx.send_to_memory = AsyncMock(
            return_value={
                "rows": [
                    [1, "Low task", "open", "low", None, "self"],
                    [2, "Urgent task", "open", "critical", "2026-05-13", "self"],
                ],
            }
        )
        await handle_next(
            command="next",
            args="",
            tenant_id="t1",
            channel_id="c1",
            send_reply=reply,
            nexus_context=ctx,
        )
        sent = reply.call_args[0][1]
        assert "Urgent task" in sent
