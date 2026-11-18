import pytest
from datetime import datetime, timedelta, timezone
from app.sandbox.db import init_db
from app.sandbox.service import reset_synthetic_data, get_order, save_task_scope
from app.policy.models import TaskScope, PolicyConfig, PolicyVerdict
from app.policy.engine import evaluate_policy
from app.governance.boundary import GovernanceBoundary
from app.approval.service import ApprovalError, decide_approval


@pytest.mark.parametrize(("amount", "expected"), [
    (1250, PolicyVerdict.ALLOWED),
    (1251, PolicyVerdict.APPROVAL_REQUIRED),
    (2500, PolicyVerdict.APPROVAL_REQUIRED),
    (2501, PolicyVerdict.BLOCKED),
])
def test_taka_thresholds_apply_directly_in_poisha(db_conn, amount, expected):
    scope = TaskScope(
        scope_id="bdt-scope", operator_id="operator", order_id="ORD-103",
        max_amount=500000, allowed_currency="BDT", allowed_destination="bkash_01711000000",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    save_task_scope(db_conn, **scope.model_dump(mode="json"))
    policy = PolicyConfig(auto_allow_threshold=1250, hard_ceiling_threshold=2500)
    result = GovernanceBoundary(db_conn, policy).intercept_and_evaluate({
        "tool": "refund_order",
        "arguments": {"order_id": scope.order_id, "amount": amount, "currency": "BDT",
                      "destination": scope.allowed_destination},
    }, scope)
    assert result["verdict"] == expected
    assert get_order(db_conn, scope.order_id)["refundable_amount"] == 500000 - (
        amount if expected == PolicyVerdict.ALLOWED else 0)
    if amount == 2500:
        stricter = PolicyConfig(auto_allow_threshold=1250, hard_ceiling_threshold=2499)
        with pytest.raises(ApprovalError, match="POLICY_HARD_CEILING"):
            decide_approval(db_conn, result["action_id"], "approve", "operator", policy_config=stricter)
        assert get_order(db_conn, scope.order_id)["refundable_amount"] == 500000


@pytest.mark.parametrize("currency", ["USD", "EUR", "bdt", ""])
def test_non_taka_refunds_are_blocked(currency):
    order = {"currency": "BDT", "original_destination": "bkash_01711000000", "refundable_amount": 500000}
    verdict, reason = evaluate_policy("refund_order", {
        "order_id": "ORD-103", "amount": 100, "currency": currency, "destination": "bkash_01711000000",
    }, order, None, PolicyConfig(enforce_task_scope=False))
    assert verdict == PolicyVerdict.BLOCKED
    assert reason.startswith("UNSUPPORTED_CURRENCY") or reason.startswith("VALIDATION_ERROR")

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
        max_amount=3000000,  # ৳30,000
        allowed_currency="BDT",
        allowed_destination="card_visa_4242",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1)
    )
    save_task_scope(db_conn, **scope.model_dump(mode='json'))
    return scope

def test_allowed_refund_within_scope_and_policy(boundary, db_conn, valid_scope):
    """
    Low value (৳4,000 = 400000 poisha) within task scope and below auto-allow threshold (৳5,000).
    Verdict: ALLOW. Backend state must change.
    """
    action_payload = {
        "tool": "refund_order",
        "arguments": {
            "order_id": "ORD-101",
            "amount": 400000,
            "currency": "BDT",
            "destination": "card_visa_4242",
            "reason": "Customer received damaged product"
        },
        "idempotency_key": "idemp-allow-01"
    }

    result = boundary.intercept_and_evaluate(action_payload, task_scope=valid_scope)
    assert result["verdict"] == PolicyVerdict.ALLOWED.value
    assert result["executed"] is True
    assert result["refund"] is not None
    assert result["refund"]["amount"] == 400000

    # Physical verification: backend state must be deducted
    order = get_order(db_conn, "ORD-101")
    assert order["refundable_amount"] == 2100000  # ৳25,000 - ৳4,000 = ৳21,000

def test_approval_required_for_moderate_amount(boundary, db_conn, valid_scope):
    """
    Moderate value (৳25,000 = 2500000 poisha) within task scope, but exceeds auto-allow threshold (৳5,000).
    Verdict: APPROVAL_REQUIRED. Backend state must NOT change.
    """
    action_payload = {
        "tool": "refund_order",
        "arguments": {
            "order_id": "ORD-101",
            "amount": 2500000,
            "currency": "BDT",
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
    assert order["refundable_amount"] == 2500000  # ৳25,000 intact

def test_hard_block_for_excessive_amount(boundary, db_conn):
    """
    On high-value order (ORD-104, ৳500,000 balance), an excessive refund of ৳500,000
    exceeds the system-wide hard policy ceiling (৳100,000 = 10000000 poisha),
    even though the order has enough balance and operator scope was set to ৳1,000,000.
    Verdict: BLOCKED (POLICY_HARD_CEILING). Backend state must NOT change.
    """
    loose_scope = TaskScope(
        scope_id="scope-loose-01",
        operator_id="operator_dipto",
        order_id="ORD-104",
        allowed_action="refund_order",
        max_amount=100000000,  # ৳1,000,000 loose scope
        allowed_currency="BDT",
        allowed_destination="wire_swift_chase",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1)
    )
    save_task_scope(db_conn, **loose_scope.model_dump(mode='json'))

    action_payload = {
        "tool": "refund_order",
        "arguments": {
            "order_id": "ORD-104",
            "amount": 50000000,  # ৳500,000 > ৳100,000 ceiling
            "currency": "BDT",
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
    assert order["refundable_amount"] == 50000000

def test_hard_block_for_action_outside_task_scope(boundary, db_conn, valid_scope):
    """
    Low amount (৳1,000 = 100000 poisha), but on an order (ORD-102) NOT in trusted task scope (ORD-101).
    A small refund outside scope MUST NOT silently execute!
    Verdict: BLOCKED.
    """
    action_payload = {
        "tool": "refund_order",
        "arguments": {
            "order_id": "ORD-102",  # Outside task scope!
            "amount": 100000,
            "currency": "BDT",
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
    assert order_102["refundable_amount"] == 400000

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
        max_amount=1000000,
        allowed_currency="BDT",
        allowed_destination="card_visa_4242",
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=5)
    )
    save_task_scope(db_conn, **expired_scope.model_dump(mode='json'))

    action_payload = {
        "tool": "refund_order",
        "arguments": {
            "order_id": "ORD-101",
            "amount": 200000,
            "currency": "BDT",
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
            "amount": 200000,
            "currency": "BDT",
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
            "amount": 100000,
            "currency": "BDT",
            "destination": "card_visa_4242"
        },
        "idempotency_key": "idemp-failclosed-01"
    }

    result = boundary.intercept_and_evaluate(action_payload, task_scope=valid_scope)
    assert result["verdict"] == PolicyVerdict.BLOCKED.value
    assert "FAIL_CLOSED" in result["reason"]
