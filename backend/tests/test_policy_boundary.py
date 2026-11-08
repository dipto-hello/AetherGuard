import pytest
from datetime import datetime, timedelta, timezone
from app.sandbox.db import init_db
from app.sandbox.service import reset_synthetic_data, get_order, save_task_scope
from app.policy.models import TaskScope, PolicyConfig, PolicyVerdict
from app.policy.engine import evaluate_policy
from app.governance.boundary import GovernanceBoundary

@pytest.fixture
def db_conn():
    conn = init_db(":memory:")
    reset_synthetic_data(conn)
    yield conn
    conn.close()

@pytest.fixture
def boundary(db_conn):
    return GovernanceBoundary(db_conn)

@pytest.fixture
def valid_scope(db_conn):
    scope = TaskScope(
        scope_id="scope-001",
        operator_id="operator_dipto",
        order_id="ORD-101",
        allowed_action="refund_order",
        max_amount=30000,  # $300.00
        allowed_currency="USD",
        allowed_destination="card_visa_4242",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1)
    )
    save_task_scope(db_conn, **scope.model_dump(mode='json'))
    return scope

def test_allowed_refund_within_scope_and_policy(boundary, db_conn, valid_scope):
    """
    Low value ($40 = 4000 cents) within task scope and below auto-allow threshold ($50).
    Verdict: ALLOW. Backend state must change.
    """
    action_payload = {
        "tool": "refund_order",
        "arguments": {
            "order_id": "ORD-101",
            "amount": 4000,
            "currency": "USD",
            "destination": "card_visa_4242",
            "reason": "Customer received damaged product"
        },
        "idempotency_key": "idemp-allow-01"
    }

    result = boundary.intercept_and_evaluate(action_payload, task_scope=valid_scope)
    assert result["verdict"] == PolicyVerdict.ALLOWED.value
    assert result["executed"] is True
    assert result["refund"] is not None
    assert result["refund"]["amount"] == 4000

    # Physical verification: backend state must be deducted
    order = get_order(db_conn, "ORD-101")
    assert order["refundable_amount"] == 21000  # $250 - $40 = $210

def test_approval_required_for_moderate_amount(boundary, db_conn, valid_scope):
    """
    Moderate value ($250 = 25000 cents) within task scope, but exceeds auto-allow threshold ($50).
    Verdict: APPROVAL_REQUIRED. Backend state must NOT change.
    """
    action_payload = {
        "tool": "refund_order",
        "arguments": {
            "order_id": "ORD-101",
            "amount": 25000,
            "currency": "USD",
            "destination": "card_visa_4242",
            "reason": "Customer cancellation within 30 days"
        },
        "idempotency_key": "idemp-approval-01"
    }

    result = boundary.intercept_and_evaluate(action_payload, task_scope=valid_scope)
    assert result["verdict"] == PolicyVerdict.APPROVAL_REQUIRED.value
    assert result["executed"] is False
    assert result["action_id"] is not None
    assert result["pending_approval"] is True

    # Physical verification: backend state must remain completely UNTOUCHED
    order = get_order(db_conn, "ORD-101")
    assert order["refundable_amount"] == 25000  # $250.00 intact

def test_hard_block_for_excessive_amount(boundary, db_conn):
    """
    On high-value order (ORD-104, $5,000 balance), an excessive refund of $5,000
    exceeds the system-wide hard policy ceiling ($1,000 = 100000 cents),
    even though the order has enough balance and operator scope was set to $10,000.
    Verdict: BLOCKED (POLICY_HARD_CEILING). Backend state must NOT change.
    """
    loose_scope = TaskScope(
        scope_id="scope-loose-01",
        operator_id="operator_dipto",
        order_id="ORD-104",
        allowed_action="refund_order",
        max_amount=1000000,  # $10,000.00 loose scope
        allowed_currency="USD",
        allowed_destination="wire_swift_chase",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1)
    )
    save_task_scope(db_conn, **loose_scope.model_dump(mode='json'))

    action_payload = {
        "tool": "refund_order",
        "arguments": {
            "order_id": "ORD-104",
            "amount": 500000,  # $5,000.00 > $1,000.00 ceiling
            "currency": "USD",
            "destination": "wire_swift_chase",
            "reason": "Massive refund"
        },
        "idempotency_key": "idemp-block-01"
    }

    result = boundary.intercept_and_evaluate(action_payload, task_scope=loose_scope)
    assert result["verdict"] == PolicyVerdict.BLOCKED.value
    assert result["executed"] is False
    assert "HARD_CEILING" in result["reason"]

    # Physical verification: backend state unchanged
    order = get_order(db_conn, "ORD-104")
    assert order["refundable_amount"] == 500000

def test_hard_block_for_action_outside_task_scope(boundary, db_conn, valid_scope):
    """
    Low amount ($10 = 1000 cents), but on an order (ORD-102) NOT in trusted task scope (ORD-101).
    A small refund outside scope MUST NOT silently execute!
    Verdict: BLOCKED.
    """
    action_payload = {
        "tool": "refund_order",
        "arguments": {
            "order_id": "ORD-102",  # Outside task scope!
            "amount": 1000,
            "currency": "USD",
            "destination": "card_mc_5555",
            "reason": "Unauthorized small refund"
        },
        "idempotency_key": "idemp-scope-violation-01"
    }

    result = boundary.intercept_and_evaluate(action_payload, task_scope=valid_scope)
    assert result["verdict"] == PolicyVerdict.BLOCKED.value
    assert result["executed"] is False
    assert "OUTSIDE_TRUSTED_TASK_SCOPE" in result["reason"]

    # Physical verification: ORD-102 balance unchanged
    order_102 = get_order(db_conn, "ORD-102")
    assert order_102["refundable_amount"] == 4000

def test_hard_block_when_task_scope_expired(boundary, db_conn):
    """
    Task scope whose expires_at is in the past.
    Verdict: BLOCKED.
    """
    expired_scope = TaskScope(
        scope_id="scope-expired",
        operator_id="operator_dipto",
        order_id="ORD-101",
        allowed_action="refund_order",
        max_amount=10000,
        allowed_currency="USD",
        allowed_destination="card_visa_4242",
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=5)
    )
    save_task_scope(db_conn, **expired_scope.model_dump(mode='json'))

    action_payload = {
        "tool": "refund_order",
        "arguments": {
            "order_id": "ORD-101",
            "amount": 2000,
            "currency": "USD",
            "destination": "card_visa_4242",
            "reason": "Test expired"
        },
        "idempotency_key": "idemp-expired-01"
    }

    result = boundary.intercept_and_evaluate(action_payload, task_scope=expired_scope)
    assert result["verdict"] == PolicyVerdict.BLOCKED.value
    assert "TASK_SCOPE_EXPIRED" in result["reason"]

def test_hard_block_destination_tampered(boundary, db_conn, valid_scope):
    """
    Destination altered to attacker wallet.
    Verdict: BLOCKED.
    """
    action_payload = {
        "tool": "refund_order",
        "arguments": {
            "order_id": "ORD-101",
            "amount": 2000,
            "currency": "USD",
            "destination": "attacker_crypto_account",
            "reason": "Payout diverted"
        },
        "idempotency_key": "idemp-tamper-01"
    }

    result = boundary.intercept_and_evaluate(action_payload, task_scope=valid_scope)
    assert result["verdict"] == PolicyVerdict.BLOCKED.value
    assert "DESTINATION_MISMATCH" in result["reason"]

def test_hard_block_for_unknown_tool(boundary, db_conn, valid_scope):
    """
    Unknown or destructive tool call (e.g. drop_database, exec_cmd).
    Verdict: BLOCKED.
    """
    action_payload = {
        "tool": "exec_system_command",
        "arguments": {"cmd": "rm -rf /"},
        "idempotency_key": "idemp-rogue-01"
    }

    result = boundary.intercept_and_evaluate(action_payload, task_scope=valid_scope)
    assert result["verdict"] == PolicyVerdict.BLOCKED.value
    assert "UNKNOWN_TOOL" in result["reason"]

def test_missing_policy_fails_closed(boundary, db_conn, valid_scope):
    """
    When policy configuration is missing or broken, system must FAIL CLOSED (BLOCK).
    """
    boundary.policy_config = None  # Simulate missing policy
    action_payload = {
        "tool": "refund_order",
        "arguments": {
            "order_id": "ORD-101",
            "amount": 1000,
            "currency": "USD",
            "destination": "card_visa_4242"
        },
        "idempotency_key": "idemp-failclosed-01"
    }

    result = boundary.intercept_and_evaluate(action_payload, task_scope=valid_scope)
    assert result["verdict"] == PolicyVerdict.BLOCKED.value
    assert "FAIL_CLOSED" in result["reason"]
