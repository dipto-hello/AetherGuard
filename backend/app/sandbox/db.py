"""Synthetic Sandbox Database Schema & Connection Management"""
import sqlite3
import os
import json
from typing import Optional

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "sandbox.db")

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS orders (
    id TEXT PRIMARY KEY,
    customer_name TEXT NOT NULL,
    currency TEXT NOT NULL,
    paid_amount INTEGER NOT NULL CHECK (paid_amount > 0),
    refundable_amount INTEGER NOT NULL CHECK (refundable_amount >= 0),
    original_destination TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('paid', 'partially_refunded', 'fully_refunded')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS refunds (
    id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(id),
    amount INTEGER NOT NULL CHECK (amount > 0),
    currency TEXT NOT NULL,
    destination TEXT NOT NULL,
    idempotency_key TEXT NOT NULL UNIQUE,
    action_id TEXT,
    status TEXT NOT NULL CHECK (status IN ('succeeded', 'failed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pending_actions (
    action_id TEXT PRIMARY KEY,
    tool TEXT NOT NULL,
    arguments TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    task_scope_id TEXT,
    status TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'rejected', 'expired', 'executing', 'executed')),
    reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_events (
    id TEXT PRIMARY KEY,
    action_id TEXT,
    tool TEXT NOT NULL,
    verdict TEXT NOT NULL,
    reason TEXT NOT NULL,
    fingerprint TEXT,
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS task_scopes (
    scope_id TEXT PRIMARY KEY,
    operator_id TEXT NOT NULL,
    order_id TEXT NOT NULL,
    allowed_action TEXT NOT NULL,
    max_amount INTEGER NOT NULL,
    allowed_currency TEXT NOT NULL,
    allowed_destination TEXT NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS policy_config (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    config TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS action_requests (
    idempotency_key TEXT PRIMARY KEY,
    fingerprint TEXT NOT NULL,
    scope_id TEXT,
    action_id TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS schema_migrations (
    name TEXT PRIMARY KEY
);

CREATE INDEX IF NOT EXISTS idx_refunds_order_id ON refunds(order_id);
CREATE INDEX IF NOT EXISTS idx_refunds_idempotency ON refunds(idempotency_key);
CREATE INDEX IF NOT EXISTS idx_pending_actions_status ON pending_actions(status);
CREATE INDEX IF NOT EXISTS idx_audit_events_created ON audit_events(created_at);
CREATE INDEX IF NOT EXISTS idx_task_scopes_order ON task_scopes(order_id);
"""

DEFAULT_SYNTHETIC_ORDERS = [
    {
        "id": "ORD-101",
        "customer_name": "Rahim Chowdhury",
        "currency": "USD",
        "paid_amount": 25000,  # $250.00
        "refundable_amount": 25000,
        "original_destination": "card_visa_4242",
        "status": "paid"
    },
    {
        "id": "ORD-102",
        "customer_name": "Sarah Jenkins",
        "currency": "USD",
        "paid_amount": 4000,   # $40.00
        "refundable_amount": 4000,
        "original_destination": "card_mc_5555",
        "status": "paid"
    },
    {
        "id": "ORD-103",
        "customer_name": "Tanvir Hasan",
        "currency": "BDT",
        "paid_amount": 500000, # ৳5,000.00 (in poisha)
        "refundable_amount": 500000,
        "original_destination": "bkash_01711000000",
        "status": "paid"
    },
    {
        "id": "ORD-104",
        "customer_name": "Enterprise Client X",
        "currency": "USD",
        "paid_amount": 500000, # $5,000.00
        "refundable_amount": 500000,
        "original_destination": "wire_swift_chase",
        "status": "paid"
    }
]

def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    target = db_path or os.environ.get("AETHERGUARD_DB_PATH") or DEFAULT_DB_PATH
    if target != ":memory:":
        os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
    conn = sqlite3.connect(target, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db(db_path: Optional[str] = None) -> sqlite3.Connection:
    conn = get_connection(db_path)
    with conn:
        conn.execute('BEGIN IMMEDIATE')
        fresh = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='orders'"
        ).fetchone() is None
        fresh_policy = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='policy_config'"
        ).fetchone() is None
        fresh_registry = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='action_requests'"
        ).fetchone() is None
        for statement in SCHEMA_SQL.split(';'):
            if statement.strip():
                conn.execute(statement)
        if not conn.execute("SELECT 1 FROM schema_migrations WHERE name = 'cumulative_scope_budget'").fetchone():
            # Old refunds may lack scope attribution, so old authority cannot safely be reused.
            conn.execute("UPDATE task_scopes SET expires_at = '1970-01-01T00:00:00+00:00'")
            conn.execute("UPDATE pending_actions SET status = 'expired', reason = 'Scope budget upgraded; create a new scope' WHERE status = 'pending'")
            conn.execute("INSERT INTO schema_migrations (name) VALUES ('cumulative_scope_budget')")
        if fresh_registry:
            conn.execute("UPDATE task_scopes SET expires_at = '1970-01-01T00:00:00+00:00'")
            conn.execute("UPDATE pending_actions SET status = 'expired', reason = 'Legacy action lacks a recoverable idempotency key' WHERE status = 'pending'")
        if fresh_policy:
            conn.execute("INSERT OR IGNORE INTO policy_config (id, config) VALUES (1, ?)",
                         (json.dumps({"version": "1.0.0", "allowed_tools": ["refund_order", "lookup_order"],
                                      "auto_allow_threshold": 5000, "hard_ceiling_threshold": 100000,
                                      "enforce_task_scope": True, "require_exact_destination_match": True}),))
        conn.execute("""INSERT OR IGNORE INTO action_requests
            (idempotency_key, fingerprint, scope_id, action_id)
            SELECT idempotency_key, 'legacy', NULL, COALESCE(action_id, id) FROM refunds""")
        if fresh:
            conn.executemany(
                """INSERT INTO orders
                (id, customer_name, currency, paid_amount, refundable_amount, original_destination, status)
                VALUES (:id, :customer_name, :currency, :paid_amount, :refundable_amount, :original_destination, :status)""",
                DEFAULT_SYNTHETIC_ORDERS,
            )
    return conn
