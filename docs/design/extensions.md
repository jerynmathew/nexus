# Design: Extension Architecture

> Status: Draft — foundational architecture for composable Nexus
> Priority: High — enables nexus-work and all future extensions
> Blocks: Work intelligence, finance, homelab extensions

---

## Vision

Nexus is the **platform**. Extensions add **capability**.

```
Nexus (core)
├── nexus-work        — work intelligence (pip install)
├── nexus-finance     — gold/stocks/analysis (pip install)
├── nexus-homelab     — Jellyfin/Paperless/Immich (skills-only)
├── nexus-health      — fitness/health tracking (future)
└── custom/           — user's own skills (directory)
```

The core platform provides: supervision, MCP, transports, governance, skills engine, memory, personas, dashboard. Extensions add domain-specific skills, commands, schemas, and configuration.

---

## Extension Types

### Type 1: Skill-Only Extension (directory)

A folder with SKILL.md files. No Python code. Installed by dropping into `skills/` or `~/.nexus/extensions/`.

```
~/.nexus/extensions/homelab/
├── extension.yaml         # metadata + config
├── skills/
│   ├── jellyfin-status/
│   │   └── SKILL.md
│   └── paperless-search/
│       └── SKILL.md
```

```yaml
# extension.yaml
name: nexus-homelab
version: 1.0.0
description: Homelab service monitoring and control
author: community
requires_nexus: ">=0.1.0"

skills:
  - jellyfin-status
  - paperless-search

config:
  jellyfin_url: "http://jellyfin:8096"
  paperless_url: "http://paperless:8000"
```

### Type 2: Code Extension (pip package)

A Python package that registers skills, commands, schemas, and hooks with Nexus.

```
nexus-work/
├── pyproject.toml
├── src/nexus_work/
│   ├── __init__.py        # extension entry point
│   ├── extension.py       # NexusExtension subclass
│   ├── commands.py        # /actions, /delegate, /commitments
│   ├── schema.py          # work_actions, work_delegations tables
│   ├── extractors.py      # action item extraction
│   └── skills/
│       ├── work-morning-briefing/
│       │   └── SKILL.md
│       ├── meeting-prep/
│       │   └── SKILL.md
│       └── evening-wrap/
│           └── SKILL.md
├── tests/
└── README.md
```

---

## Extension API

### NexusExtension Protocol

```python
from typing import Protocol

class NexusExtension(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def version(self) -> str: ...

    async def on_load(self, nexus: NexusContext) -> None:
        """Called when extension is loaded. Register skills, commands, schemas."""
        ...

    async def on_unload(self) -> None:
        """Called on shutdown. Cleanup resources."""
        ...
```

### NexusContext (what extensions can access)

```python
class NexusContext:
    """Provided to extensions during on_load(). Gives access to core capabilities."""

    def register_command(self, name: str, handler: CommandHandler) -> None:
        """Register a /command that the ConversationManager will handle."""
        ...

    def register_schema(self, sql: str) -> None:
        """Register SQL to execute on MemoryAgent startup (CREATE TABLE IF NOT EXISTS)."""
        ...

    def register_skill_dir(self, path: Path) -> None:
        """Register a directory of SKILL.md files to load."""
        ...

    def register_signal_handler(self, event_type: str, handler: SignalHandler) -> None:
        """Register a handler called for every inbound signal of this type."""
        ...

    def register_hook(self, hook: str, handler: HookHandler) -> None:
        """Register a lifecycle hook (pre_message, post_message, pre_meeting, etc.)."""
        ...

    async def send_to_memory(self, action: str, payload: dict) -> dict:
        """Query MemoryAgent."""
        ...

    async def send_to_dashboard(self, action: str, payload: dict) -> None:
        """Update dashboard state."""
        ...

    @property
    def llm(self) -> LLMClient:
        """Access the LLM client for lightweight calls (action extraction, etc.)."""
        ...
```

### Discovery

Code extensions discovered via Python entry points:

```toml
# nexus-work/pyproject.toml
[project.entry-points."nexus.extensions"]
work = "nexus_work.extension:WorkExtension"
```

Nexus scans `nexus.extensions` entry point group on startup:

```python
from importlib.metadata import entry_points

for ep in entry_points(group="nexus.extensions"):
    extension = ep.load()()  # instantiate
    await extension.on_load(nexus_context)
```

Skill-only extensions discovered by scanning `~/.nexus/extensions/*/extension.yaml`.

---

## Extension Lifecycle

```
Startup:
1. Nexus core starts (config, runtime, agents)
2. Scan for pip extensions (entry_points)
3. Scan for directory extensions (~/.nexus/extensions/)
4. For each extension:
   a. Validate requirements (requires_nexus version)
   b. Call on_load(nexus_context)
   c. Register commands, schemas, skills, hooks
5. MemoryAgent executes registered schemas
6. SkillManager loads registered skill directories
7. ConversationManager adds registered commands to dispatch

Shutdown:
1. For each extension: call on_unload()
2. Nexus core stops
```

---

## Example: nexus-work Extension

```python
# src/nexus_work/extension.py

from pathlib import Path
from nexus.extensions import NexusExtension, NexusContext

_SCHEMA = """
CREATE TABLE IF NOT EXISTS work_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT DEFAULT 'open',
    priority TEXT DEFAULT 'medium',
    due_date TEXT,
    source TEXT NOT NULL,
    assigned_to TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS work_delegations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    delegated_to TEXT NOT NULL,
    task TEXT NOT NULL,
    status TEXT DEFAULT 'assigned',
    due_date TEXT,
    last_update TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


class WorkExtension:
    @property
    def name(self) -> str:
        return "nexus-work"

    @property
    def version(self) -> str:
        return "0.1.0"

    async def on_load(self, nexus: NexusContext) -> None:
        nexus.register_schema(_SCHEMA)

        skills_dir = Path(__file__).parent / "skills"
        nexus.register_skill_dir(skills_dir)

        from nexus_work.commands import (
            handle_actions,
            handle_commitments,
            handle_delegate,
        )
        nexus.register_command("actions", handle_actions)
        nexus.register_command("delegate", handle_delegate)
        nexus.register_command("commitments", handle_commitments)

        nexus.register_signal_handler("inbound_message", self._extract_actions)

    async def _extract_actions(self, signal: dict, nexus: NexusContext) -> None:
        # LLM scans every inbound message for action items
        ...

    async def on_unload(self) -> None:
        pass
```

---

## What Nexus Core Needs to Change

To support extensions, the core needs:

| Change | Component | Effort |
|---|---|---|
| Extension loader (entry_points + directory scan) | `src/nexus/extensions.py` (new) | Medium |
| `NexusContext` class | `src/nexus/extensions.py` (new) | Medium |
| Command registry in ConversationManager | `src/nexus/agents/conversation.py` | Low |
| Schema registration in MemoryAgent | `src/nexus/agents/memory.py` | Low |
| Dynamic skill directory registration | `src/nexus/skills/manager.py` | Low |
| Signal hooks in ConversationManager | `src/nexus/agents/conversation.py` | Medium |
| Extension config in NexusConfig | `src/nexus/config.py` | Low |

**Total: ~5-7 tasks to build the extension system in Nexus core.**

---

## Ecosystem Vision

| Extension | Scope | Distribution |
|---|---|---|
| **nexus-work** | Action tracking, meeting prep, delegation, priority engine | pip (code + skills) |
| **nexus-finance** | Gold/stocks, charts, buy/sell recommendations | pip (code + skills) |
| **nexus-homelab** | Jellyfin, Paperless, Immich monitoring | directory (skills-only) |
| **nexus-health** | Fitness tracking, medication reminders | directory (skills-only) |
| **nexus-dev** | GitHub integration, code review tracking, CI monitoring | pip (code + skills) |
| **nexus-family** | Shared calendar, grocery lists, family coordination | directory (skills-only) |

Each extension has its own repo, its own release cycle, its own maintainers. The Nexus core stays lean, general-purpose, and stable.

---

## Open Questions

1. **Extension isolation**: Should extensions run in the same process or separate? (Same for now, separate later if needed)
2. **Extension conflicts**: What if two extensions register the same command? (First wins, log warning)
3. **Extension dependencies**: Can extensions depend on each other? (Not in v1)
4. **Extension marketplace**: Like VS Code marketplace? (Future — start with GitHub repos)
5. **Extension governance**: Should extensions go through trust system? (Yes — registered skills governed like all skills)
6. **Extension config**: How does the user configure extension-specific settings? (In config.yaml under `extensions:` key)
