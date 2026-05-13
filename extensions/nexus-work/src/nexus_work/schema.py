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
    meeting_date TEXT
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
"""
