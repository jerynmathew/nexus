from __future__ import annotations

import time
from collections import deque
from typing import Any

from civitas.genserver import GenServer

_MAX_ACTIVITY = 100
_TICK_INTERVAL_MS = 30_000


class DashboardServer(GenServer):
    async def init(self) -> None:
        self.state["agents"] = {}
        self.state["activity"] = []
        self.state["mcp_servers"] = {}
        self.state["started_at"] = time.time()
        self._activity: deque[dict[str, Any]] = deque(maxlen=_MAX_ACTIVITY)
        self.send_after(_TICK_INTERVAL_MS, {"action": "tick"})

    async def handle_call(
        self,
        payload: dict[str, Any],
        from_: str,
    ) -> dict[str, Any]:
        action = payload.get("action", "")

        if action == "get_health":
            return self._build_health()
        if action == "get_topology":
            return self._build_topology()
        if action == "get_agents":
            return {"agents": dict(self.state.get("agents", {}))}
        if action == "get_activity":
            return {"activity": list(self._activity)}
        if action == "get_trust":
            return {"trust": dict(self.state.get("trust_scores", {}))}

        return {"error": f"unknown action: {action}"}

    async def handle_cast(self, payload: dict[str, Any]) -> None:
        action = payload.get("action", "")

        if action == "agent_health":
            agent_name = payload.get("agent")
            if agent_name:
                agents = self.state.setdefault("agents", {})
                agents[agent_name] = {
                    "status": payload.get("status", "unknown"),
                    "restart_count": payload.get("restart_count", 0),
                    "last_active": time.time(),
                }

        elif action == "activity":
            self._activity.append(
                {
                    "agent": payload.get("agent", ""),
                    "type": payload.get("type", ""),
                    "detail": payload.get("detail", ""),
                    "timestamp": time.time(),
                }
            )

        elif action == "mcp_status":
            server_name = payload.get("server")
            if server_name:
                mcp = self.state.setdefault("mcp_servers", {})
                mcp[server_name] = {
                    "connected": payload.get("connected", False),
                    "tool_count": payload.get("tool_count", 0),
                }

        elif action == "trust_update":
            tenant_id = payload.get("tenant_id", "")
            category = payload.get("category", "")
            score = payload.get("score", 0.5)
            trust = self.state.setdefault("trust_scores", {})
            tenant_trust = trust.setdefault(tenant_id, {})
            tenant_trust[category] = score

    async def handle_info(self, payload: dict[str, Any]) -> None:
        if payload.get("action") == "tick":
            self.state["activity"] = list(self._activity)
            self.send_after(_TICK_INTERVAL_MS, {"action": "tick"})

    def _build_health(self) -> dict[str, Any]:
        agents = self.state.get("agents", {})
        all_running = all(a.get("status") == "running" for a in agents.values())
        return {
            "status": "healthy" if all_running else "degraded",
            "agent_count": len(agents),
            "uptime_seconds": time.time() - self.state.get("started_at", time.time()),
        }

    def _build_topology(self) -> dict[str, Any]:
        agents = self.state.get("agents", {})
        mcp = self.state.get("mcp_servers", {})
        return {
            "nexus": {
                "supervisor": "root",
                "strategy": "ONE_FOR_ALL",
                "children": [
                    {"name": n, "type": info.get("type", "agent"), **info}
                    for n, info in agents.items()
                ],
            },
            "external": {
                "agentgateway": {"status": "running", "port": 4000},
                "mcp_servers": {
                    n: {**s, "status": "connected" if s.get("connected") else "disconnected"}
                    for n, s in mcp.items()
                },
            },
        }
