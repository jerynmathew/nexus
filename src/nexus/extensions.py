"""Extension system — NexusExtension protocol, NexusContext API, and ExtensionLoader."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from importlib.metadata import entry_points
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import yaml

from nexus.llm.client import LLMClient
from nexus.mcp.manager import MCPManager

logger = logging.getLogger(__name__)

CommandHandler = Callable[..., Awaitable[None]]
SignalHandler = Callable[[dict[str, Any]], Awaitable[None]]
HookHandler = Callable[[dict[str, Any]], Awaitable[None]]

_ENTRY_POINT_GROUP = "nexus.extensions"


@runtime_checkable
class NexusExtension(Protocol):
    """Protocol that all Nexus extensions must implement."""

    @property
    def name(self) -> str: ...

    @property
    def version(self) -> str: ...

    async def on_load(self, nexus: NexusContext) -> None: ...

    async def on_unload(self) -> None: ...


class NexusContext:
    """API surface exposed to extensions during on_load().

    Gives extensions access to core capabilities without exposing internals.
    """

    def __init__(
        self,
        runtime: Any,
        llm: LLMClient | None = None,
        mcp: MCPManager | None = None,
        extensions_config: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self._runtime = runtime
        self._llm = llm
        self._mcp = mcp
        self._extensions_config = extensions_config or {}
        self._commands: dict[str, CommandHandler] = {}
        self._schemas: list[str] = []
        self._skill_dirs: list[Path] = []
        self._signal_handlers: dict[str, list[SignalHandler]] = {}
        self._hooks: dict[str, list[HookHandler]] = {}

    def register_command(self, name: str, handler: CommandHandler) -> None:
        """Register a /command that ConversationManager will dispatch to."""
        if name in self._commands:
            logger.warning("Extension command '/%s' already registered — skipping duplicate", name)
            return
        self._commands[name] = handler
        logger.info("Registered extension command: /%s", name)

    def register_schema(self, sql: str) -> None:
        """Register SQL to execute on MemoryAgent startup (CREATE TABLE IF NOT EXISTS)."""
        self._schemas.append(sql)

    def register_skill_dir(self, path: Path) -> None:
        """Register an additional directory of SKILL.md files."""
        if path.exists():
            self._skill_dirs.append(path)
            logger.info("Registered extension skill directory: %s", path)
        else:
            logger.warning("Extension skill directory does not exist: %s", path)

    def register_signal_handler(self, event_type: str, handler: SignalHandler) -> None:
        """Register a handler called for matching inbound signals."""
        self._signal_handlers.setdefault(event_type, []).append(handler)

    def register_hook(self, hook: str, handler: HookHandler) -> None:
        """Register a lifecycle hook (pre_message, post_message, etc.)."""
        self._hooks.setdefault(hook, []).append(handler)

    def get_config(self, extension_name: str) -> dict[str, Any]:
        """Get extension-specific config from config.yaml extensions section."""
        return dict(self._extensions_config.get(extension_name, {}))

    async def send_to_memory(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Send a message to MemoryAgent and return the response payload."""
        result = await self._runtime.call("memory", {"action": action, **payload})
        return dict(result) if isinstance(result, dict) else result

    async def send_to_dashboard(self, action: str, payload: dict[str, Any]) -> None:
        """Send a cast to DashboardServer (fire-and-forget)."""
        await self._runtime.cast("dashboard", {"action": action, **payload})

    @property
    def llm(self) -> LLMClient | None:
        return self._llm

    @property
    def mcp(self) -> MCPManager | None:
        return self._mcp

    async def call_tool(self, tool_name: str, arguments: dict[str, Any] | None = None) -> str:
        if not self._mcp:
            return "MCP not available"
        return await self._mcp.call_tool(tool_name, arguments or {})

    @property
    def commands(self) -> dict[str, CommandHandler]:
        """All registered extension commands."""
        return dict(self._commands)

    @property
    def schemas(self) -> list[str]:
        """All registered extension schemas."""
        return list(self._schemas)

    @property
    def skill_dirs(self) -> list[Path]:
        """All registered extension skill directories."""
        return list(self._skill_dirs)

    @property
    def signal_handlers(self) -> dict[str, list[SignalHandler]]:
        """All registered signal handlers."""
        return dict(self._signal_handlers)

    @property
    def hooks(self) -> dict[str, list[HookHandler]]:
        """All registered hooks."""
        return dict(self._hooks)


class ExtensionLoader:
    """Discovers and loads extensions from pip packages and directories."""

    def __init__(self, nexus_context: NexusContext) -> None:
        self._context = nexus_context
        self._extensions: list[NexusExtension] = []

    async def load_all(
        self,
        extension_dirs: list[Path] | None = None,
    ) -> list[NexusExtension]:
        """Load extensions from entry_points and directories."""
        await self._load_pip_extensions()
        if extension_dirs:
            for ext_dir in extension_dirs:
                await self._load_directory_extensions(ext_dir)
        logger.info("Loaded %d extension(s)", len(self._extensions))
        return self._extensions

    async def unload_all(self) -> None:
        """Call on_unload() on all loaded extensions."""
        for ext in reversed(self._extensions):
            try:
                await ext.on_unload()
            except Exception:
                logger.warning("Error unloading extension '%s'", ext.name, exc_info=True)
        self._extensions.clear()

    @property
    def extensions(self) -> list[NexusExtension]:
        """All loaded extensions."""
        return list(self._extensions)

    async def _load_pip_extensions(self) -> None:
        """Discover extensions via Python entry_points."""
        discovered = entry_points(group=_ENTRY_POINT_GROUP)
        for ep in discovered:
            try:
                ext_cls = ep.load()
                ext = ext_cls()
                await ext.on_load(self._context)
                self._extensions.append(ext)
                logger.info(
                    "Loaded pip extension: %s v%s (entry_point: %s)",
                    ext.name,
                    ext.version,
                    ep.name,
                )
            except Exception:
                logger.warning(
                    "Failed to load pip extension '%s'",
                    ep.name,
                    exc_info=True,
                )

    async def _load_directory_extensions(self, base_dir: Path) -> None:
        """Discover skill-only extensions from directories."""
        manifests = await asyncio.to_thread(self._scan_extension_dirs, base_dir)
        for raw, ext_dir in manifests:
            try:
                ext = _DirectoryExtension(raw, ext_dir)
                await ext.on_load(self._context)
                self._extensions.append(ext)
                logger.info(
                    "Loaded directory extension: %s v%s from %s",
                    ext.name,
                    ext.version,
                    ext_dir,
                )
            except Exception:
                logger.warning(
                    "Failed to load directory extension from %s",
                    ext_dir,
                    exc_info=True,
                )

    @staticmethod
    def _scan_extension_dirs(base_dir: Path) -> list[tuple[dict[str, Any], Path]]:
        if not base_dir.exists():
            return []
        results: list[tuple[dict[str, Any], Path]] = []
        for ext_dir in sorted(base_dir.iterdir()):
            manifest = ext_dir / "extension.yaml"
            if not manifest.exists():
                continue
            raw = yaml.safe_load(manifest.read_text())
            if isinstance(raw, dict):
                results.append((raw, ext_dir))
        return results


class _DirectoryExtension:
    """Skill-only extension loaded from a directory with extension.yaml."""

    def __init__(self, manifest: dict[str, Any], base_dir: Path) -> None:
        self._manifest = manifest
        self._base_dir = base_dir

    @property
    def name(self) -> str:
        return str(self._manifest.get("name", self._base_dir.name))

    @property
    def version(self) -> str:
        return str(self._manifest.get("version", "0.0.0"))

    async def on_load(self, nexus: NexusContext) -> None:
        skills_dir = self._base_dir / "skills"
        if skills_dir.exists():
            nexus.register_skill_dir(skills_dir)

    async def on_unload(self) -> None:
        pass
