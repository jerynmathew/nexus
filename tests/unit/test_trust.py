from __future__ import annotations

from nexus.governance.trust import TrustStore, tool_category


class TestToolCategory:
    def test_gmail_tool(self) -> None:
        assert tool_category("search_gmail_messages") == "gmail"

    def test_calendar_tool(self) -> None:
        assert tool_category("list_calendars") == "calendar"

    def test_events_tool(self) -> None:
        assert tool_category("get_events") == "calendar"

    def test_send_tool(self) -> None:
        assert tool_category("send_gmail_message") == "gmail"

    def test_tasks_tool(self) -> None:
        assert tool_category("list_task_lists") == "tasks"

    def test_freebusy(self) -> None:
        assert tool_category("query_freebusy") == "calendar"

    def test_unknown(self) -> None:
        assert tool_category("something_random") == "general"

    def test_web_search(self) -> None:
        assert tool_category("web_search") == "search"


class TestTrustStore:
    def test_default_score(self) -> None:
        store = TrustStore()
        assert store.get_score("t1", "gmail") == 0.5

    def test_positive_delta(self) -> None:
        store = TrustStore()
        new = store.update_score("t1", "gmail", 0.1)
        assert new == 0.6
        assert store.get_score("t1", "gmail") == 0.6

    def test_negative_delta(self) -> None:
        store = TrustStore()
        new = store.update_score("t1", "gmail", -0.2)
        assert new == 0.3

    def test_clamped_at_max(self) -> None:
        store = TrustStore()
        store.update_score("t1", "gmail", 0.6)
        assert store.get_score("t1", "gmail") == 1.0

    def test_clamped_at_min(self) -> None:
        store = TrustStore()
        store.update_score("t1", "gmail", -0.8)
        assert store.get_score("t1", "gmail") == 0.0

    def test_independent_categories(self) -> None:
        store = TrustStore()
        store.update_score("t1", "gmail", 0.2)
        store.update_score("t1", "calendar", -0.1)
        assert store.get_score("t1", "gmail") == 0.7
        assert store.get_score("t1", "calendar") == 0.4

    def test_get_all_scores(self) -> None:
        store = TrustStore()
        store.update_score("t1", "gmail", 0.1)
        store.update_score("t1", "calendar", 0.2)
        scores = store.get_all_scores("t1")
        assert "gmail" in scores
        assert "calendar" in scores

    def test_independent_tenants(self) -> None:
        store = TrustStore()
        store.update_score("t1", "gmail", 0.3)
        assert store.get_score("t2", "gmail") == 0.5


class TestTrustPersistence:
    async def test_load_from_memory_success(self) -> None:
        from unittest.mock import AsyncMock

        from civitas.messages import Message

        store = TrustStore()
        resp = Message(
            sender="memory",
            recipient="test",
            payload={"configs": {"scores": {"gmail": "0.8", "calendar": "0.6"}}},
        )
        ask_fn = AsyncMock(return_value=resp)
        await store.load_from_memory(ask_fn, "t1")
        assert store.get_score("t1", "gmail") == 0.8
        assert store.get_score("t1", "calendar") == 0.6

    async def test_load_from_memory_failure(self) -> None:
        from unittest.mock import AsyncMock

        store = TrustStore()
        ask_fn = AsyncMock(side_effect=Exception("fail"))
        await store.load_from_memory(ask_fn, "t1")
        assert store.get_score("t1", "gmail") == 0.5

    async def test_save_to_memory_success(self) -> None:
        from unittest.mock import AsyncMock

        store = TrustStore()
        store.update_score("t1", "gmail", 0.1)
        send_fn = AsyncMock()
        await store.save_to_memory(send_fn, "t1")
        send_fn.assert_called_once()

    async def test_save_to_memory_failure(self) -> None:
        from unittest.mock import AsyncMock

        store = TrustStore()
        store.update_score("t1", "gmail", 0.1)
        send_fn = AsyncMock(side_effect=Exception("fail"))
        await store.save_to_memory(send_fn, "t1")
