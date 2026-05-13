from __future__ import annotations

FINANCE_SCHEMA = """
CREATE TABLE IF NOT EXISTS finance_holdings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    name TEXT NOT NULL,
    asset_class TEXT NOT NULL,
    quantity REAL NOT NULL,
    avg_price REAL NOT NULL,
    current_price REAL,
    current_value REAL,
    pnl REAL,
    pnl_pct REAL,
    source TEXT NOT NULL,
    metadata TEXT,
    last_synced TIMESTAMP,
    UNIQUE(tenant_id, symbol, source)
);

CREATE TABLE IF NOT EXISTS finance_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    snapshot_date DATE NOT NULL,
    total_value REAL NOT NULL,
    equity_value REAL,
    mf_value REAL,
    etf_value REAL,
    gold_value REAL,
    debt_value REAL,
    day_change REAL,
    day_change_pct REAL,
    asset_allocation TEXT,
    UNIQUE(tenant_id, snapshot_date)
);

CREATE TABLE IF NOT EXISTS finance_gold_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE NOT NULL,
    city TEXT NOT NULL,
    gold_22k REAL,
    gold_24k REAL,
    currency TEXT DEFAULT 'INR',
    UNIQUE(date, city)
);

CREATE TABLE IF NOT EXISTS finance_mf_nav (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scheme_code TEXT NOT NULL,
    date DATE NOT NULL,
    nav REAL NOT NULL,
    UNIQUE(scheme_code, date)
);

CREATE TABLE IF NOT EXISTS finance_bank_statements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    bank TEXT NOT NULL,
    upload_date TIMESTAMP NOT NULL,
    statement_period_start DATE,
    statement_period_end DATE,
    parsed_data TEXT,
    raw_filename TEXT
);

CREATE TABLE IF NOT EXISTS finance_reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    reminder_type TEXT NOT NULL,
    last_completed TIMESTAMP,
    frequency_days INTEGER DEFAULT 30,
    UNIQUE(tenant_id, reminder_type)
);

CREATE TABLE IF NOT EXISTS finance_fire_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT NOT NULL,
    target_corpus REAL,
    monthly_expenses REAL,
    withdrawal_rate REAL DEFAULT 0.04,
    inflation_rate REAL DEFAULT 0.06,
    expected_return REAL DEFAULT 0.12,
    target_allocation TEXT,
    UNIQUE(tenant_id)
);
"""
