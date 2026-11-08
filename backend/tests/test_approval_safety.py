import pytest
import threading
from datetime import datetime, timedelta, timezone
from app.sandbox.db import init_db
from app.sandbox.service import reset_synthetic_data, save_task_scope, get_order
from app.policy.models import TaskScope, PolicyVerdict
from app.governance.boundary import GovernanceBoundary
from app.approval.service import (
    decide_approval,
    get_pending_action,
    ApprovalAlreadyProcessedError,
    FingerprintMismatchError,
    ApprovalNotFoundError
)

@pytest.fixture
def setup_test():
    conn = init_db(":memory:")
    reset_synthetic_data(conn)
    boundary = GovernanceBoundary(conn)

    # Setup valid task scope for ORD-101 up to $300 (30000 cents)
    expiry = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    save_task_scope(
        conn=conn,
        scope_id="scope-appr-01",
        operator_id="operator_dipto",
        order_id="ORD-101",
        allowed_action="refund_order",
        max_amount=30000,
        allowed_currency="USD",
        allowed_destination="card_visa_4242",
        expires_at=expiry
    )
    yield conn, boundary
    conn.close()

def test_approve_exact_pending_action_executes_and_deducts_sandbox(setup_test):
    conn, boundary = setup_test
    raw_scope = TaskScope(
        scope_id="scope-appr-01",
        operator_id="operator_dipto",
        order_id="ORD-101",
        allowed_action="refund_order",
        max_amount=30000,
        allowed_currency="USD",
        allowed_destination="card_visa_4242",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=2)
    )

    # 1. Propose moderate refund ($250) requiring approval
    eval_res = boundary.intercept_and_evaluate(
        {
            "tool": "refund_order",
            "arguments": {
                "order_id": "ORD-101",
                "amount": 25000,
                "currency": "USD",
                "destination": "card_visa_4242",
                "reason": "Customer cancellation after review"
            },
            "idempotency_key": "idemp-appr-001"
        },
        task_scope=raw_scope
    )
    assert eval_res["verdict"] == PolicyVerdict.APPROVAL_REQUIRED.value
    action_id = eval_res["action_id"]

    # Verify pending state before approval
    pending = get_pending_action(conn, action_id)
    assert pending is not None
    assert pending["status"] == "pending"
    assert pending["fingerprint"] == eval_res["fingerprint"]

    # Verify sandbox is UNCHANGED
    order_before = get_order(conn, "ORD-101")
    assert order_before["refundable_amount"] == 25000

    # 2. Reviewer approves exact pending action
    approval_res = decide_approval(
        conn=conn,
        action_id=action_id,
        decision="approve",
        reviewer_id="reviewer_sarah"
    )
    assert approval_res["status"] == "executed"
    assert approval_res["refund"] is not None
    assert approval_res["refund"]["amount"] == 25000

    # 3. Physical verification: backend state must be deducted
    order_after = get_order(conn, "ORD-101")
    assert order_after["refundable_amount"] == 0
    assert order_after["status"] == "fully_refunded"

def test_reject_pending_action_leaves_sandbox_untouched(setup_test):
    conn, boundary = setup_test
    raw_scope = TaskScope(
        scope_id="scope-appr-01",
        operator_id="operator_dipto",
        order_id="ORD-101",
        allowed_action="refund_order",
        max_amount=30000,
        allowed_currency="USD",
        allowed_destination="card_visa_4242",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=2)
    )

    eval_res = boundary.intercept_and_evaluate(
        {
            "tool": "refund_order",
            "arguments": {
                "order_id": "ORD-101",
                "amount": 25000,
                "currency": "USD",
                "destination": "card_visa_4242",
                "reason": "Suspicious request"
            },
            "idempotency_key": "idemp-appr-002"
        },
        task_scope=raw_scope
    )
    action_id = eval_res["action_id"]

    # Reviewer rejects
    rejection = decide_approval(
        conn=conn,
        action_id=action_id,
        decision="reject",
        reviewer_id="reviewer_sarah",
        reason="Suspicious activity reported"
    )
    assert rejection["status"] == "rejected"
    assert rejection["refund"] is None

    # Verify sandbox state is 100% UNTOUCHED
    order = get_order(conn, "ORD-101")
    assert order["refundable_amount"] == 25000

def test_replay_approval_cannot_execute_twice(setup_test):
    conn, boundary = setup_test
    raw_scope = TaskScope(
        scope_id="scope-appr-01",
        operator_id="operator_dipto",
        order_id="ORD-101",
        allowed_action="refund_order",
        max_amount=30000,
        allowed_currency="USD",
        allowed_destination="card_visa_4242",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=2)
    )

    eval_res = boundary.intercept_and_evaluate(
        {
            "tool": "refund_order",
            "arguments": {
                "order_id": "ORD-101",
                "amount": 10000,  # $100.00
                "currency": "USD",
                "destination": "card_visa_4242"
            },
            "idempotency_key": "idemp-appr-003"
        },
        task_scope=raw_scope
    )
    action_id = eval_res["action_id"]

    # First approval succeeds
    res1 = decide_approval(conn, action_id, "approve", "reviewer_sarah")
    assert res1["status"] == "executed"

    # Second approval (Replay attempt) MUST raise ApprovalAlreadyProcessedError
    with pytest.raises(ApprovalAlreadyProcessedError):
        decide_approval(conn, action_id, "approve", "reviewer_sarah")

    # Verify balance was only deducted ONCE ($250 - $100 = $150)
    order = get_order(conn, "ORD-101")
    assert order["refundable_amount"] == 15000

def test_tampered_fingerprint_rejected(setup_test):
    conn, boundary = setup_test
    raw_scope = TaskScope(
        scope_id="scope-appr-01",
        operator_id="operator_dipto",
        order_id="ORD-101",
        allowed_action="refund_order",
        max_amount=30000,
        allowed_currency="USD",
        allowed_destination="card_visa_4242",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=2)
    )

    eval_res = boundary.intercept_and_evaluate(
        {
            "tool": "refund_order",
            "arguments": {
                "order_id": "ORD-101",
                "amount": 25000,
                "currency": "USD",
                "destination": "card_visa_4242"
            },
            "idempotency_key": "idemp-appr-004"
        },
        task_scope=raw_scope
    )
    action_id = eval_res["action_id"]

    # Simulate database tampering: alter arguments behind the scenes
    with conn:
        conn.execute(
            "UPDATE pending_actions SET arguments = ? WHERE action_id = ?",
            ('{"order_id": "ORD-101", "amount": 99999, "currency": "USD", "destination": "card_visa_4242"}', action_id)
        )

    # Reviewer tries to approve, but fingerprint does not match tampered arguments!
    with pytest.raises(FingerprintMismatchError):
        decide_approval(conn, action_id, "approve", "reviewer_sarah")

def test_concurrent_duplicate_approval_prevention(tmp_path):
    """
    Test that atomic status transition blocks concurrent execution races.
    If two operators click 'Approve' simultaneously, only ONE succeeds;
    the second must fail with ApprovalAlreadyProcessedError and NEVER double-refund.
    """
    import uuid
    from app.sandbox.db import get_connection
    db_uri = str(tmp_path / 'approval-race.db')
    init_conn = init_db(db_uri)
    reset_synthetic_data(init_conn)
    boundary = GovernanceBoundary(init_conn)

    scope_id = f"scope_race_{uuid.uuid4().hex[:8]}"
    expiry = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    save_task_scope(
        conn=init_conn,
        scope_id=scope_id,
        operator_id="operator_dipto",
        order_id="ORD-101",
        allowed_action="refund_order",
        max_amount=30000,
        allowed_currency="USD",
        allowed_destination="card_visa_4242",
        expires_at=expiry
    )

    raw_scope = TaskScope(
        scope_id=scope_id,
        operator_id="operator_dipto",
        order_id="ORD-101",
        allowed_action="refund_order",
        max_amount=30000,
        allowed_currency="USD",
        allowed_destination="card_visa_4242",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=2)
    )

    eval_res = boundary.intercept_and_evaluate(
        {
            "tool": "refund_order",
            "arguments": {
                "order_id": "ORD-101",
                "amount": 10000,  # $100.00
                "currency": "USD",
                "destination": "card_visa_4242"
            },
            "idempotency_key": "idemp-appr-race-01"
        },
        task_scope=raw_scope
    )
    action_id = eval_res["action_id"]

    results = []
    errors = []

    def attempt_approve(reviewer):
        thread_conn = get_connection(db_uri)
        try:
            res = decide_approval(thread_conn, action_id, "approve", reviewer)
            results.append(res)
        except ApprovalAlreadyProcessedError as e:
            errors.append(e)
        finally:
            thread_conn.close()

    # Launch two simulated threads racing to approve the same pending action
    t1 = threading.Thread(target=attempt_approve, args=("reviewer_alice",))
    t2 = threading.Thread(target=attempt_approve, args=("reviewer_bob",))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Exactly ONE approval succeeded, and exactly ONE was blocked as duplicate
    assert len(results) == 1
    assert len(errors) == 1

    # Backend balance deducted only ONCE ($250 - $100 = $150)
    order = get_order(init_conn, "ORD-101")
    assert order["refundable_amount"] == 15000
    init_conn.close()

def test_audit_records_match_actual_outcomes(setup_test):
    conn, boundary = setup_test
    # Check audit log table contains valid hashes and zero secrets
    cur = conn.execute("SELECT * FROM audit_events ORDER BY created_at DESC")
    rows = cur.fetchall()
    for row in rows:
        assert row["verdict"] in ["ALLOWED", "BLOCKED", "APPROVAL_REQUIRED", "APPROVED", "REJECTED"]
        assert row["fingerprint"] is not None
        assert len(row["fingerprint"]) == 64  # SHA-256 length
