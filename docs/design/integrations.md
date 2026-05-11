# Design: Integrations

> MCP-prioritized integration model, tool filtering, custom agents, and governance.

**Status:** Draft
**Module:** `src/nexus/agents/` (MCP via ConversationManager), `src/nexus/agents/homelab/` (custom agents, future)
**Principle:** Skills + MCP tools are the norm. Custom agents are the exception.

---

## Integration Hierarchy

When adding a new integration to Nexus, follow this decision tree:

```
Does an MCP server exist for this service?
├── YES → Use MCP. No custom code needed.
│         Configure as Docker sidecar in docker-compose.yaml.
│         LLM calls MCP tools directly via tool-use loop.
│
└── NO → Is the integration simple (REST API, stateless)?
    ├── YES → Write a skill (SKILL.md) that uses web_fetch or shell tools.
    │         No custom agent. ConversationManager executes the skill.
    │
    └── NO → Custom IntegrationAgent (exception).
             Only for: stateful connections, custom rendering,
             proprietary protocols, or cases requiring dedicated
             process lifecycle.
```

**Examples:**

| Service | Integration path | Why |
|---|---|---|
| Gmail, Calendar, Drive | MCP (Google Workspace MCP server) | Mature MCP server exists |
| Brave Search | MCP (Brave Search MCP server) | Mature MCP server exists |
| Slack | MCP (Slack MCP server) | Mature MCP server exists |
| Jellyfin | Skill (SKILL.md with REST calls) or custom agent | No MCP, REST API, may need custom agent for complex queries |
| Paperless | Skill (SKILL.md with REST calls) | No MCP, simple REST API |
| Home Assistant | MCP (Home Assistant MCP server exists) | MCP server available |
| Custom homelab service | Custom IntegrationAgent | No MCP, stateful, proprietary |

---

## MCP Architecture

### MCPManager

Manages connections to multiple MCP servers, merges tool schemas, routes tool calls:

```python
class MCPManager:
    """Connects to multiple MCP servers, merges tools, routes calls."""

    def __init__(self) -> None:
        self._clients: dict[str, MCPClient] = {}     # server_name → client
        self._tools: dict[str, ToolSchema] = {}       # tool_name → schema
        self._tool_to_server: dict[str, str] = {}     # tool_name → server_name
        self._ready = asyncio.Event()

    async def connect_all(self, servers: dict[str, MCPServerConfig]) -> None:
        for name, config in servers.items():
            if not config.enabled:
                continue
            try:
                client = MCPClient(name, config.url)
                await client.connect()
                for tool in client.tools:
                    self._tools[tool.name] = tool
                    self._tool_to_server[tool.name] = name
                self._clients[name] = client
            except Exception as exc:
                logger.warning("MCP server '%s' failed to connect: %s", name, exc)
        self._ready.set()

    async def call_tool(self, tool_name: str, arguments: dict) -> str:
        server_name = self._tool_to_server.get(tool_name)
        if not server_name:
            raise ToolNotFoundError(f"Unknown tool: {tool_name}")
        client = self._clients[server_name]
        return await client.call_tool(tool_name, arguments)

    def filter_tools(self, tool_groups: list[str]) -> list[ToolSchema]:
        """Return only tools belonging to the specified groups."""
        if not tool_groups:
            return list(self._tools.values())
        return [t for t in self._tools.values() if t.group in tool_groups]

    @property
    def all_tools(self) -> list[ToolSchema]:
        return list(self._tools.values())

    async def health_check(self) -> dict[str, bool]:
        results = {}
        for name, client in self._clients.items():
            results[name] = await client.ping()
        return results
```

### MCPClient

Per-server connection with long-lived session:

```python
class MCPClient:
    """Connection to a single MCP server."""

    def __init__(self, name: str, url: str) -> None:
        self.name = name
        self._url = url
        self._session: aiohttp.ClientSession | None = None  # long-lived, reused
        self._session_id: str | None = None
        self._request_id = itertools.count(1)                # unique per request
        self.tools: list[ToolSchema] = []

    async def connect(self) -> None:
        self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
        # Initialize MCP session
        response = await self._rpc("initialize", {...})
        self._session_id = response.get("session_id")
        # Fetch tool list
        tools_response = await self._rpc("tools/list", {})
        self.tools = [ToolSchema.from_mcp(t) for t in tools_response.get("tools", [])]

    async def call_tool(self, name: str, arguments: dict) -> str:
        result = await self._rpc("tools/call", {"name": name, "arguments": arguments})
        return result.get("content", "")

    async def _rpc(self, method: str, params: dict) -> dict:
        payload = {
            "jsonrpc": "2.0",
            "id": next(self._request_id),
            "method": method,
            "params": params,
        }
        async with self._session.post(self._url, json=payload) as resp:
            raw = await resp.text()
            return _parse_sse(raw)
```

**Key decisions (learned from Vigil):**
- **Long-lived `aiohttp.ClientSession`** — no new TCP connection per request (issue A6)
- **`itertools.count` for request IDs** — no hardcoded `id: 2` (issue A7)
- **Proper SSE parser** — accumulates `data:` lines, handles multi-line payloads (issue I1)
- **`asyncio.Event` for readiness** — no 30-second busy-wait (issue A2)

### Auto-Reconnect

```python
async def _ensure_connected(self, server_name: str) -> MCPClient:
    client = self._clients.get(server_name)
    if client is None or not await client.ping():
        logger.info("Reconnecting MCP server '%s'", server_name)
        config = self._configs[server_name]
        client = MCPClient(server_name, config.url)
        await client.connect()
        # Re-register tools
        for tool in client.tools:
            self._tools[tool.name] = tool
            self._tool_to_server[tool.name] = server_name
        self._clients[server_name] = client
    return client
```

Periodic health checks (via SchedulerAgent) detect failed servers. Auto-reconnect restores tools when the server comes back.

---

## Tool Filtering (Intent-Based)

Sending all tool schemas to the LLM on every request is expensive (all tools ≈ 12-15K tokens) and reduces accuracy (LLM confused by irrelevant tools).

**Solution:** Classify intent first (cheap model), then send only relevant tools.

### Tool Groups

```yaml
# config.yaml
mcp:
  tool_groups:
    gmail: [search_gmail_messages, get_gmail_message_content, send_gmail_message, draft_gmail_message, list_gmail_labels]
    calendar: [list_calendars, get_events, manage_event, query_freebusy]
    tasks: [list_task_lists, list_tasks, get_task, manage_task]
    drive: [search_drive_files, get_drive_file_content, create_drive_file]
    search: [brave_web_search, brave_local_search]
```

Or auto-derived from MCP server names (each server's tools form a group).

### Filtering Flow

```
User: "Check my email"
  → IntentClassifier: tool_groups=["gmail"]
  → MCPManager.filter_tools(["gmail"]) → 5 tools (~3K tokens)
  → LLM call with only gmail tools

User: "Check my email and what's on my calendar"
  → IntentClassifier: tool_groups=["gmail", "calendar"]
  → MCPManager.filter_tools(["gmail", "calendar"]) → 9 tools (~4.5K tokens)

User: "Tell me a joke" (no tools needed)
  → IntentClassifier: tool_groups=[]
  → No tools sent → pure LLM response
```

**Impact:** 3-5x token reduction per request. Virtually eliminates rate-limit issues.

---

## Custom IntegrationAgent (Exception Path)

For services without MCP servers that need stateful connections or custom rendering:

```python
class IntegrationAgent(AgentProcess):
    """Base class for custom service integration agents.

    Use ONLY when MCP doesn't cover the use case.
    """

    def __init__(self, name: str, service_config: ServiceConfig, **kwargs: Any) -> None:
        super().__init__(name, **kwargs)
        self._config = service_config
        self._client: httpx.AsyncClient | None = None

    async def on_start(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=self._config.url,
            headers=self._auth_headers(),
            timeout=30.0,
        )

    async def on_stop(self) -> None:
        if self._client:
            await self._client.aclose()

    async def health_check(self) -> bool:
        try:
            resp = await self._client.get(self._health_endpoint)
            return resp.is_success
        except httpx.RequestError:
            return False

    def _auth_headers(self) -> dict[str, str]:
        if self._config.api_key:
            return {"Authorization": f"Bearer {self._config.api_key}"}
        return {}
```

**When to use this:**
- Service has no MCP server AND no simple REST API a skill could call
- Integration needs a persistent connection (WebSocket, streaming)
- Custom rendering or UI beyond what LLM text output provides
- Proprietary protocol that needs dedicated client code

**Custom agents are supervised** under `integrations (ONE_FOR_ONE)` — they get the same crash recovery as everything else.

---

## Governance

All integration paths — MCP tools, skills, and custom agents — are governed identically:

| Integration path | Policy check point | Audit | Trust |
|---|---|---|---|
| MCP tool call | ConversationManager `_tool_use_loop`, before each call | Every call logged | Yes |
| Skill execution | ConversationManager `_execute_skill`, before each tool call within skill | Every call logged | Yes |
| Custom agent `ask()` | ConversationManager, before routing to custom agent | Response logged | Yes |

**No governance gap between paths.** A Gmail action via MCP and a Jellyfin action via custom agent go through the same policy check, same audit sink, same trust score update.

---

## Docker Compose Layout

```yaml
services:
  nexus:
    image: nexus:latest
    depends_on: [mcp-google]
    volumes:
      - ./config:/app/config
      - ./data:/app/data
      - ./personas:/app/personas

  mcp-google:
    image: taylorwilsdon/google_workspace_mcp:latest
    volumes:
      - ./data/mcp-google:/app/data
    restart: unless-stopped

  mcp-search:
    image: mcp/brave-search:latest
    environment:
      - BRAVE_API_KEY=${BRAVE_API_KEY}
    restart: unless-stopped
    profiles: [search]                    # optional — enable with --profile search

  mcp-slack:
    image: mcp/slack:latest
    environment:
      - SLACK_BOT_TOKEN=${SLACK_BOT_TOKEN}
    restart: unless-stopped
    profiles: [slack]                     # optional

  ollama:
    image: ollama/ollama:latest
    volumes:
      - ollama_data:/root/.ollama
    restart: unless-stopped
    profiles: [local-llm]                 # optional — enable with --profile local-llm
```

Each MCP server is an independent Docker sidecar. Nexus connects via HTTP. Crash recovery: Docker `restart: unless-stopped` for sidecars, Civitas supervision for Nexus agents.

---

## Adding a New MCP Integration

1. Find or build an MCP server for the service
2. Add it as a sidecar in `docker-compose.yaml`
3. Add the server URL to `config.yaml`:
   ```yaml
   mcp:
     servers:
       new-service:
         url: "http://mcp-new-service:8080/mcp"
         enabled: true
   ```
4. Optionally define tool groups for intent-based filtering
5. No code changes to Nexus. Tools auto-discovered on next start.

**This is the power of MCP-prioritized architecture:** adding Gmail, Calendar, Slack, web search — all config, zero code.
