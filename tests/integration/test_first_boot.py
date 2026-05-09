from __future__ import annotations

import asyncio

import pytest

from nexus.config import NexusConfig
from nexus.runtime import build_runtime, seed_on_start


@pytest.fixture()
async def fresh_runtime(tmp_path):
    personas_dir = tmp_path / "personas"
    personas_dir.mkdir()
    (personas_dir / "default.md").write_text("# Default\nYou are helpful.")
    (personas_dir / "dross.md").write_text("# Dross\nYou are witty.")

    users_dir = tmp_path / "users"
    users_dir.mkdir()

    config = NexusConfig(
        memory={"db_path": str(tmp_path / "nexus.db")},
        persona_dir=str(personas_dir),
        users_dir=str(users_dir),
        data_dir=str(tmp_path),
        seed_users=[
            {
                "name": "Alice",
                "tenant_id": "alice",
                "role": "admin",
                "persona": "dross",
                "timezone": "Asia/Kolkata",
                "telegram_user_id": 11111,
            },
            {
                "name": "Bob",
                "tenant_id": "bob",
                "role": "user",
                "persona": "default",
                "timezone": "UTC",
                "telegram_user_id": 22222,
            },
        ],
    )
    return config, tmp_path


class TestFirstBoot:
    async def test_fresh_start_creates_db(self, fresh_runtime):
        config, tmp_path = fresh_runtime
        db_path = tmp_path / "nexus.db"
        assert not db_path.exists()

        runtime, _ = build_runtime(config)
        await runtime.start()
        await seed_on_start(runtime, config)
        await asyncio.sleep(0.1)

        assert db_path.exists()

        result = await runtime.ask(
            "memory",
            {
                "action": "resolve_tenant",
                "transport": "telegram",
                "transport_user_id": "11111",
            },
        )
        assert result.payload["tenant_id"] == "alice"
        assert result.payload["name"] == "Alice"

        result2 = await runtime.ask(
            "memory",
            {
                "action": "resolve_tenant",
                "transport": "telegram",
                "transport_user_id": "22222",
            },
        )
        assert result2.payload["tenant_id"] == "bob"

        await runtime.stop()

    async def test_re_seed_idempotent(self, fresh_runtime):
        config, _ = fresh_runtime

        runtime, _ = build_runtime(config)
        await runtime.start()
        await seed_on_start(runtime, config)
        await seed_on_start(runtime, config)
        await asyncio.sleep(0.1)

        result = await runtime.ask(
            "memory",
            {
                "action": "resolve_tenant",
                "transport": "telegram",
                "transport_user_id": "11111",
            },
        )
        assert result.payload["tenant_id"] == "alice"

        await runtime.stop()

    async def test_persona_selection_per_tenant(self, fresh_runtime):
        config, _ = fresh_runtime

        runtime, _ = build_runtime(config)
        await runtime.start()
        await seed_on_start(runtime, config)
        await asyncio.sleep(0.1)

        alice_persona = await runtime.ask(
            "memory",
            {
                "action": "get_tenant_persona",
                "tenant_id": "alice",
            },
        )
        assert alice_persona.payload["persona_name"] == "dross"

        bob_persona = await runtime.ask(
            "memory",
            {
                "action": "get_tenant_persona",
                "tenant_id": "bob",
            },
        )
        assert bob_persona.payload["persona_name"] == "default"

        await runtime.stop()
