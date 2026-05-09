from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any

import aiosqlite
from civitas.messages import Message
from civitas.process import AgentProcess

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tenants (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    role       TEXT NOT NULL DEFAULT 'user',
    timezone   TEXT NOT NULL DEFAULT 'UTC',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_config (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id  TEXT NOT NULL REFERENCES tenants(id),
    namespace  TEXT NOT NULL,
    key        TEXT NOT NULL,
    value      TEXT NOT NULL,
    UNIQUE(tenant_id, namespace, key)
);

CREATE TABLE IF NOT EXISTS sessions (
    id         TEXT PRIMARY KEY,
    tenant_id  TEXT NOT NULL REFERENCES tenants(id),
    status     TEXT NOT NULL DEFAULT 'active',
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at   TIMESTAMP,
    summary    TEXT,
    checkpoint TEXT
);

CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    role       TEXT NOT NULL,
    content    TEXT NOT NULL,
    tool_calls TEXT,
    token_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS memories (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id  TEXT NOT NULL REFERENCES tenants(id),
    namespace  TEXT NOT NULL,
    key        TEXT NOT NULL,
    value      TEXT NOT NULL,
    source     TEXT,
    confidence REAL DEFAULT 1.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, namespace, key)
);

CREATE TABLE IF NOT EXISTS conversations (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id  TEXT NOT NULL REFERENCES tenants(id),
    session_id TEXT REFERENCES sessions(id),
    summary    TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS schedule_runs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    task_name  TEXT NOT NULL,
    tenant_id  TEXT,
    ran_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status     TEXT NOT NULL,
    details    TEXT
);
"""

_FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    key, value,
    content='memories',
    content_rowid='id'
);
"""

_FTS_TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts(rowid, key, value) VALUES (new.id, new.key, new.value);
END;

CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, key, value)
        VALUES('delete', old.id, old.key, old.value);
END;

CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, key, value)
        VALUES('delete', old.id, old.key, old.value);
    INSERT INTO memories_fts(rowid, key, value) VALUES (new.id, new.key, new.value);
END;
"""


class MemoryAgent(AgentProcess):
    def __init__(self, name: str, db_path: str = "data/nexus.db", **kwargs: Any) -> None:
        super().__init__(name, **kwargs)
        self._db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def on_start(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self._db_path)
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.executescript(_SCHEMA)
        await self._db.executescript(_FTS_SCHEMA)
        await self._db.executescript(_FTS_TRIGGERS)
        await self._db.commit()

    async def on_stop(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None

    async def handle(self, message: Message) -> Message | None:
        action = message.payload.get("action")
        if not action:
            return self.reply({"error": "Missing required field: action"})

        handler = getattr(self, f"_action_{action}", None)
        if handler is None:
            return self.reply({"error": f"Unknown action: {action}"})

        result = await handler(message.payload)
        return self.reply(result)

    async def _action_store(self, payload: dict[str, Any]) -> dict[str, Any]:
        tenant_id = payload.get("tenant_id")
        namespace = payload.get("namespace")
        key = payload.get("key")
        value = payload.get("value")
        if not all([tenant_id, namespace, key, value]):
            return {"error": "store requires: tenant_id, namespace, key, value"}

        source = payload.get("source", "user_stated")
        confidence = payload.get("confidence", 1.0)

        if not self._db:
            return {"error": "database not initialized"}
        await self._db.execute(
            """INSERT INTO memories (tenant_id, namespace, key, value, source, confidence)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(tenant_id, namespace, key)
               DO UPDATE SET value=excluded.value, source=excluded.source,
                             confidence=excluded.confidence, updated_at=CURRENT_TIMESTAMP""",
            (tenant_id, namespace, key, value, source, confidence),
        )
        await self._db.commit()
        return {"status": "ok"}

    async def _action_recall(self, payload: dict[str, Any]) -> dict[str, Any]:
        tenant_id = payload.get("tenant_id")
        namespace = payload.get("namespace")
        key = payload.get("key")
        if not all([tenant_id, namespace, key]):
            return {"error": "recall requires: tenant_id, namespace, key"}

        if not self._db:
            return {"error": "database not initialized"}
        sql = (
            "SELECT value, source, confidence FROM memories"
            " WHERE tenant_id=? AND namespace=? AND key=?"
        )
        async with self._db.execute(sql, (tenant_id, namespace, key)) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return {"value": None}
        return {"value": row[0], "source": row[1], "confidence": row[2]}

    @staticmethod
    def _sanitize_fts_query(query: str) -> str:
        import re

        sanitized = re.sub(r"[^\w\s]", " ", query)
        words = sanitized.split()
        if not words:
            return '""'
        return " ".join(words)

    async def _action_search(self, payload: dict[str, Any]) -> dict[str, Any]:
        tenant_id = payload.get("tenant_id")
        query = payload.get("query")
        if not tenant_id or not query:
            return {"error": "search requires: tenant_id, query"}

        limit = payload.get("limit", 10)
        fts_query = self._sanitize_fts_query(query)

        if not self._db:
            return {"error": "database not initialized"}
        try:
            async with self._db.execute(
                """SELECT m.namespace, m.key, m.value, m.source, m.confidence
                   FROM memories m
                   JOIN memories_fts f ON m.id = f.rowid
                   WHERE m.tenant_id = ? AND memories_fts MATCH ?
                   LIMIT ?""",
                (tenant_id, fts_query, limit),
            ) as cursor:
                rows = await cursor.fetchall()
        except Exception:
            return {"results": []}

        results = [
            {"namespace": r[0], "key": r[1], "value": r[2], "source": r[3], "confidence": r[4]}
            for r in rows
        ]
        return {"results": results}

    async def _action_delete(self, payload: dict[str, Any]) -> dict[str, Any]:
        tenant_id = payload.get("tenant_id")
        namespace = payload.get("namespace")
        key = payload.get("key")
        if not all([tenant_id, namespace, key]):
            return {"error": "delete requires: tenant_id, namespace, key"}

        if not self._db:
            return {"error": "database not initialized"}
        await self._db.execute(
            "DELETE FROM memories WHERE tenant_id=? AND namespace=? AND key=?",
            (tenant_id, namespace, key),
        )
        await self._db.commit()
        return {"status": "ok"}

    async def _action_save_message(self, payload: dict[str, Any]) -> dict[str, Any]:
        session_id = payload.get("session_id")
        role = payload.get("role")
        content = payload.get("content")
        if not all([session_id, role, content]):
            return {"error": "save_message requires: session_id, role, content"}

        tool_calls = payload.get("tool_calls")
        tool_calls_json = json.dumps(tool_calls) if tool_calls else None
        token_count = payload.get("token_count")

        if not self._db:
            return {"error": "database not initialized"}
        sql = (
            "INSERT INTO messages (session_id, role, content, tool_calls, token_count)"
            " VALUES (?, ?, ?, ?, ?)"
        )
        await self._db.execute(sql, (session_id, role, content, tool_calls_json, token_count))
        await self._db.commit()
        return {"status": "ok"}

    async def _action_config_get(self, payload: dict[str, Any]) -> dict[str, Any]:
        tenant_id = payload.get("tenant_id")
        namespace = payload.get("namespace")
        key = payload.get("key")
        if not all([tenant_id, namespace, key]):
            return {"error": "config_get requires: tenant_id, namespace, key"}

        if not self._db:
            return {"error": "database not initialized"}
        async with self._db.execute(
            "SELECT value FROM user_config WHERE tenant_id=? AND namespace=? AND key=?",
            (tenant_id, namespace, key),
        ) as cursor:
            row = await cursor.fetchone()

        return {"value": row[0] if row else None}

    async def _action_config_set(self, payload: dict[str, Any]) -> dict[str, Any]:
        tenant_id = payload.get("tenant_id")
        namespace = payload.get("namespace")
        key = payload.get("key")
        value = payload.get("value")
        if not all([tenant_id, namespace, key, value]):
            return {"error": "config_set requires: tenant_id, namespace, key, value"}

        if not self._db:
            return {"error": "database not initialized"}
        await self._db.execute(
            """INSERT INTO user_config (tenant_id, namespace, key, value)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(tenant_id, namespace, key) DO UPDATE SET value=excluded.value""",
            (tenant_id, namespace, key, value),
        )
        await self._db.commit()
        return {"status": "ok"}

    async def _action_config_get_all(self, payload: dict[str, Any]) -> dict[str, Any]:
        tenant_id = payload.get("tenant_id")
        if not tenant_id:
            return {"error": "config_get_all requires: tenant_id"}

        if not self._db:
            return {"error": "database not initialized"}
        async with self._db.execute(
            "SELECT namespace, key, value FROM user_config WHERE tenant_id=?",
            (tenant_id,),
        ) as cursor:
            rows = await cursor.fetchall()

        configs: dict[str, dict[str, str]] = {}
        for ns, k, v in rows:
            configs.setdefault(ns, {})[k] = v
        return {"configs": configs}

    async def _action_create_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        tenant_id = payload.get("tenant_id")
        if not tenant_id:
            return {"error": "create_session requires: tenant_id"}

        session_id = payload.get("session_id") or str(uuid.uuid4())

        if not self._db:
            return {"error": "database not initialized"}
        await self._db.execute(
            "INSERT INTO sessions (id, tenant_id, status) VALUES (?, ?, 'active')",
            (session_id, tenant_id),
        )
        await self._db.commit()
        return {"session_id": session_id, "status": "ok"}

    async def _action_get_active_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        tenant_id = payload.get("tenant_id")
        if not tenant_id:
            return {"error": "get_active_session requires: tenant_id"}

        if not self._db:
            return {"error": "database not initialized"}
        sql = (
            "SELECT id, checkpoint FROM sessions"
            " WHERE tenant_id=? AND status='active'"
            " ORDER BY started_at DESC LIMIT 1"
        )
        async with self._db.execute(sql, (tenant_id,)) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return {"session_id": None}

        checkpoint = json.loads(row[1]) if row[1] else None
        return {"session_id": row[0], "checkpoint": checkpoint}

    async def _action_checkpoint_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        session_id = payload.get("session_id")
        checkpoint = payload.get("checkpoint")
        if not session_id or checkpoint is None:
            return {"error": "checkpoint_session requires: session_id, checkpoint"}

        if not self._db:
            return {"error": "database not initialized"}
        await self._db.execute(
            "UPDATE sessions SET checkpoint=? WHERE id=?",
            (json.dumps(checkpoint), session_id),
        )
        await self._db.commit()
        return {"status": "ok"}

    async def _action_expire_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        session_id = payload.get("session_id")
        if not session_id:
            return {"error": "expire_session requires: session_id"}

        if not self._db:
            return {"error": "database not initialized"}
        await self._db.execute(
            "UPDATE sessions SET status='expired', ended_at=CURRENT_TIMESTAMP WHERE id=?",
            (session_id,),
        )
        await self._db.commit()
        return {"status": "ok"}

    async def _action_complete_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        session_id = payload.get("session_id")
        summary = payload.get("summary")
        if not session_id or not summary:
            return {"error": "complete_session requires: session_id, summary"}

        if not self._db:
            return {"error": "database not initialized"}
        sql = (
            "UPDATE sessions SET status='completed', summary=?,"
            " ended_at=CURRENT_TIMESTAMP WHERE id=?"
        )
        await self._db.execute(sql, (summary, session_id))
        await self._db.commit()
        return {"status": "ok"}

    async def _action_seed_tenants(self, payload: dict[str, Any]) -> dict[str, Any]:
        users = payload.get("users")
        if not users:
            return {"error": "seed_tenants requires: users"}

        if not self._db:
            return {"error": "database not initialized"}

        for user in users:
            await self._db.execute(
                """INSERT INTO tenants (id, name, role, timezone)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET name=excluded.name, role=excluded.role,
                                                  timezone=excluded.timezone""",
                (
                    user["tenant_id"],
                    user["name"],
                    user.get("role", "admin"),
                    user.get("timezone", "UTC"),
                ),
            )

            if user.get("persona"):
                await self._db.execute(
                    """INSERT INTO user_config (tenant_id, namespace, key, value)
                       VALUES (?, 'persona', 'persona_name', ?)
                       ON CONFLICT(tenant_id, namespace, key) DO UPDATE SET value=excluded.value""",
                    (user["tenant_id"], user["persona"]),
                )

            if user.get("telegram_user_id"):
                await self._db.execute(
                    """INSERT INTO user_config (tenant_id, namespace, key, value)
                       VALUES (?, 'transport_ids', 'telegram', ?)
                       ON CONFLICT(tenant_id, namespace, key) DO UPDATE SET value=excluded.value""",
                    (user["tenant_id"], str(user["telegram_user_id"])),
                )

        await self._db.commit()
        return {"status": "ok", "count": len(users)}

    async def _action_resolve_tenant(self, payload: dict[str, Any]) -> dict[str, Any]:
        transport = payload.get("transport")
        transport_user_id = payload.get("transport_user_id")
        if not transport or not transport_user_id:
            return {"error": "resolve_tenant requires: transport, transport_user_id"}

        if not self._db:
            return {"error": "database not initialized"}
        async with self._db.execute(
            """SELECT uc.tenant_id, t.name, t.role, t.timezone
               FROM user_config uc
               JOIN tenants t ON uc.tenant_id = t.id
               WHERE uc.namespace='transport_ids' AND uc.key=? AND uc.value=?""",
            (transport, str(transport_user_id)),
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return {"tenant_id": None}
        return {"tenant_id": row[0], "name": row[1], "role": row[2], "timezone": row[3]}

    async def _action_get_tenant_persona(self, payload: dict[str, Any]) -> dict[str, Any]:
        tenant_id = payload.get("tenant_id")
        if not tenant_id:
            return {"error": "get_tenant_persona requires: tenant_id"}

        if not self._db:
            return {"error": "database not initialized"}
        sql = (
            "SELECT value FROM user_config"
            " WHERE tenant_id=? AND namespace='persona' AND key='persona_name'"
        )
        async with self._db.execute(sql, (tenant_id,)) as cursor:
            row = await cursor.fetchone()

        return {"persona_name": row[0] if row else "default"}
