"""Dependency-free checks of real approval and policy code in a separate process."""
import hashlib
import inspect
import json
import sqlite3
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from enum import Enum


class PolicyVerdict(str, Enum):
    ALLOWED = "ALLOWED"
    BLOCKED = "BLOCKED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"


class PolicyConfig:
    def __init__(self):
        self.allowed_tools = ["refund_order"]
        self.enforce_task_scope = True
        self.require_exact_destination_match = True
        self.auto_allow_threshold = 5000
        self.hard_ceiling_threshold = 100000


class TaskScope:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        if isinstance(self.expires_at, str):
            self.expires_at = datetime.fromisoformat(self.expires_at)

    def is_expired(self):
        return datetime.now(timezone.utc) > self.expires_at


models = types.ModuleType("app.policy.models")
models.PolicyVerdict = PolicyVerdict
models.PolicyConfig = PolicyConfig
models.TaskScope = TaskScope
sys.modules["app.policy.models"] = models

from app.approval.service import ApprovalError, decide_approval
from app.sandbox.db import init_db
from app.sandbox.service import save_task_scope


class ApprovalPolicyChecks(unittest.TestCase):
    def setUp(self):
        self.assertIn("policy_config", inspect.signature(decide_approval).parameters)
        self.conn = init_db(":memory:")
        self.args = {"order_id": "ORD-101", "amount": 10000, "currency": "USD", "destination": "card_visa_4242"}
        self.scope_id = "scope-test"
        save_task_scope(self.conn, self.scope_id, "operator", "ORD-101", "refund_order", 20000,
                        "USD", "card_visa_4242", (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat())
        fingerprint = hashlib.sha256(json.dumps({"tool": "refund_order", "arguments": self.args}, sort_keys=True).encode()).hexdigest()
        self.conn.execute("INSERT INTO pending_actions (action_id, tool, arguments, fingerprint, task_scope_id, status) VALUES (?, ?, ?, ?, ?, ?)",
                          ("action-test", "refund_order", json.dumps(self.args), fingerprint, self.scope_id, "pending"))
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def assert_not_executed(self):
        self.assertEqual(self.conn.execute("SELECT refundable_amount FROM orders WHERE id='ORD-101'").fetchone()[0], 25000)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM refunds").fetchone()[0], 0)

    def test_missing_scope_denies_approval(self):
        self.conn.execute("DELETE FROM task_scopes WHERE scope_id = ?", (self.scope_id,))
        self.conn.commit()
        with self.assertRaises(ApprovalError):
            decide_approval(self.conn, "action-test", "approve", "operator", policy_config=PolicyConfig())
        self.assert_not_executed()

    def test_tightened_policy_denies_approval(self):
        policy = PolicyConfig()
        policy.hard_ceiling_threshold = 5000
        with self.assertRaises(ApprovalError):
            decide_approval(self.conn, "action-test", "approve", "operator", policy_config=policy)
        self.assert_not_executed()

    def test_expired_scope_denies_approval(self):
        self.conn.execute("UPDATE task_scopes SET expires_at = ? WHERE scope_id = ?",
                          ((datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(), self.scope_id))
        self.conn.commit()
        with self.assertRaises(ApprovalError):
            decide_approval(self.conn, "action-test", "approve", "operator", policy_config=PolicyConfig())
        self.assert_not_executed()

    def test_changed_scope_and_missing_policy_deny_approval(self):
        self.conn.execute("UPDATE task_scopes SET allowed_destination = 'other' WHERE scope_id = ?", (self.scope_id,))
        self.conn.commit()
        with self.assertRaises(ApprovalError):
            decide_approval(self.conn, "action-test", "approve", "operator", policy_config=PolicyConfig())
        self.assert_not_executed()
        with self.assertRaises(ApprovalError):
            decide_approval(self.conn, "action-test", "approve", "operator", policy_config=None)
        self.assert_not_executed()

    def test_valid_scope_and_policy_allow_approval(self):
        result = decide_approval(self.conn, "action-test", "approve", "operator", policy_config=PolicyConfig())
        self.assertEqual(result["status"], "executed")
        self.assertEqual(self.conn.execute("SELECT refundable_amount FROM orders WHERE id='ORD-101'").fetchone()[0], 15000)

    def test_audit_failure_rolls_back_refund_and_approval(self):
        self.conn.execute("CREATE TRIGGER fail_approval BEFORE INSERT ON audit_events WHEN NEW.verdict = 'APPROVED' BEGIN SELECT RAISE(ABORT, 'test audit failure'); END")
        self.conn.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            decide_approval(self.conn, "action-test", "approve", "operator", policy_config=PolicyConfig())
        self.assert_not_executed()
        self.assertEqual(self.conn.execute("SELECT status FROM pending_actions WHERE action_id='action-test'").fetchone()[0], "pending")


if __name__ == "__main__":
    unittest.main()
