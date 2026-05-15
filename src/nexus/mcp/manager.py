from __future__ import annotations

import asyncio
import contextlib
import logging
import re as _re
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client

from nexus.config import MCPServerEntry

_ANSI_ESCAPE = _re.compile(r"\x1b\[[0-9;]*m")

logger = logging.getLogger(__name__)


class MCPManager:
    def __init__(self) -> None:
        self._clients: dict[str, Any] = {}
        self._tool_schemas: dict[str, dict[str, Any]] = {}
        self._tool_to_server: dict[str, str] = {}
        self._tool_to_group: dict[str, str] = {}
        self._server_configs: dict[str, MCPServerEntry] = {}
        self._ready = asyncio.Event()

    async def connect_all(self, servers: list[MCPServerEntry]) -> None:
        for server in servers:
            if not server.enabled:
                continue
            self._server_configs[server.name] = server
            await self._connect_server(server)
        self._ready.set()

    async def _connect_server(self, server: MCPServerEntry) -> None:
        try:
            client, tools = await self._create_client(server)
            self._clients[server.name] = client
            group = server.tool_group or server.name
            for tool in tools:
                name = tool.get("name", "")
                self._tool_schemas[name] = self._to_openai_tool(tool)
                self._tool_to_server[name] = server.name
                self._tool_to_group[name] = group
            logger.info(
                "Connected to MCP server '%s': %d tools",
                server.name,
                len(tools),
            )
        except Exception:
            logger.warning("Failed to connect MCP server '%s'", server.name, exc_info=True)

    async def _create_client(
        self,
        server: MCPServerEntry,
    ) -> tuple[Any, list[dict[str, Any]]]:
        if server.transport in ("sse", "streamable-http") and server.url:
            if server.transport == "sse":
                client_ctx = sse_client(url=server.url)
            else:
                client_ctx = streamablehttp_client(url=server.url)

            read_stream, write_stream, _ = await client_ctx.__aenter__()
            session = ClientSession(read_stream, write_stream)
            await session.__aenter__()
            await session.initialize()

            result = await session.list_tools()
            tools = [
                {"name": t.name, "description": t.description or "", "input_schema": t.inputSchema}
                for t in result.tools
            ]
            self._clients[f"_ctx_{server.name}"] = client_ctx
            self._clients[f"_session_{server.name}"] = session
            return session, tools

        if server.transport == "stdio" and server.command:
            params = StdioServerParameters(
                command=server.command,
                args=server.args,
                env={**server.env} if server.env else None,
            )
            client_ctx = stdio_client(params)
            read_stream, write_stream = await client_ctx.__aenter__()
            session = ClientSession(read_stream, write_stream)
            await session.__aenter__()
            await session.initialize()

            result = await session.list_tools()
            tools = [
                {"name": t.name, "description": t.description or "", "input_schema": t.inputSchema}
                for t in result.tools
            ]
            self._clients[f"_ctx_{server.name}"] = client_ctx
            self._clients[f"_session_{server.name}"] = session
            return session, tools

        raise ValueError(f"Unsupported MCP transport: {server.transport}")

    @staticmethod
    def _to_openai_tool(mcp_tool: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": mcp_tool["name"],
                "description": mcp_tool.get("description", ""),
                "parameters": mcp_tool.get("input_schema", {}),
            },
        }

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> str:
        server_name = self._tool_to_server.get(tool_name)
        if not server_name:
            return f"Unknown tool: {tool_name}"

        session = self._clients.get(f"_session_{server_name}")
        if session is None:
            session = await self._reconnect_server(server_name)
            if session is None:
                return f"MCP server '{server_name}' unavailable"

        try:
            result = await session.call_tool(tool_name, arguments=arguments)
            return self._parse_tool_result(result)
        except Exception as exc:
            logger.warning("MCP tool '%s' failed: %s", tool_name, exc)
            await self._reconnect_server(server_name)
            clean = _ANSI_ESCAPE.sub("", str(exc))
            return f"Tool '{tool_name}' failed: {clean[:2000]}"

    async def _reconnect_server(self, server_name: str) -> Any | None:
        config = self._server_configs.get(server_name)
        if config:
            logger.info("Reconnecting to MCP server '%s'", server_name)
            await self._connect_server(config)
        return self._clients.get(f"_session_{server_name}")

    @staticmethod
    def _parse_tool_result(result: Any) -> str:
        parts: list[str] = []

        if hasattr(result, "isError") and result.isError:
            for block in result.content:
                if hasattr(block, "text"):
                    parts.append(block.text)
            error_text = "\n".join(parts) if parts else "Unknown error"
            clean = _ANSI_ESCAPE.sub("", error_text)
            return f"Tool error: {clean[:2000]}"

        for block in result.content:
            if hasattr(block, "text"):
                parts.append(block.text)
            elif hasattr(block, "data") and hasattr(block, "mimeType"):
                parts.append(f"[Image: {block.mimeType}]")
            elif hasattr(block, "resource"):
                res = block.resource
                uri = getattr(res, "uri", "unknown")
                parts.append(f"[Resource: {uri}]")

        return "\n".join(parts) if parts else "(empty result)"

    def filter_tools(self, tool_groups: list[str]) -> list[dict[str, Any]]:
        if not tool_groups:
            return list(self._tool_schemas.values())

        by_group = [
            schema
            for name, schema in self._tool_schemas.items()
            if self._tool_to_group.get(name) in tool_groups
        ]
        if by_group:
            return by_group

        by_prefix = [
            schema
            for name, schema in self._tool_schemas.items()
            if any(group in name for group in tool_groups)
        ]
        return by_prefix

    def all_tool_schemas(self) -> list[dict[str, Any]]:
        return list(self._tool_schemas.values())

    async def health_check(self) -> dict[str, bool]:
        results: dict[str, bool] = {}
        for name in self._server_configs:
            session = self._clients.get(f"_session_{name}")
            if session is None:
                results[name] = False
                continue
            try:
                await session.send_ping()
                results[name] = True
            except Exception:
                logger.debug("MCP health check failed for '%s'", name)
                results[name] = False
        return results

    async def close(self) -> None:
        for name in list(self._server_configs.keys()):
            session = self._clients.pop(f"_session_{name}", None)
            ctx = self._clients.pop(f"_ctx_{name}", None)
            if session:
                with contextlib.suppress(Exception):
                    await session.__aexit__(None, None, None)
            if ctx:
                with contextlib.suppress(Exception):
                    await ctx.__aexit__(None, None, None)
        self._clients.clear()
        self._tool_schemas.clear()
        self._tool_to_server.clear()
        self._tool_to_group.clear()
