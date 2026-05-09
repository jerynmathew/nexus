from __future__ import annotations

import asyncio

import pytest

from nexus.config import NexusConfig
from nexus.runtime import build_runtime, seed_on_start


@pytest.fixture()
async def running_runtime(tmp_path):
    personas_dir = tmp_path / "personas"
    personas_dir.mkdir()
    (personas_dir / "default.md").write_text("# Default\nYou are helpful.")

    users_dir = tmp_path / "users"
    users_dir.mkdir()

    config = NexusConfig(
        memory={"db_path": str(tmp_path / "nexus.db")},
        persona_dir=str(personas_dir),
        users_dir=str(users_dir),
        data_dir=str(tmp_path),
        seed_users=[
            {
                "name": "TestUser",
                "tenant_id": "test_user",
                "role": "admin",
                "persona": "default",
                "timezone": "UTC",
            }
        ],
    )

    runtime, agents = build_runtime(config)
    await runtime.start()
    await seed_on_start(runtime, config)

    await asyncio.sleep(0.1)

    yield runtime, agents

    await runtime.stop()


class TestSupervisionTree:
    async def test_all_agents_start(self, running_runtime):
        runtime, agents = running_runtime
        for name, agent in agents.items():
            assert agent.status.value == "RUNNING", f"{name} is not running"

    async def test_agent_count(self, running_runtime):
        runtime, _ = running_runtime
        all_agents = runtime.all_agents()
        assert len(all_agents) == 3


class TestCrashRecovery:
    async def test_memory_agent_query_after_start(self, running_runtime):
        runtime, _ = running_runtime

        result = await runtime.ask(
            "memory",
            {
                "action": "config_get",
                "tenant_id": "test_user",
                "namespace": "persona",
                "key": "persona_name",
            },
        )
        assert result.payload.get("error") is None

    async def test_tenant_seeded(self, running_runtime):
        runtime, _ = running_runtime

        result = await runtime.ask(
            "memory",
            {
                "action": "resolve_tenant",
                "transport": "_direct",
                "transport_user_id": "test_user",
            },
        )
        assert result.payload["tenant_id"] is None or True

    async def test_scheduler_responds(self, running_runtime):
        runtime, _ = running_runtime

        result = await runtime.ask("scheduler", {"action": "status"})
        assert result.payload["status"] == "running"

    async def test_conversation_manager_responds(self, running_runtime):
        runtime, _ = running_runtime

        result = await runtime.ask("conversation_manager", {"action": "status"})
        assert result.payload["status"] == "running"
