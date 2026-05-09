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
