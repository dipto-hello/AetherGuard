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
