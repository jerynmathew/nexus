from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from nexus.config import MCPServerEntry
from nexus.mcp.manager import MCPManager


def _entry(**overrides) -> MCPServerEntry:
    defaults = {
        "name": "test",
        "transport": "streamable-http",
        "url": "http://test:8080/mcp",
        "enabled": True,
    }
    defaults.update(overrides)
    return MCPServerEntry(**defaults)


def _mock_tool(name: str = "tool1", desc: str = "desc", schema: dict | None = None):
    t = SimpleNamespace()
    t.name = name
    t.description = desc
    t.inputSchema = schema or {"type": "object"}
    return t


class TestInit:
    def test_empty_state(self) -> None:
        m = MCPManager()
        assert m._tool_schemas == {}
        assert m._clients == {}
        assert not m._ready.is_set()


class TestToOpenaiTool:
    def test_converts_format(self) -> None:
        result = MCPManager._to_openai_tool(
            {"name": "search", "description": "Find stuff", "input_schema": {"type": "object"}}
        )
        assert result["type"] == "function"
        assert result["function"]["name"] == "search"


class TestConnectAll:
    async def test_skips_disabled(self) -> None:
        m = MCPManager()
        m._connect_server = AsyncMock()
        await m.connect_all([_entry(enabled=False)])
        m._connect_server.assert_not_called()
        assert m._ready.is_set()

    async def test_connects_enabled(self) -> None:
        m = MCPManager()
        m._connect_server = AsyncMock()
        await m.connect_all([_entry()])
        m._connect_server.assert_called_once()
        assert m._ready.is_set()


class TestConnectServer:
    async def test_success_registers_tools(self) -> None:
        m = MCPManager()
        entry = _entry()

        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_tools = MagicMock()
        mock_tools.tools = [_mock_tool("search_gmail")]
        mock_session.list_tools = AsyncMock(return_value=mock_tools)

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=(MagicMock(), MagicMock(), None))

        with (
            patch("nexus.mcp.manager.streamablehttp_client", return_value=mock_ctx),
            patch("nexus.mcp.manager.ClientSession", return_value=mock_session),
        ):
            await m._connect_server(entry)

        assert "search_gmail" in m._tool_schemas
        assert m._tool_to_server["search_gmail"] == "test"

    async def test_failure_logs_warning(self) -> None:
        m = MCPManager()
        entry = _entry()

        with patch("nexus.mcp.manager.streamablehttp_client", side_effect=Exception("conn err")):
            await m._connect_server(entry)

        assert len(m._tool_schemas) == 0


class TestCreateClient:
    async def test_unsupported_transport(self) -> None:
        m = MCPManager()
        entry = _entry(transport="grpc")

        with pytest.raises(ValueError, match="Unsupported"):
            await m._create_client(entry)

    async def test_sse_transport(self) -> None:
        m = MCPManager()
        entry = _entry(transport="sse")

        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.list_tools = AsyncMock(return_value=MagicMock(tools=[_mock_tool()]))

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=(MagicMock(), MagicMock(), None))

        with (
            patch("nexus.mcp.manager.sse_client", return_value=mock_ctx),
            patch("nexus.mcp.manager.ClientSession", return_value=mock_session),
        ):
            _session, tools = await m._create_client(entry)

        assert len(tools) == 1

    async def test_stdio_transport(self) -> None:
        m = MCPManager()
        entry = _entry(transport="stdio", command="test-cmd", url=None)

        mock_session = AsyncMock()
        mock_session.initialize = AsyncMock()
        mock_session.list_tools = AsyncMock(return_value=MagicMock(tools=[_mock_tool()]))

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=(MagicMock(), MagicMock()))

        with (
            patch("nexus.mcp.manager.stdio_client", return_value=mock_ctx),
            patch("nexus.mcp.manager.ClientSession", return_value=mock_session),
        ):
            _session, tools = await m._create_client(entry)

        assert len(tools) == 1


class TestCallTool:
    async def test_unknown_tool(self) -> None:
        m = MCPManager()
        result = await m.call_tool("nonexistent", {})
        assert "Unknown tool" in result

    async def test_no_session_triggers_reconnect(self) -> None:
        m = MCPManager()
        m._tool_to_server["tool1"] = "srv1"
        m._server_configs["srv1"] = _entry(name="srv1")
        m._connect_server = AsyncMock()
        result = await m.call_tool("tool1", {})
        assert "unavailable" in result

    async def test_success(self) -> None:
        m = MCPManager()
        m._tool_to_server["tool1"] = "srv1"
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.isError = False
        mock_result.content = [SimpleNamespace(text="result text")]
        mock_session.call_tool.return_value = mock_result
        m._clients["_session_srv1"] = mock_session

        result = await m.call_tool("tool1", {"q": "test"})
        assert result == "result text"

    async def test_failure_triggers_reconnect(self) -> None:
        m = MCPManager()
        m._tool_to_server["tool1"] = "srv1"
        m._server_configs["srv1"] = _entry(name="srv1")
        mock_session = AsyncMock()
        mock_session.call_tool.side_effect = Exception("timeout")
        m._clients["_session_srv1"] = mock_session
        m._connect_server = AsyncMock()

        result = await m.call_tool("tool1", {})
        assert "failed" in result


class TestParseToolResult:
    def test_text_blocks(self) -> None:
        result = MagicMock()
        result.isError = False
        result.content = [SimpleNamespace(text="hello"), SimpleNamespace(text="world")]
        assert MCPManager._parse_tool_result(result) == "hello\nworld"

    def test_error_result(self) -> None:
        result = MagicMock()
        result.isError = True
        result.content = [SimpleNamespace(text="bad request")]
        assert "Tool error" in MCPManager._parse_tool_result(result)

    def test_image_block(self) -> None:
        result = MagicMock()
        result.isError = False

        block = SimpleNamespace(data=b"img")
        block.mimeType = "image/png"

        result.content = [block]
        parsed = MCPManager._parse_tool_result(result)
        assert "Image" in parsed

    def test_resource_block(self) -> None:
        result = MagicMock()
        result.isError = False

        class ResBlock:
            resource = SimpleNamespace(uri="file:///test")

        result.content = [ResBlock()]
        parsed = MCPManager._parse_tool_result(result)
        assert "Resource" in parsed

    def test_empty_result(self) -> None:
        result = MagicMock()
        result.isError = False
        result.content = []
        assert MCPManager._parse_tool_result(result) == "(empty result)"


class TestFilterTools:
    def test_empty_groups_returns_all(self) -> None:
        m = MCPManager()
        m._tool_schemas = {"a": {"type": "function"}, "b": {"type": "function"}}
        assert len(m.filter_tools([])) == 2

    def test_by_group(self) -> None:
        m = MCPManager()
        m._tool_schemas = {"a": {}, "b": {}}
        m._tool_to_group = {"a": "gmail", "b": "calendar"}
        result = m.filter_tools(["gmail"])
        assert len(result) == 1

    def test_prefix_fallback(self) -> None:
        m = MCPManager()
        m._tool_schemas = {"search_gmail": {}, "list_tasks": {}}
        m._tool_to_group = {"search_gmail": "google", "list_tasks": "google"}
        result = m.filter_tools(["gmail"])
        assert len(result) == 1


class TestHealthCheck:
    async def test_healthy_server(self) -> None:
        m = MCPManager()
        m._server_configs["srv1"] = _entry(name="srv1")
        mock_session = AsyncMock()
        m._clients["_session_srv1"] = mock_session
        result = await m.health_check()
        assert result["srv1"] is True

    async def test_unhealthy_server(self) -> None:
        m = MCPManager()
        m._server_configs["srv1"] = _entry(name="srv1")
        mock_session = AsyncMock()
        mock_session.send_ping.side_effect = Exception("dead")
        m._clients["_session_srv1"] = mock_session
        result = await m.health_check()
        assert result["srv1"] is False

    async def test_no_session(self) -> None:
        m = MCPManager()
        m._server_configs["srv1"] = _entry(name="srv1")
        result = await m.health_check()
        assert result["srv1"] is False


class TestClose:
    async def test_cleans_up(self) -> None:
        m = MCPManager()
        m._server_configs["srv1"] = _entry(name="srv1")
        m._clients["_session_srv1"] = AsyncMock()
        m._clients["_ctx_srv1"] = AsyncMock()
        m._tool_schemas["t1"] = {}
        m._tool_to_server["t1"] = "srv1"
        await m.close()
        assert m._tool_schemas == {}
        assert m._clients == {}
