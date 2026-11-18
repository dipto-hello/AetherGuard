"""Upgrading a USD-era database to taka-only policy keeps history and retires USD authority."""
import json

import pytest

from app.policy.storage import load_policy
from app.sandbox.db import init_db


def _legacy_db(path, auto, ceiling):
    conn = init_db(path)
    with conn:
        conn.execute("DELETE FROM schema_migrations WHERE name = 'bdt_only'")
        conn.execute("UPDATE policy_config SET config = ? WHERE id = 1", (json.dumps({
            "version": "1.0.0", "allowed_tools": ["refund_order", "lookup_order"],
            "auto_allow_threshold": auto, "hard_ceiling_threshold": ceiling,
            "enforce_task_scope": True, "require_exact_destination_match": True}),))
        conn.execute("""INSERT INTO orders (id, customer_name, currency, paid_amount, refundable_amount,
                        original_destination, status) VALUES ('ORD-OLD', 'Legacy', 'USD', 25000, 21000, 'card_old', 'partially_refunded')""")
        conn.execute("""INSERT INTO refunds (id, order_id, amount, currency, destination, idempotency_key, status)
                        VALUES ('ref-old', 'ORD-OLD', 4000, 'USD', 'card_old', 'old-key', 'succeeded')""")
        for scope_id, currency in (("usd-scope", "USD"), ("bdt-scope", "BDT")):
            conn.execute("""INSERT INTO task_scopes (scope_id, operator_id, order_id, allowed_action, max_amount,
                            allowed_currency, allowed_destination, expires_at)
                            VALUES (?, 'op', 'ORD-OLD', 'refund_order', 5000, ?, 'card_old', '2999-01-01T00:00:00+00:00')""",
                         (scope_id, currency))
        for action_id, currency in (("act-usd", "USD"), ("act-bdt", "BDT")):
            conn.execute("""INSERT INTO pending_actions (action_id, tool, arguments, fingerprint, status)
                            VALUES (?, 'refund_order', ?, 'fp', 'pending')""",
                         (action_id, json.dumps({"order_id": "ORD-OLD", "amount": 6000, "currency": currency})))
        conn.execute("INSERT INTO pending_actions (action_id, tool, arguments, fingerprint, status) "
                     "VALUES ('act-bad', 'refund_order', 'not json', 'fp', 'pending')")
    conn.close()


def test_upgrade_retires_usd_authority_and_keeps_history(tmp_path):
    path = str(tmp_path / "legacy.db")
    _legacy_db(path, 5000, 100000)
    conn = init_db(path)
    try:
        policy = load_policy(conn)
        assert (policy.auto_allow_threshold, policy.hard_ceiling_threshold) == (500_000, 10_000_000)
        expiry = dict(conn.execute("SELECT scope_id, expires_at FROM task_scopes").fetchall())
        assert expiry["usd-scope"].startswith("1970")
        assert expiry["bdt-scope"].startswith("2999")
        status = dict(conn.execute("SELECT action_id, status FROM pending_actions").fetchall())
        assert status == {"act-usd": "expired", "act-bdt": "pending", "act-bad": "expired"}
        assert tuple(conn.execute("SELECT currency, paid_amount, refundable_amount FROM orders WHERE id = 'ORD-OLD'").fetchone()) == ("USD", 25000, 21000)
        assert tuple(conn.execute("SELECT currency, amount FROM refunds WHERE id = 'ref-old'").fetchone()) == ("USD", 4000)
    finally:
        conn.close()


@pytest.mark.parametrize(("old", "new"), [((5500, 20000), (684_310, 2_488_400)), ((1, 1), (124, 124))])
def test_custom_usd_thresholds_convert_at_dated_reference_rate(tmp_path, old, new):
    path = str(tmp_path / "custom.db")
    _legacy_db(path, *old)
    conn = init_db(path)
    try:
        policy = load_policy(conn)
        assert (policy.auto_allow_threshold, policy.hard_ceiling_threshold) == new
    finally:
        conn.close()


def test_migration_runs_once(tmp_path):
    path = str(tmp_path / "once.db")
    init_db(path).close()
    conn = init_db(path)
    try:
        with conn:
            conn.execute("UPDATE policy_config SET config = json_set(config, '$.auto_allow_threshold', 5000, "
                         "'$.hard_ceiling_threshold', 100000) WHERE id = 1")
        conn.close()
        conn = init_db(path)
        policy = load_policy(conn)
        # A taka policy that happens to equal the old USD defaults must not be rescaled again.
        assert (policy.auto_allow_threshold, policy.hard_ceiling_threshold) == (5000, 100000)
    finally:
        conn.close()
