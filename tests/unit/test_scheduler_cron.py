from __future__ import annotations

from datetime import UTC, datetime

from nexus.agents.scheduler import SchedulerAgent


class TestCronMatches:
    def test_matching_minute(self) -> None:
        now = datetime(2026, 5, 10, 7, 0, 0, tzinfo=UTC)
        assert SchedulerAgent._cron_matches("0 7 * * *", now)

    def test_non_matching_minute(self) -> None:
        now = datetime(2026, 5, 10, 8, 0, 0, tzinfo=UTC)
        assert not SchedulerAgent._cron_matches("0 7 * * *", now)

    def test_every_minute(self) -> None:
        now = datetime(2026, 5, 10, 14, 33, 0, tzinfo=UTC)
        assert SchedulerAgent._cron_matches("* * * * *", now)

    def test_invalid_cron(self) -> None:
        now = datetime(2026, 5, 10, 7, 0, 0, tzinfo=UTC)
        assert not SchedulerAgent._cron_matches("invalid", now)
