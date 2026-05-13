from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from pathlib import Path
from typing import Any

import uvicorn

from nexus.dashboard.views import ContentStore

try:
    from nexus_work.priority import score_action as _score_action

    _HAS_WORK = True
except ImportError:
    _HAS_WORK = False

logger = logging.getLogger(__name__)

_STATIC_DIR = Path(__file__).parent / "static"
_CONTENT_TYPE_JSON = "application/json"
_CONTENT_TYPE_HTML = "text/html; charset=utf-8"


class DashboardApp:
    def __init__(
        self,
        runtime: Any,
        dashboard_agent: str = "dashboard",
        content_store: ContentStore | None = None,
        port: int = 8080,
    ) -> None:
        self._runtime = runtime
        self._dashboard_agent = dashboard_agent
        self._content_store = content_store or ContentStore()
        self._port = port

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Any,
        send: Any,
    ) -> None:
        if scope["type"] == "lifespan":
            await self._handle_lifespan(receive, send)
            return
        if scope["type"] != "http":
            return

        path = scope.get("path", "/")
        method = scope.get("method", "GET")

        if method == "GET" and path == "/":
            await self._serve_static("index.html", send)
        elif method == "GET" and path == "/dashboard/finance":
            await self._serve_static("finance.html", send)
        elif method == "GET" and path == "/dashboard/work":
            await self._serve_static("work.html", send)
        elif method == "GET" and path.startswith("/api/"):
            await self._handle_api(path, send)
        elif method == "GET" and path.startswith("/view/"):
            await self._handle_view(path, send)
        else:
            await self._send_response(send, 404, {"error": "not found"})

    async def _handle_api(self, path: str, send: Any) -> None:
        if path == "/api/finance":
            await self._handle_finance_api(send)
            return
        if path == "/api/work":
            await self._handle_work_api(send)
            return

        action_map = {
            "/api/health": "get_health",
            "/api/topology": "get_topology",
            "/api/agents": "get_agents",
            "/api/activity": "get_activity",
            "/api/trust": "get_trust",
        }

        action = action_map.get(path)
        if not action:
            await self._send_response(send, 404, {"error": "unknown endpoint"})
            return

        try:
            result = await self._runtime.call(
                self._dashboard_agent,
                {"action": action},
            )
            await self._send_response(send, 200, result)
        except Exception as exc:
            logger.warning("Dashboard API error: %s", exc)
            await self._send_response(send, 500, {"error": str(exc)})

    async def _query_memory(self, sql: str, params: list[Any] | None = None) -> dict[str, Any]:
        result = await self._runtime.call(
            "memory",
            {"action": "ext_query", "sql": sql, "params": params or []},
        )
        return dict(result) if isinstance(result, dict) else result

    async def _handle_finance_api(self, send: Any) -> None:
        try:
            snap = await self._query_memory(
                "SELECT snapshot_date, total_value, equity_value, mf_value,"
                " etf_value, gold_value, debt_value, asset_allocation"
                " FROM finance_snapshots ORDER BY snapshot_date DESC LIMIT 1"
            )
            snap_rows = snap.get("rows", [])
            snapshot = None
            allocation: dict[str, float] = {}
            if snap_rows:
                r = snap_rows[0]
                snapshot = {
                    "snapshot_date": r[0],
                    "total_value": r[1],
                    "equity_value": r[2],
                    "mf_value": r[3],
                    "etf_value": r[4],
                    "gold_value": r[5],
                    "debt_value": r[6],
                }
                if r[7]:
                    allocation = json.loads(r[7])

            holdings_result = await self._query_memory(
                "SELECT symbol, name, asset_class, quantity, avg_price,"
                " current_price, current_value, pnl, pnl_pct, source"
                " FROM finance_holdings ORDER BY current_value DESC"
            )
            holdings = [
                {
                    "symbol": r[0],
                    "name": r[1],
                    "asset_class": r[2],
                    "quantity": r[3],
                    "avg_price": r[4],
                    "current_price": r[5],
                    "current_value": r[6],
                    "pnl": r[7],
                    "pnl_pct": r[8],
                    "source": r[9],
                }
                for r in holdings_result.get("rows", [])
            ]

            total_pnl = sum(h["pnl"] or 0 for h in holdings)
            total_cost = sum(h["quantity"] * h["avg_price"] for h in holdings)
            total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0

            fire_result = await self._query_memory(
                "SELECT target_corpus, monthly_expenses, withdrawal_rate,"
                " inflation_rate, expected_return"
                " FROM finance_fire_config LIMIT 1"
            )
            fire_config = None
            fire_rows = fire_result.get("rows", [])
            if fire_rows:
                fr = fire_rows[0]
                fire_config = {
                    "target_corpus": fr[0],
                    "monthly_expenses": fr[1],
                    "withdrawal_rate": fr[2] or 0.04,
                    "inflation_rate": fr[3] or 0.06,
                    "expected_return": fr[4] or 0.12,
                }

            history_result = await self._query_memory(
                "SELECT snapshot_date, total_value, equity_value, mf_value,"
                " gold_value, debt_value"
                " FROM finance_snapshots ORDER BY snapshot_date DESC LIMIT 30"
            )
            snapshots = [
                {
                    "date": r[0],
                    "total_value": r[1],
                    "equity_value": r[2],
                    "mf_value": r[3],
                    "gold_value": r[4],
                    "debt_value": r[5],
                }
                for r in reversed(history_result.get("rows", []))
            ]

            await self._send_response(
                send,
                200,
                {
                    "snapshot": snapshot,
                    "allocation": allocation,
                    "holdings": holdings,
                    "holdings_count": len(holdings),
                    "total_pnl": round(total_pnl, 2),
                    "total_pnl_pct": round(total_pnl_pct, 2),
                    "fire_config": fire_config,
                    "snapshots": snapshots,
                },
            )
        except Exception as exc:
            logger.warning("Finance API error: %s", exc)
            await self._send_response(send, 500, {"error": str(exc)})

    async def _handle_work_api(self, send: Any) -> None:
        try:
            actions_result = await self._query_memory(
                "SELECT id, title, status, priority, due_date, assigned_to"
                " FROM work_actions WHERE status != 'done'"
                " ORDER BY created_at DESC"
            )
            actions = [
                {
                    "id": r[0],
                    "title": r[1],
                    "status": r[2],
                    "priority": r[3],
                    "due_date": r[4],
                    "assigned_to": r[5],
                }
                for r in actions_result.get("rows", [])
            ]

            overdue = sum(1 for a in actions if a["status"] == "overdue")

            deleg_result = await self._query_memory(
                "SELECT id, delegated_to, task, status, due_date, last_update"
                " FROM work_delegations WHERE status != 'done'"
                " ORDER BY created_at DESC"
            )
            delegations = [
                {
                    "id": r[0],
                    "delegated_to": r[1],
                    "task": r[2],
                    "status": r[3],
                    "due_date": r[4],
                    "last_update": r[5],
                }
                for r in deleg_result.get("rows", [])
            ]
            stale = sum(1 for d in delegations if d["status"] == "stale")

            meetings_result = await self._query_memory(
                "SELECT id, title, meeting_date, attendees, notes"
                " FROM work_meetings ORDER BY meeting_date DESC LIMIT 10"
            )
            meetings = [
                {
                    "id": r[0],
                    "title": r[1],
                    "meeting_date": r[2],
                    "attendees": r[3],
                    "notes": r[4],
                }
                for r in meetings_result.get("rows", [])
            ]

            next_action = None
            if actions and _HAS_WORK:
                scored = [{**a, "score": _score_action(a)} for a in actions]
                scored.sort(key=lambda x: x["score"], reverse=True)
                next_action = scored[0]

            await self._send_response(
                send,
                200,
                {
                    "open_actions": len(actions),
                    "overdue_count": overdue,
                    "active_delegations": len(delegations),
                    "stale_delegations": stale,
                    "upcoming_meetings": len(meetings),
                    "next_action": next_action,
                    "actions": actions,
                    "delegations": delegations,
                    "meetings": meetings,
                },
            )
        except Exception as exc:
            logger.warning("Work API error: %s", exc)
            await self._send_response(send, 500, {"error": str(exc)})

    async def _handle_view(self, path: str, send: Any) -> None:
        view_id = path.removeprefix("/view/").strip("/")
        if not view_id or not view_id.isalnum():
            await self._send_html(send, 400, "<h1>Invalid view ID</h1>")
            return

        html = self._content_store.get(view_id)
        if html is None:
            await self._send_html(send, 404, "<h1>View not found or expired</h1>")
            return

        await self._send_html(send, 200, html)

    async def _serve_static(self, filename: str, send: Any) -> None:
        path = _STATIC_DIR / filename
        if not path.exists():
            await self._send_html(
                send,
                200,
                "<h1>Nexus Dashboard</h1><p>Static files not found.</p>",
            )
            return
        await self._send_html(send, 200, path.read_text())

    @staticmethod
    async def _send_response(
        send: Any,
        status: int,
        body: dict[str, Any],
    ) -> None:
        payload = json.dumps(body).encode()
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    [b"content-type", _CONTENT_TYPE_JSON.encode()],
                    [b"content-length", str(len(payload)).encode()],
                ],
            }
        )
        await send({"type": "http.response.body", "body": payload})

    @staticmethod
    async def _send_html(send: Any, status: int, html: str) -> None:
        payload = html.encode()
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    [b"content-type", _CONTENT_TYPE_HTML.encode()],
                    [b"content-length", str(len(payload)).encode()],
                ],
            }
        )
        await send({"type": "http.response.body", "body": payload})

    @staticmethod
    async def _handle_lifespan(receive: Any, send: Any) -> None:
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return

    async def start(self) -> None:
        config = uvicorn.Config(
            app=self,
            host="0.0.0.0",
            port=self._port,
            log_level="warning",
        )
        server = uvicorn.Server(config)
        self._server_task = asyncio.create_task(server.serve())
        logger.info("Dashboard listening on http://0.0.0.0:%d", self._port)

    async def stop(self) -> None:
        if hasattr(self, "_server_task") and not self._server_task.done():
            self._server_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._server_task
