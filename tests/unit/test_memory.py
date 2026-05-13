from __future__ import annotations

import pytest
from civitas.messages import Message

from nexus.agents.memory import MemoryAgent


@pytest.fixture()
async def memory_agent(tmp_path):
    db_path = str(tmp_path / "test.db")
    agent = MemoryAgent(name="memory", db_path=db_path)
    await agent.on_start()
    try:
        yield agent
    finally:
        await agent.on_stop()


def _make_msg(payload):
    return Message(sender="test", recipient="memory", payload=payload, reply_to="test")


async def _handle(agent, msg):
    agent._current_message = msg
    try:
        return await agent.handle(msg)
    finally:
        agent._current_message = None


class TestMemorySchema:
    async def test_schema_creation(self, memory_agent):
        assert memory_agent._db is not None

    async def test_schema_idempotent(self, tmp_path):
        db_path = str(tmp_path / "idem.db")
        agent = MemoryAgent(name="memory", db_path=db_path)
        await agent.on_start()
        await agent.on_start()
        assert agent._db is not None
        await agent.on_stop()


class TestStoreRecall:
    async def test_store_and_recall(self, memory_agent):
        msg = _make_msg(
            {
                "action": "store",
                "tenant_id": "t1",
                "namespace": "facts",
                "key": "diet",
                "value": "vegetarian",
            }
        )
        result = await _handle(memory_agent, msg)
        assert result is not None
        assert result.payload["status"] == "ok"

        msg2 = _make_msg(
            {
                "action": "recall",
                "tenant_id": "t1",
                "namespace": "facts",
                "key": "diet",
            }
        )
        result2 = await _handle(memory_agent, msg2)
        assert result2 is not None
        assert result2.payload["value"] == "vegetarian"

    async def test_recall_missing(self, memory_agent):
        msg = _make_msg(
            {
                "action": "recall",
                "tenant_id": "t1",
                "namespace": "facts",
                "key": "nonexistent",
            }
        )
        result = await _handle(memory_agent, msg)
        assert result is not None
        assert result.payload["value"] is None

    async def test_upsert(self, memory_agent):
        for value in ["v1", "v2"]:
            msg = _make_msg(
                {
                    "action": "store",
                    "tenant_id": "t1",
                    "namespace": "facts",
                    "key": "k",
                    "value": value,
                }
            )
            await _handle(memory_agent, msg)

        msg = _make_msg(
            {
                "action": "recall",
                "tenant_id": "t1",
                "namespace": "facts",
                "key": "k",
            }
        )
        result = await _handle(memory_agent, msg)
        assert result is not None
        assert result.payload["value"] == "v2"


class TestSearch:
    async def test_fts_search(self, memory_agent):
        await _handle(
            memory_agent,
            _make_msg(
                {
                    "action": "store",
                    "tenant_id": "t1",
                    "namespace": "facts",
                    "key": "diet",
                    "value": "vegetarian since 2020",
                }
            ),
        )
        await _handle(
            memory_agent,
            _make_msg(
                {
                    "action": "store",
                    "tenant_id": "t1",
                    "namespace": "facts",
                    "key": "location",
                    "value": "Bangalore India",
                }
            ),
        )

        result = await _handle(
            memory_agent,
            _make_msg(
                {
                    "action": "search",
                    "tenant_id": "t1",
                    "query": "vegetarian",
                }
            ),
        )
        assert result is not None
        assert len(result.payload["results"]) >= 1
        assert any(r["key"] == "diet" for r in result.payload["results"])


class TestDelete:
    async def test_delete(self, memory_agent):
        await _handle(
            memory_agent,
            _make_msg(
                {
                    "action": "store",
                    "tenant_id": "t1",
                    "namespace": "facts",
                    "key": "temp",
                    "value": "data",
                }
            ),
        )
        await _handle(
            memory_agent,
            _make_msg(
                {
                    "action": "delete",
                    "tenant_id": "t1",
                    "namespace": "facts",
                    "key": "temp",
                }
            ),
        )

        result = await _handle(
            memory_agent,
            _make_msg(
                {
                    "action": "recall",
                    "tenant_id": "t1",
                    "namespace": "facts",
                    "key": "temp",
                }
            ),
        )
        assert result is not None
        assert result.payload["value"] is None


class TestConfig:
    async def test_config_get_set(self, memory_agent):
        await _handle(
            memory_agent,
            _make_msg(
                {
                    "action": "config_set",
                    "tenant_id": "t1",
                    "namespace": "prefs",
                    "key": "theme",
                    "value": "dark",
                }
            ),
        )
        result = await _handle(
            memory_agent,
            _make_msg(
                {
                    "action": "config_get",
                    "tenant_id": "t1",
                    "namespace": "prefs",
                    "key": "theme",
                }
            ),
        )
        assert result is not None
        assert result.payload["value"] == "dark"

    async def test_config_get_all(self, memory_agent):
        for k, v in [("a", "1"), ("b", "2")]:
            await _handle(
                memory_agent,
                _make_msg(
                    {
                        "action": "config_set",
                        "tenant_id": "t1",
                        "namespace": "ns",
                        "key": k,
                        "value": v,
                    }
                ),
            )
        result = await _handle(
            memory_agent,
            _make_msg(
                {
                    "action": "config_get_all",
                    "tenant_id": "t1",
                }
            ),
        )
        assert result is not None
        assert result.payload["configs"]["ns"]["a"] == "1"
        assert result.payload["configs"]["ns"]["b"] == "2"


class TestSessions:
    async def test_session_lifecycle(self, memory_agent):
        create = await _handle(
            memory_agent,
            _make_msg(
                {
                    "action": "create_session",
                    "tenant_id": "t1",
                }
            ),
        )
        assert create is not None
        sid = create.payload["session_id"]

        active = await _handle(
            memory_agent,
            _make_msg(
                {
                    "action": "get_active_session",
                    "tenant_id": "t1",
                }
            ),
        )
        assert active is not None
        assert active.payload["session_id"] == sid

        checkpoint_data = {
            "session_id": sid,
            "tenant_id": "t1",
            "messages": [{"role": "user", "content": "hi"}],
        }
        await _handle(
            memory_agent,
            _make_msg(
                {
                    "action": "checkpoint_session",
                    "session_id": sid,
                    "checkpoint": checkpoint_data,
                }
            ),
        )

        restored = await _handle(
            memory_agent,
            _make_msg(
                {
                    "action": "get_active_session",
                    "tenant_id": "t1",
                }
            ),
        )
        assert restored is not None
        assert restored.payload["checkpoint"]["messages"][0]["content"] == "hi"

        await _handle(
            memory_agent,
            _make_msg(
                {
                    "action": "expire_session",
                    "session_id": sid,
                }
            ),
        )
        after_expire = await _handle(
            memory_agent,
            _make_msg(
                {
                    "action": "get_active_session",
                    "tenant_id": "t1",
                }
            ),
        )
        assert after_expire is not None
        assert after_expire.payload["session_id"] is None


class TestSaveMessage:
    async def test_save_message(self, memory_agent):
        create = await _handle(
            memory_agent,
            _make_msg(
                {
                    "action": "create_session",
                    "tenant_id": "t1",
                }
            ),
        )
        assert create is not None
        sid = create.payload["session_id"]

        result = await _handle(
            memory_agent,
            _make_msg(
                {
                    "action": "save_message",
                    "session_id": sid,
                    "role": "user",
                    "content": "hello world",
                }
            ),
        )
        assert result is not None
        assert result.payload["status"] == "ok"


class TestTenantSeeding:
    async def test_seed_and_resolve(self, memory_agent):
        await _handle(
            memory_agent,
            _make_msg(
                {
                    "action": "seed_tenants",
                    "users": [
                        {
                            "name": "Alice",
                            "tenant_id": "alice",
                            "role": "admin",
                            "persona": "dross",
                            "timezone": "UTC",
                            "telegram_user_id": 12345,
                        },
                    ],
                }
            ),
        )

        result = await _handle(
            memory_agent,
            _make_msg(
                {
                    "action": "resolve_tenant",
                    "transport": "telegram",
                    "transport_user_id": "12345",
                }
            ),
        )
        assert result is not None
        assert result.payload["tenant_id"] == "alice"
        assert result.payload["name"] == "Alice"

    async def test_seed_idempotent(self, memory_agent):
        users = [{"name": "Bob", "tenant_id": "bob", "role": "user"}]
        await _handle(memory_agent, _make_msg({"action": "seed_tenants", "users": users}))
        await _handle(memory_agent, _make_msg({"action": "seed_tenants", "users": users}))


class TestTenantIsolation:
    async def test_cross_tenant_invisible(self, memory_agent):
        await _handle(
            memory_agent,
            _make_msg(
                {
                    "action": "store",
                    "tenant_id": "t1",
                    "namespace": "facts",
                    "key": "secret",
                    "value": "t1-data",
                }
            ),
        )
        result = await _handle(
            memory_agent,
            _make_msg(
                {
                    "action": "recall",
                    "tenant_id": "t2",
                    "namespace": "facts",
                    "key": "secret",
                }
            ),
        )
        assert result is not None
        assert result.payload["value"] is None


class TestValidation:
    async def test_missing_action(self, memory_agent):
        result = await _handle(memory_agent, _make_msg({}))
        assert result is not None
        assert "error" in result.payload

    async def test_unknown_action(self, memory_agent):
        result = await _handle(memory_agent, _make_msg({"action": "bogus"}))
        assert result is not None
        assert "error" in result.payload

    async def test_missing_fields(self, memory_agent):
        result = await _handle(memory_agent, _make_msg({"action": "store", "tenant_id": "t1"}))
        assert result is not None
        assert "error" in result.payload


class TestExtQuery:
    async def test_select(self, memory_agent):
        memory_agent.register_extension_schemas(
            ["CREATE TABLE IF NOT EXISTS test_ext (id INTEGER PRIMARY KEY, val TEXT);"]
        )
        await memory_agent.on_start()
        await _handle(
            memory_agent,
            _make_msg(
                {
                    "action": "ext_execute",
                    "sql": "INSERT INTO test_ext (val) VALUES (?)",
                    "params": ["hello"],
                }
            ),
        )
        result = await _handle(
            memory_agent,
            _make_msg({"action": "ext_query", "sql": "SELECT val FROM test_ext", "params": []}),
        )
        assert result is not None
        assert result.payload["rows"] == [["hello"]]
        assert result.payload["columns"] == ["val"]

    async def test_query_rejects_non_select(self, memory_agent):
        result = await _handle(
            memory_agent,
            _make_msg({"action": "ext_query", "sql": "DELETE FROM tenants"}),
        )
        assert result is not None
        assert "error" in result.payload

    async def test_execute_rejects_select(self, memory_agent):
        result = await _handle(
            memory_agent,
            _make_msg({"action": "ext_execute", "sql": "SELECT 1"}),
        )
        assert result is not None
        assert "error" in result.payload

    async def test_execute_rejects_drop(self, memory_agent):
        result = await _handle(
            memory_agent,
            _make_msg({"action": "ext_execute", "sql": "DROP TABLE tenants"}),
        )
        assert result is not None
        assert "DROP" in result.payload["error"]

    async def test_missing_sql(self, memory_agent):
        result = await _handle(
            memory_agent,
            _make_msg({"action": "ext_query"}),
        )
        assert result is not None
        assert "error" in result.payload
