from __future__ import annotations

from nexus.dashboard.server import DashboardServer


async def _call(server: DashboardServer, payload: dict) -> dict:
    from civitas.messages import Message

    msg = Message(sender="test", recipient="dashboard", payload=payload, reply_to="test")
    server._current_message = msg
    try:
        result = await server.handle(msg)
        return result.payload if result else {}
    finally:
        server._current_message = None


async def _cast(server: DashboardServer, payload: dict) -> None:
    from civitas.messages import Message

    msg = Message(sender="test", recipient="dashboard", payload={**payload, "__cast__": True})
    server._current_message = msg
    try:
        await server.handle(msg)
    finally:
        server._current_message = None


class TestDashboardServer:
    async def test_get_health(self) -> None:
        server = DashboardServer(name="dashboard")
        await server.init()
        result = await _call(server, {"action": "get_health"})
        assert result["status"] in ("healthy", "degraded")
        assert "agent_count" in result

    async def test_get_agents_empty(self) -> None:
        server = DashboardServer(name="dashboard")
        await server.init()
        result = await _call(server, {"action": "get_agents"})
        assert result["agents"] == {}

    async def test_cast_agent_health(self) -> None:
        server = DashboardServer(name="dashboard")
        await server.init()
        await _cast(
            server,
            {
                "action": "agent_health",
                "agent": "memory",
                "status": "running",
                "restart_count": 0,
            },
        )
        result = await _call(server, {"action": "get_agents"})
        assert "memory" in result["agents"]
        assert result["agents"]["memory"]["status"] == "running"

    async def test_cast_activity(self) -> None:
        server = DashboardServer(name="dashboard")
        await server.init()
        await _cast(
            server,
            {
                "action": "activity",
                "agent": "conversation_manager",
                "type": "inbound",
                "detail": "check my email",
            },
        )
        result = await _call(server, {"action": "get_activity"})
        assert len(result["activity"]) == 1
        assert result["activity"][0]["agent"] == "conversation_manager"

    async def test_activity_capped(self) -> None:
        server = DashboardServer(name="dashboard")
        await server.init()
        for i in range(150):
            await _cast(server, {"action": "activity", "agent": f"a{i}", "type": "test"})
        result = await _call(server, {"action": "get_activity"})
        assert len(result["activity"]) <= 100

    async def test_get_topology(self) -> None:
        server = DashboardServer(name="dashboard")
        await server.init()
        await _cast(server, {"action": "agent_health", "agent": "memory", "status": "running"})
        result = await _call(server, {"action": "get_topology"})
        nexus = result["nexus"]
        assert nexus["supervisor"] == "root"
        assert len(nexus["children"]) == 1
