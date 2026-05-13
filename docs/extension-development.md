# Extension Development Guide

Build custom extensions for Nexus — add commands, database tables, skills, and signal handlers.

---

## Quick Start

Create a new extension in 5 minutes:

```
my-extension/
├── pyproject.toml
├── src/my_extension/
│   ├── __init__.py
│   ├── extension.py
│   ├── commands.py
│   └── schema.py
└── tests/
```

### pyproject.toml

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "nexus-myextension"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["nexus>=0.1"]

[project.entry-points."nexus.extensions"]
myext = "my_extension.extension:MyExtension"

[tool.hatch.build.targets.wheel]
packages = ["src/my_extension"]
```

The `entry-points` section is how Nexus discovers your extension automatically.

### extension.py

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from nexus.extensions import NexusContext

from my_extension.commands import handle_mycommand
from my_extension.schema import MY_SCHEMA


class MyExtension:
    def __init__(self) -> None:
        self._ctx: NexusContext | None = None

    @property
    def name(self) -> str:
        return "my-extension"

    @property
    def version(self) -> str:
        return "0.1.0"

    async def on_load(self, nexus: NexusContext) -> None:
        self._ctx = nexus
        nexus.register_schema(MY_SCHEMA)
        nexus.register_command("mycommand", handle_mycommand)

    async def on_unload(self) -> None:
        self._ctx = None
```

### Install and Run

```bash
pip install -e ./my-extension
# Nexus auto-discovers via entry_points on next start
```

---

## NexusContext API

Your extension receives a `NexusContext` during `on_load()`. This is your API surface:

### Database Access

```python
# Read from your extension tables
result = await ctx.send_to_memory("ext_query", {
    "sql": "SELECT * FROM my_table WHERE tenant_id = ?",
    "params": [tenant_id],
})
rows = result.get("rows", [])
columns = result.get("columns", [])

# Write to your extension tables
await ctx.send_to_memory("ext_execute", {
    "sql": "INSERT INTO my_table (tenant_id, value) VALUES (?, ?)",
    "params": [tenant_id, "hello"],
})
```

- `ext_query` — SELECT only. Returns `{"columns": [...], "rows": [...]}`
- `ext_execute` — INSERT/UPDATE/DELETE. Blocks DROP/ALTER/CREATE.

### MCP Tool Calls

```python
# Call any registered MCP tool
result = await ctx.call_tool("tool_name", {"param": "value"})
# Returns string (JSON or text)
```

### LLM Access

```python
if ctx.llm:
    response = await ctx.llm.chat(
        messages=[{"role": "user", "content": "Analyze this data..."}],
    )
    text = response.content
```

### Charts and Views

```python
# Store HTML in ContentStore, get a viewable URL
url = ctx.store_view("<html>...</html>", title="My Chart")
# Returns: http://localhost:8080/view/abc123

# Get dashboard base URL
dash_url = ctx.dashboard_url("/dashboard/mypage")
```

### Extension Config

```yaml
# In config.yaml
extensions:
  my-extension:
    api_key: "..."
    refresh_interval: 300
```

```python
config = ctx.get_config("my-extension")
# {"api_key": "...", "refresh_interval": 300}
```

---

## Commands

Register commands that users invoke via `/mycommand` in Telegram:

```python
async def handle_mycommand(
    *,
    command: str,
    args: str,
    tenant_id: str,
    channel_id: str,
    send_reply: Callable[..., Awaitable[None]],
    nexus_context: NexusContext | None = None,
    **kwargs: Any,
) -> None:
    if not nexus_context:
        await send_reply(channel_id, "Service unavailable.")
        return

    await send_reply(channel_id, f"Hello from my extension! Args: {args}")
```

All keyword arguments. `nexus_context` comes via `**kwargs` — always check for `None`.

---

## Signal Handlers

React to events fired by Nexus core or other extensions:

```python
async def on_load(self, nexus: NexusContext) -> None:
    nexus.register_signal_handler("my_event", self._handle_event)

async def _handle_event(self, payload: dict[str, Any]) -> None:
    tenant_id = payload.get("tenant_id")
    # Process the event...
```

Built-in signal types:
- `inbound_message` — fired after every user message
- `scheduled_sync` — fired by scheduler for data sync
- Custom signals can be fired by other extensions

---

## Database Schema

Register SQL that runs on MemoryAgent startup:

```python
MY_SCHEMA = """
CREATE TABLE IF NOT EXISTS my_table (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    value TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""
```

- Always use `CREATE TABLE IF NOT EXISTS`
- Always include `tenant_id` for multi-tenant isolation
- FTS5 virtual tables and triggers are supported

---

## Skills

Register a directory of SKILL.md files:

```python
nexus.register_skill_dir(Path(__file__).parent / "skills")
```

Skill format:

```markdown
---
name: my-skill
description: What this skill does
execution: sequential
tool_groups: [google, search]
schedule: "0 9 * * *"        # Optional: cron for scheduled execution
active_hours_only: true       # Optional: only during active hours
---

Instructions for the LLM when this skill is triggered...
```

---

## Testing

Follow the project pattern — mock `NexusContext`:

```python
from unittest.mock import AsyncMock

ctx = AsyncMock()
ctx.send_to_memory = AsyncMock(return_value={"rows": [], "columns": []})
ctx.call_tool = AsyncMock(return_value="[]")
ctx.llm = None

await handle_mycommand(
    command="mycommand", args="test",
    tenant_id="t1", channel_id="c1",
    send_reply=AsyncMock(), nexus_context=ctx,
)
```

---

## Examples

See the built-in extensions for reference:

- `extensions/nexus-finance/` — 6 commands, 2 MCP servers, 7 tables, 8 signal handlers
- `extensions/nexus-work/` — 4 commands, 5 tables, 6 signal handlers, priority engine
