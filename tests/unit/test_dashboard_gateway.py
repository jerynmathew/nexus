from __future__ import annotations

import json
from unittest.mock import AsyncMock

from nexus.dashboard.gateway import DashboardApp
from nexus.dashboard.views import ContentStore


def _make_app(**overrides):
    defaults = {
        "runtime": AsyncMock(),
        "content_store": ContentStore(views_dir="/tmp/nexus-test-views"),
    }
    defaults.update(overrides)
    return DashboardApp(**defaults)


async def _collect_response(app, path: str, method: str = "GET"):
    responses = []

    async def mock_send(data):
        responses.append(data)

    scope = {"type": "http", "path": path, "method": method}
    await app(scope, AsyncMock(), mock_send)
    return responses


class TestInit:
    def test_defaults(self) -> None:
        app = _make_app()
        assert app._port == 8080


class TestCall:
    async def test_non_http_scope(self) -> None:
        app = _make_app()
        responses = []
        await app({"type": "websocket"}, AsyncMock(), lambda d: responses.append(d))
        assert responses == []

    async def test_root_serves_static(self) -> None:
        app = _make_app()
        responses = await _collect_response(app, "/")
        assert responses[0]["status"] == 200

    async def test_404(self) -> None:
        app = _make_app()
        responses = await _collect_response(app, "/nonexistent")
        status = responses[0]["status"]
        assert status == 404


class TestHandleApi:
    async def test_health(self) -> None:
        runtime = AsyncMock()
        runtime.call.return_value = {"status": "ok", "uptime": 100}
        app = _make_app(runtime=runtime)
        responses = await _collect_response(app, "/api/health")
        assert responses[0]["status"] == 200
        body = json.loads(responses[1]["body"])
        assert body["status"] == "ok"

    async def test_topology(self) -> None:
        runtime = AsyncMock()
        runtime.call.return_value = {"agents": []}
        app = _make_app(runtime=runtime)
        responses = await _collect_response(app, "/api/topology")
        assert responses[0]["status"] == 200

    async def test_unknown_endpoint(self) -> None:
        app = _make_app()
        responses = await _collect_response(app, "/api/bogus")
        assert responses[0]["status"] == 404

    async def test_runtime_error(self) -> None:
        runtime = AsyncMock()
        runtime.call.side_effect = Exception("broken")
        app = _make_app(runtime=runtime)
        responses = await _collect_response(app, "/api/health")
        assert responses[0]["status"] == 500


class TestHandleView:
    async def test_invalid_view_id(self) -> None:
        app = _make_app()
        responses = await _collect_response(app, "/view/bad-id!")
        assert responses[0]["status"] == 400

    async def test_missing_view(self) -> None:
        app = _make_app()
        responses = await _collect_response(app, "/view/abc123")
        assert responses[0]["status"] == 404

    async def test_valid_view(self) -> None:
        store = ContentStore(views_dir="/tmp/nexus-test-views")
        view_id = store.store("<h1>Test</h1>")
        app = _make_app(content_store=store)
        responses = await _collect_response(app, f"/view/{view_id}")
        assert responses[0]["status"] == 200
        assert b"Test" in responses[1]["body"]


class TestSendResponse:
    async def test_json_encoding(self) -> None:
        responses = []

        async def mock_send(d):
            responses.append(d)

        await DashboardApp._send_response(mock_send, 200, {"key": "value"})
        assert responses[0]["status"] == 200
        body = json.loads(responses[1]["body"])
        assert body["key"] == "value"


class TestSendHtml:
    async def test_html_encoding(self) -> None:
        responses = []

        async def mock_send(d):
            responses.append(d)

        await DashboardApp._send_html(mock_send, 200, "<h1>Hello</h1>")
        assert responses[0]["status"] == 200
        assert b"Hello" in responses[1]["body"]


class TestDashboardRoutes:
    async def test_finance_route(self) -> None:
        app = _make_app()
        responses = await _collect_response(app, "/dashboard/finance")
        assert responses[0]["status"] == 200

    async def test_work_route(self) -> None:
        app = _make_app()
        responses = await _collect_response(app, "/dashboard/work")
        assert responses[0]["status"] == 200


class TestFinanceApi:
    async def test_returns_data(self) -> None:
        runtime = AsyncMock()
        runtime.call = AsyncMock(return_value={"rows": [], "columns": []})
        app = _make_app(runtime=runtime)
        responses = await _collect_response(app, "/api/finance")
        assert responses[0]["status"] == 200
        body = json.loads(responses[1]["body"])
        assert "holdings" in body
        assert "snapshot" in body

    async def test_handles_error(self) -> None:
        runtime = AsyncMock()
        runtime.call = AsyncMock(side_effect=Exception("db down"))
        app = _make_app(runtime=runtime)
        responses = await _collect_response(app, "/api/finance")
        assert responses[0]["status"] == 500


class TestWorkApi:
    async def test_returns_data(self) -> None:
        runtime = AsyncMock()
        runtime.call = AsyncMock(return_value={"rows": [], "columns": []})
        app = _make_app(runtime=runtime)
        responses = await _collect_response(app, "/api/work")
        assert responses[0]["status"] == 200
        body = json.loads(responses[1]["body"])
        assert "actions" in body
        assert "delegations" in body

    async def test_handles_error(self) -> None:
        runtime = AsyncMock()
        runtime.call = AsyncMock(side_effect=Exception("db down"))
        app = _make_app(runtime=runtime)
        responses = await _collect_response(app, "/api/work")
        assert responses[0]["status"] == 500


class TestLifespan:
    async def test_startup_shutdown(self) -> None:
        messages = [
            {"type": "lifespan.startup"},
            {"type": "lifespan.shutdown"},
        ]
        idx = 0

        async def receive():
            nonlocal idx
            msg = messages[idx]
            idx += 1
            return msg

        sent = []

        async def send(data):
            sent.append(data)

        await DashboardApp._handle_lifespan(receive, send)
        assert sent[0]["type"] == "lifespan.startup.complete"
        assert sent[1]["type"] == "lifespan.shutdown.complete"


class TestStartStop:
    async def test_stop_no_task(self) -> None:
        app = _make_app()
        await app.stop()

    async def test_stop_with_task(self) -> None:
        import asyncio

        app = _make_app()
        app._server_task = asyncio.create_task(asyncio.sleep(100))
        await app.stop()
        assert app._server_task.cancelled()
