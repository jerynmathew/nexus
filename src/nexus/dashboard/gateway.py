from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from pathlib import Path
from typing import Any

from nexus.dashboard.views import ContentStore

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
        elif method == "GET" and path.startswith("/api/"):
            await self._handle_api(path, send)
        elif method == "GET" and path.startswith("/view/"):
            await self._handle_view(path, send)
        else:
            await self._send_response(send, 404, {"error": "not found"})

    async def _handle_api(self, path: str, send: Any) -> None:
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
        import uvicorn

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
