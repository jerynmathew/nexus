from __future__ import annotations

from pathlib import Path

from nexus.config import NexusConfig
from nexus.runtime import build_runtime


class TestBuildRuntime:
    def test_builds_without_error(self, tmp_path: Path) -> None:
        config = NexusConfig(
            memory={"db_path": str(tmp_path / "test.db")},
            persona_dir=str(tmp_path / "personas"),
            users_dir=str(tmp_path / "users"),
            data_dir=str(tmp_path),
        )
        runtime, agents = build_runtime(config)
        assert runtime is not None
        assert "memory" in agents
        assert "conversation_manager" in agents
        assert "scheduler" in agents

    def test_agents_have_correct_types(self, tmp_path: Path) -> None:
        from nexus.agents.conversation import ConversationManager
        from nexus.agents.memory import MemoryAgent
        from nexus.agents.scheduler import SchedulerAgent

        config = NexusConfig(
            memory={"db_path": str(tmp_path / "test.db")},
            persona_dir=str(tmp_path / "personas"),
            users_dir=str(tmp_path / "users"),
            data_dir=str(tmp_path),
        )
        _, agents = build_runtime(config)
        assert isinstance(agents["memory"], MemoryAgent)
        assert isinstance(agents["conversation_manager"], ConversationManager)
        assert isinstance(agents["scheduler"], SchedulerAgent)
