import pytest
import sqlite3
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app, headers={"Authorization": "Bearer test-only-operator-token"})


@pytest.fixture(autouse=True)
def reset_before_test():
    assert client.post("/api/sandbox/reset").status_code == 200


def test_api_list_and_get_orders():
    response = client.get("/api/sandbox/orders")
    assert response.status_code == 200
    assert len(response.json()["orders"]) >= 4
    assert client.get("/api/sandbox/orders/ORD-101").json()["order"]["refundable_amount"] == 25000
    assert client.get("/api/sandbox/orders/ORD-NONEXISTENT").status_code == 404


def test_paid_amount_edit_preserves_refunds_and_rejects_stale_changes():
    path = "/api/sandbox/orders/ORD-101"
    payload = {"paid_amount": 30000, "expected_paid_amount": 25000, "expected_refundable_amount": 25000}
    assert TestClient(app).patch(path, json=payload).status_code == 401
    edited = client.patch(path, json=payload)
    assert edited.status_code == 200
    assert edited.json()["order"]["refundable_amount"] == 30000
    assert client.patch(path, json=payload).status_code == 409

    from app.sandbox.db import get_connection
    from app.sandbox.service import execute_sandbox_refund
    conn = get_connection()
    try:
        execute_sandbox_refund(conn, "ORD-101", 4000, "USD", "card_visa_4242", "paid-amount-test")
    finally:
        conn.close()
    payload = {"paid_amount": 3999, "expected_paid_amount": 30000, "expected_refundable_amount": 26000}
    assert client.patch(path, json=payload).status_code == 422
    order = client.patch(path, json={**payload, "paid_amount": 4000}).json()["order"]
    assert (order["paid_amount"], order["refundable_amount"], order["status"]) == (4000, 0, "fully_refunded")
    assert client.get("/api/sandbox/refunds").json()["refunds"][0]["amount"] == 4000
    assert client.post("/api/sandbox/reset").status_code == 200
    assert client.get(path).json()["order"]["refundable_amount"] == 25000


def test_pending_approval_rechecks_edited_order_balance():
    order_path = "/api/sandbox/orders/ORD-101"
    scope = client.post("/api/governance/scopes", json={
        "operator_id": "operator", "order_id": "ORD-101", "max_amount": 15000,
        "allowed_currency": "USD", "allowed_destination": "card_visa_4242",
    }).json()["scope"]
    result = client.post("/api/governance/evaluate", json={
        "tool": "refund_order", "scope_id": scope["scope_id"], "idempotency_key": "edited-balance-pending",
        "arguments": {"order_id": "ORD-101", "amount": 15000, "currency": "USD", "destination": "card_visa_4242"},
    }).json()["result"]
    assert result["verdict"] == "APPROVAL_REQUIRED"
    assert client.patch(order_path, json={
        "paid_amount": 10000, "expected_paid_amount": 25000, "expected_refundable_amount": 25000,
    }).status_code == 200
    decide_path = f"/api/governance/approvals/{result['action_id']}/decide"
    rejected_approval = client.post(decide_path, json={"decision": "approve", "reviewer_id": "operator"})
    assert rejected_approval.status_code == 400
    assert "EXCEEDS_ORDER_BALANCE" in rejected_approval.json()["detail"]["message"]
    assert client.post(decide_path, json={"decision": "reject", "reviewer_id": "operator"}).status_code == 200
    assert client.get(order_path).json()["order"]["refundable_amount"] == 10000
    assert client.get("/api/sandbox/refunds").json()["refunds"] == []


def test_direct_refund_cannot_bypass_governance():
    response = client.post("/api/sandbox/refunds", json={
        "order_id": "ORD-101", "amount": 1000, "currency": "USD",
        "destination": "card_visa_4242", "idempotency_key": "direct-attempt",
    })
    assert response.status_code == 405
    assert client.get("/api/sandbox/orders/ORD-101").json()["order"]["refundable_amount"] == 25000


def test_api_reset_endpoint():
    assert client.post("/api/sandbox/reset").status_code == 200
    assert client.get("/api/sandbox/orders/ORD-101").json()["order"]["refundable_amount"] == 25000
    from app.sandbox.db import get_connection
    conn = get_connection()
    try:
        assert conn.execute("SELECT COUNT(*) FROM audit_events WHERE verdict='SANDBOX_RESET'").fetchone()[0] >= 1
    finally:
        conn.close()


def test_reset_rolls_back_when_audit_write_fails():
    from app.sandbox.db import get_connection
    conn = get_connection()
    conn.execute("UPDATE orders SET refundable_amount = 12345 WHERE id = 'ORD-101'")
    conn.execute("CREATE TRIGGER fail_reset_audit BEFORE INSERT ON audit_events WHEN NEW.verdict = 'SANDBOX_RESET' BEGIN SELECT RAISE(ABORT, 'test'); END")
    conn.commit()
    try:
        with pytest.raises(sqlite3.IntegrityError):
            client.post('/api/sandbox/reset')
        assert conn.execute("SELECT refundable_amount FROM orders WHERE id = 'ORD-101'").fetchone()[0] == 12345
    finally:
        conn.execute('DROP TRIGGER fail_reset_audit')
        conn.commit()
        conn.close()
