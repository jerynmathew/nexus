from __future__ import annotations

from datetime import date, timedelta

from nexus_work.priority import score_action


class TestScoreAction:
    def test_base_priority_scores(self) -> None:
        assert score_action({"priority": "critical"}) > score_action({"priority": "high"})
        assert score_action({"priority": "high"}) > score_action({"priority": "medium"})
        assert score_action({"priority": "medium"}) > score_action({"priority": "low"})

    def test_overdue_boosts_score(self) -> None:
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        overdue = score_action({"priority": "medium", "due_date": yesterday})
        no_due = score_action({"priority": "medium"})
        assert overdue > no_due

    def test_due_today_boosts_score(self) -> None:
        today = date.today().isoformat()
        due_today = score_action({"priority": "medium", "due_date": today})
        no_due = score_action({"priority": "medium"})
        assert due_today > no_due

    def test_due_soon_boosts_score(self) -> None:
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        due_soon = score_action({"priority": "medium", "due_date": tomorrow})
        far_future = score_action(
            {
                "priority": "medium",
                "due_date": (date.today() + timedelta(days=30)).isoformat(),
            }
        )
        assert due_soon > far_future

    def test_in_progress_boosts(self) -> None:
        in_prog = score_action({"priority": "medium", "status": "in_progress"})
        open_item = score_action({"priority": "medium", "status": "open"})
        assert in_prog > open_item

    def test_self_assigned_boosts(self) -> None:
        self_item = score_action({"priority": "medium", "assigned_to": "self"})
        other = score_action({"priority": "medium", "assigned_to": "Raj"})
        assert self_item > other

    def test_invalid_date_handled(self) -> None:
        score = score_action({"priority": "medium", "due_date": "not-a-date"})
        assert score == 50

    def test_missing_priority(self) -> None:
        score = score_action({})
        assert score == 50
