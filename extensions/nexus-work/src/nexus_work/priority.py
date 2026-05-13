from __future__ import annotations

from datetime import date, datetime
from typing import Any

_PRIORITY_SCORES = {"critical": 100, "high": 75, "medium": 50, "low": 25}


def score_action(action: dict[str, Any]) -> int:
    score = _PRIORITY_SCORES.get(action.get("priority", "medium"), 50)

    due = action.get("due_date")
    if due:
        try:
            due_date = datetime.strptime(due, "%Y-%m-%d").date()
            days_until = (due_date - date.today()).days
            if days_until < 0:
                score += 50 + min(abs(days_until) * 5, 50)
            elif days_until == 0:
                score += 40
            elif days_until <= 2:
                score += 20
            elif days_until <= 7:
                score += 10
        except ValueError:
            pass

    if action.get("status") == "in_progress":
        score += 10

    if action.get("assigned_to") == "self":
        score += 5

    return score
