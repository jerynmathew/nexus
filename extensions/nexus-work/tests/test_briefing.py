from __future__ import annotations

from unittest.mock import AsyncMock

from nexus_work.briefing import (
    assemble_evening_wrap,
    assemble_meeting_prep,
    assemble_morning_briefing,
)


def _ctx_with_responses(*responses):
    ctx = AsyncMock()
    ctx.send_to_memory = AsyncMock(side_effect=list(responses))
    return ctx


class TestMorningBriefing:
    async def test_empty_state(self) -> None:
        ctx = _ctx_with_responses(
            {"rows": []},
            {"rows": []},
            {"rows": []},
            {"rows": []},
        )
        text = await assemble_morning_briefing(ctx, "t1")
        assert "Good morning" in text
        assert "All clear" in text

    async def test_with_urgent_actions(self) -> None:
        ctx = _ctx_with_responses(
            {"rows": [[1, "Review PR", "open", "critical", "2026-05-13", "self"]]},
            {"rows": []},
            {"rows": []},
            {"rows": []},
        )
        text = await assemble_morning_briefing(ctx, "t1")
        assert "URGENT" in text
        assert "Review PR" in text

    async def test_with_meetings(self) -> None:
        ctx = _ctx_with_responses(
            {"rows": []},
            {"rows": []},
            {"rows": []},
            {"rows": [[1, "1:1 with Raj", "2026-05-13", '["Raj"]']]},
        )
        text = await assemble_morning_briefing(ctx, "t1")
        assert "MEETINGS" in text
        assert "Raj" in text

    async def test_with_delegations(self) -> None:
        ctx = _ctx_with_responses(
            {"rows": []},
            {"rows": []},
            {"rows": [[1, "Raj", "Cache redesign", "stale", "2026-05-16", None]]},
            {"rows": []},
        )
        text = await assemble_morning_briefing(ctx, "t1")
        assert "DELEGATION" in text
        assert "STALE" in text


class TestEveningWrap:
    async def test_empty_state(self) -> None:
        ctx = _ctx_with_responses(
            {"rows": []},
            {"rows": []},
            {"rows": []},
        )
        text = await assemble_evening_wrap(ctx, "t1")
        assert "Day Summary" in text
        assert "Quiet day" in text

    async def test_with_completed(self) -> None:
        ctx = _ctx_with_responses(
            {"rows": [[1, "Review PR", "done", "high", None, "self"]]},
            {"rows": []},
            {"rows": []},
        )
        text = await assemble_evening_wrap(ctx, "t1")
        assert "Completed" in text
        assert "Review PR" in text


class TestMeetingPrep:
    async def test_no_meeting(self) -> None:
        ctx = _ctx_with_responses({"rows": []})
        result = await assemble_meeting_prep(ctx, "t1", 999)
        assert result is None

    async def test_with_meeting(self) -> None:
        ctx = _ctx_with_responses(
            {"rows": [["1:1 with Raj", '["Raj"]', "2026-05-14", None]]},
            {"rows": []},
            {"rows": [[1, "Raj", "Cache redesign", "assigned", "2026-05-16", None]]},
        )
        result = await assemble_meeting_prep(ctx, "t1", 1)
        assert result is not None
        assert "Raj" in result
        assert "Cache redesign" in result
