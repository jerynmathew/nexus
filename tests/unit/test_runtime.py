from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from nexus.agents.conversation import ConversationManager
from nexus.agents.memory import MemoryAgent
from nexus.agents.scheduler import SchedulerAgent
from nexus.config import NexusConfig
from nexus.runtime import (
    _load_extensions,
    _register_agents_with_dashboard,
    _setup_media_handler,
    _start_dashboard,
    _start_mcp,
    _start_telegram,
    build_runtime,
    run_nexus,
    seed_on_start,
)


def _cfg(tmp_path: Path, **overrides) -> NexusConfig:
    defaults = {
        "memory": {"db_path": str(tmp_path / "test.db")},
        "persona_dir": str(tmp_path / "personas"),
        "users_dir": str(tmp_path / "users"),
        "data_dir": str(tmp_path),
    }
    defaults.update(overrides)
    return NexusConfig(**defaults)


class TestBuildRuntime:
    def test_builds_without_error(self, tmp_path: Path) -> None:
        runtime, agents = build_runtime(_cfg(tmp_path))
        assert runtime is not None
        assert "memory" in agents
        assert "conversation_manager" in agents
        assert "scheduler" in agents
        assert "dashboard" in agents

    def test_agents_have_correct_types(self, tmp_path: Path) -> None:
        _, agents = build_runtime(_cfg(tmp_path))
        assert isinstance(agents["memory"], MemoryAgent)
        assert isinstance(agents["conversation_manager"], ConversationManager)
        assert isinstance(agents["scheduler"], SchedulerAgent)


class TestSeedOnStart:
    async def test_no_seed_users(self, tmp_path: Path) -> None:
        runtime = AsyncMock()
        config = _cfg(tmp_path)
        await seed_on_start(runtime, config)
        runtime.send.assert_not_called()

    async def test_with_seed_users(self, tmp_path: Path) -> None:
        runtime = AsyncMock()
        config = _cfg(
            tmp_path,
            seed_users=[
                {
                    "name": "Alice",
                    "tenant_id": "alice",
                    "role": "admin",
                    "persona": "default",
                    "timezone": "UTC",
                    "telegram_user_id": 123,
                }
            ],
        )
        await seed_on_start(runtime, config)
        runtime.send.assert_called_once()
        payload = runtime.send.call_args[0][1]
        assert payload["action"] == "seed_tenants"
        assert len(payload["users"]) == 1


class TestRegisterAgentsWithDashboard:
    async def test_sends_health_for_each(self) -> None:
        runtime = AsyncMock()
        agent = MagicMock()
        agent.status.value.lower.return_value = "running"
        agents = {"memory": agent, "conversation_manager": agent}
        await _register_agents_with_dashboard(runtime, agents)
        assert runtime.cast.call_count == 2


class TestSetupMediaHandler:
    def test_without_stt(self) -> None:
        conv = ConversationManager(name="test")
        conv._llm = MagicMock()
        with patch("nexus.runtime._HAS_STT", False):
            _setup_media_handler(conv)
        assert conv._media_handler is not None

    def test_with_llm_vision(self) -> None:
        conv = ConversationManager(name="test")
        conv._llm = MagicMock()
        with patch("nexus.runtime._HAS_STT", False):
            _setup_media_handler(conv)
        assert conv._media_handler is not None
        assert conv._media_handler.has_vision


class TestStartMcp:
    async def test_no_servers(self, tmp_path: Path) -> None:
        conv = ConversationManager(name="test")
        config = _cfg(tmp_path)
        result = await _start_mcp(config, conv)
        assert result is None

    async def test_with_servers(self, tmp_path: Path) -> None:
        conv = ConversationManager(name="test")
        config = _cfg(
            tmp_path,
            mcp={
                "servers": [
                    {"name": "test", "transport": "streamable-http", "url": "http://test:8080/mcp"}
                ]
            },
        )
        with patch("nexus.mcp.manager.MCPManager.connect_all", new_callable=AsyncMock):
            result = await _start_mcp(config, conv)
        assert result is not None


class TestStartDashboard:
    async def test_disabled(self, tmp_path: Path) -> None:
        config = _cfg(tmp_path, dashboard={"enabled": False})
        result = await _start_dashboard(config, AsyncMock(), {}, MagicMock(), None)
        assert result is None

    async def test_enabled(self, tmp_path: Path) -> None:
        config = _cfg(tmp_path, dashboard={"enabled": True, "port": 0, "host": "localhost"})
        runtime = AsyncMock()
        conv = MagicMock()
        with patch("nexus.dashboard.gateway.DashboardApp.start", new_callable=AsyncMock):
            result = await _start_dashboard(config, runtime, {}, conv, None)
        assert result is not None


class TestStartTelegram:
    async def test_no_telegram_config(self, tmp_path: Path) -> None:
        conv = ConversationManager(name="test")
        config = _cfg(tmp_path)
        result = await _start_telegram(config, AsyncMock(), conv)
        assert result is None

    async def test_with_telegram(self, tmp_path: Path) -> None:
        conv = ConversationManager(name="test")
        config = _cfg(
            tmp_path,
            telegram={"bot_token": "fake", "allowed_user_ids": []},
            seed_users=[
                {
                    "name": "A",
                    "tenant_id": "a",
                    "role": "admin",
                    "persona": "default",
                    "timezone": "UTC",
                    "telegram_user_id": 123,
                }
            ],
        )
        with patch("nexus.transport.telegram.TelegramTransport.start", new_callable=AsyncMock):
            result = await _start_telegram(config, AsyncMock(), conv)
        assert result is not None

    async def test_tenant_map_resolution(self, tmp_path: Path) -> None:
        conv = ConversationManager(name="test")
        config = _cfg(
            tmp_path,
            telegram={"bot_token": "fake", "allowed_user_ids": []},
            seed_users=[
                {
                    "name": "Bob",
                    "tenant_id": "bob",
                    "role": "admin",
                    "persona": "default",
                    "timezone": "UTC",
                    "telegram_user_id": 456,
                },
                {
                    "name": "Eve",
                    "tenant_id": "eve",
                    "role": "user",
                    "persona": "default",
                    "timezone": "UTC",
                },
            ],
        )
        with patch("nexus.transport.telegram.TelegramTransport.start", new_callable=AsyncMock):
            result = await _start_telegram(config, AsyncMock(), conv)
        assert result is not None


class TestLoadExtensions:
    async def test_no_extensions(self, tmp_path: Path) -> None:
        config = _cfg(tmp_path)
        runtime = AsyncMock()
        conv = ConversationManager(name="test")
        conv._llm = MagicMock()
        conv._mcp = None
        agents = {"memory": MagicMock(), "conversation_manager": conv}

        with patch(
            "nexus.extensions.ExtensionLoader.load_all",
            new_callable=AsyncMock,
            return_value=[],
        ):
            result = await _load_extensions(config, runtime, agents, conv)
        assert result is not None

    async def test_with_extensions_and_schemas(self, tmp_path: Path) -> None:
        config = _cfg(tmp_path)
        runtime = AsyncMock()
        conv = ConversationManager(name="test")
        conv._llm = MagicMock()
        conv._mcp = None
        conv._skill_manager = MagicMock()
        memory = MemoryAgent(name="memory", db_path=str(tmp_path / "ext.db"))
        agents = {"memory": memory, "conversation_manager": conv}

        mock_ext = MagicMock()
        mock_ext.name = "test-ext"
        mock_ext.version = "0.1"

        mock_nexus_ctx = MagicMock()
        mock_nexus_ctx.commands = {"testcmd": AsyncMock()}
        mock_nexus_ctx.signal_handlers = {}
        mock_nexus_ctx.schemas = ["CREATE TABLE IF NOT EXISTS t (id INT);"]
        mock_nexus_ctx.skill_dirs = [tmp_path / "skills"]

        loader_instance = MagicMock()
        loader_instance.extensions = [mock_ext]
        loader_instance.load_all = AsyncMock(return_value=[mock_ext])

        with (
            patch("nexus.runtime.NexusContext", return_value=mock_nexus_ctx),
            patch("nexus.runtime.ExtensionLoader", return_value=loader_instance),
        ):
            result = await _load_extensions(config, runtime, agents, conv)
        assert result is loader_instance
        assert "testcmd" in conv._ext_commands
        assert len(memory._extension_schemas) == 1


class TestSetupMediaHandlerBranches:
    def test_stt_init_failure(self) -> None:
        conv = ConversationManager(name="test")
        conv._llm = MagicMock()
        with (
            patch("nexus.runtime._HAS_STT", True),
            patch("nexus.runtime.WhisperSTT", side_effect=Exception("no model")),
        ):
            _setup_media_handler(conv)
        assert conv._media_handler is not None

    def test_no_llm_no_vision(self) -> None:
        conv = ConversationManager(name="test")
        conv._llm = None
        with patch("nexus.runtime._HAS_STT", False):
            _setup_media_handler(conv)
        assert conv._media_handler is not None
        assert not conv._media_handler.has_vision


class TestStartDashboardWithMcp:
    async def test_mcp_health_reported(self, tmp_path: Path) -> None:
        config = _cfg(tmp_path, dashboard={"enabled": True, "port": 0, "host": "localhost"})
        runtime = AsyncMock()
        conv = MagicMock()
        mcp = MagicMock()
        mcp.health_check = AsyncMock(return_value={"search": True, "browser": False})
        mcp.filter_tools = MagicMock(return_value=[])

        with patch("nexus.dashboard.gateway.DashboardApp.start", new_callable=AsyncMock):
            result = await _start_dashboard(config, runtime, {}, conv, mcp)
        assert result is not None
        mcp_calls = [
            c for c in runtime.cast.call_args_list if c[0][1].get("action") == "mcp_status"
        ]
        assert len(mcp_calls) == 2


class TestRunNexus:
    async def test_run_and_shutdown(self, tmp_path: Path) -> None:
        config = _cfg(tmp_path)

        with (
            patch("nexus.runtime.build_runtime") as mock_build,
            patch("nexus.runtime.seed_on_start", new_callable=AsyncMock),
            patch("nexus.runtime._start_mcp", new_callable=AsyncMock, return_value=None),
            patch("nexus.runtime._setup_media_handler"),
            patch("nexus.runtime._load_extensions", new_callable=AsyncMock, return_value=None),
            patch("nexus.runtime._start_dashboard", new_callable=AsyncMock, return_value=None),
            patch("nexus.runtime._start_telegram", new_callable=AsyncMock, return_value=None),
        ):
            mock_conv = ConversationManager(name="conversation_manager")
            mock_runtime = AsyncMock()
            mock_runtime.print_tree.return_value = "tree"
            mock_build.return_value = (
                mock_runtime,
                {"conversation_manager": mock_conv},
            )

            async def fire_stop():
                await asyncio.sleep(0.05)
                stop_events = [obj for obj in asyncio.all_tasks() if "run_nexus" in repr(obj)]
                for t in stop_events:
                    t.cancel()

            with patch("asyncio.Event") as mock_event_cls:
                mock_event = MagicMock()
                mock_event.wait = AsyncMock(return_value=None)
                mock_event.set = MagicMock()
                mock_event_cls.return_value = mock_event

                await run_nexus(config)

            mock_runtime.start.assert_called_once()
            mock_runtime.stop.assert_called_once()
