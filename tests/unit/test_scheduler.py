from __future__ import annotations

from civitas.messages import Message

from nexus.agents.scheduler import SchedulerAgent


class TestSchedulerAgent:
    async def test_starts(self) -> None:
        agent = SchedulerAgent(name="scheduler")
        await agent.on_start()
        assert agent._state_loaded is False

    async def test_status_query(self) -> None:
        agent = SchedulerAgent(name="scheduler")
        await agent.on_start()

        msg = Message(
            sender="test",
            recipient="scheduler",
            payload={"action": "status"},
            reply_to="test",
        )
        agent._current_message = msg
        try:
            result = await agent.handle(msg)
        finally:
            agent._current_message = None

        assert result is not None
        assert result.payload["status"] == "running"
        assert result.payload["state_loaded"] is True
