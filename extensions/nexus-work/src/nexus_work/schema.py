from __future__ import annotations

WORK_SCHEMA = """
CREATE TABLE IF NOT EXISTS work_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    priority TEXT DEFAULT 'medium',
    due_date TEXT,
    source TEXT NOT NULL,
    source_ref TEXT,
    assigned_to TEXT,
    assigned_by TEXT,
    blocking TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    reminder_sent BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS work_delegations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    delegated_to TEXT NOT NULL,
    task TEXT NOT NULL,
    status TEXT DEFAULT 'assigned',
    due_date TEXT,
    last_update TIMESTAMP,
    source TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS work_meetings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    event_id TEXT,
    title TEXT NOT NULL,
    attendees TEXT,
    prep_sent BOOLEAN DEFAULT FALSE,
    notes TEXT,
    action_items TEXT,
    meeting_date TEXT,
    UNIQUE(tenant_id, event_id)
);

CREATE TABLE IF NOT EXISTS work_people (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    canonical_name TEXT NOT NULL,
    emails TEXT,
    slack_id TEXT,
    discord_id TEXT,
    github_username TEXT,
    relationship TEXT,
    last_seen TIMESTAMP,
    UNIQUE(tenant_id, canonical_name)
);

CREATE TABLE IF NOT EXISTS work_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    signal_id TEXT UNIQUE NOT NULL,
    source TEXT NOT NULL,
    event_type TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    title TEXT NOT NULL,
    body TEXT,
    url TEXT,
    author TEXT,
    author_email TEXT,
    channel TEXT,
    project TEXT,
    priority TEXT DEFAULT 'medium',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE VIRTUAL TABLE IF NOT EXISTS work_signals_fts USING fts5(
    title, body, author,
    content='work_signals',
    content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS work_signals_ai AFTER INSERT ON work_signals BEGIN
    INSERT INTO work_signals_fts(rowid, title, body, author)
        VALUES (new.id, new.title, new.body, new.author);
END;

CREATE TRIGGER IF NOT EXISTS work_signals_ad AFTER DELETE ON work_signals BEGIN
    INSERT INTO work_signals_fts(work_signals_fts, rowid, title, body, author)
        VALUES('delete', old.id, old.title, old.body, old.author);
END;
"""
