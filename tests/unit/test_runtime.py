from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from nexus.config import NexusConfig
from nexus.runtime import (
    _register_agents_with_dashboard,
    _setup_media_handler,
    _start_dashboard,
    _start_mcp,
    _start_telegram,
    build_runtime,
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
        from nexus.agents.conversation import ConversationManager
        from nexus.agents.memory import MemoryAgent
        from nexus.agents.scheduler import SchedulerAgent

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
        from nexus.agents.conversation import ConversationManager

        conv = ConversationManager(name="test")
        conv._llm = MagicMock()
        with patch("nexus.runtime._HAS_STT", False):
            _setup_media_handler(conv)
        assert conv._media_handler is not None

    def test_with_llm_vision(self) -> None:
        from nexus.agents.conversation import ConversationManager

        conv = ConversationManager(name="test")
        conv._llm = MagicMock()
        with patch("nexus.runtime._HAS_STT", False):
            _setup_media_handler(conv)
        assert conv._media_handler is not None
        assert conv._media_handler.has_vision


class TestStartMcp:
    async def test_no_servers(self, tmp_path: Path) -> None:
        from nexus.agents.conversation import ConversationManager

        conv = ConversationManager(name="test")
        config = _cfg(tmp_path)
        result = await _start_mcp(config, conv)
        assert result is None

    async def test_with_servers(self, tmp_path: Path) -> None:
        from nexus.agents.conversation import ConversationManager

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
        from nexus.agents.conversation import ConversationManager

        conv = ConversationManager(name="test")
        config = _cfg(tmp_path)
        result = await _start_telegram(config, AsyncMock(), conv)
        assert result is None

    async def test_with_telegram(self, tmp_path: Path) -> None:
        from nexus.agents.conversation import ConversationManager

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
