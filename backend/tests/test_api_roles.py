"""Admin and user roles through the real app: the user panel may only test refunds."""
import pytest
from fastapi.testclient import TestClient

from app.auth import USER_ROUTES
from app.main import app

pytestmark = pytest.mark.usefixtures("stub_ticket_provider")

admin = TestClient(app, headers={"Authorization": "Bearer test-only-operator-token"})
user = TestClient(app, headers={"Authorization": "Bearer test-only-user-token"})


@pytest.fixture(autouse=True)
def reset_sandbox():
    admin.post("/api/sandbox/reset")


def _user_scope(max_amount=3_000_000):
    res = user.post("/api/governance/scopes", json={
        "order_id": "ORD-101", "allowed_action": "refund_order", "max_amount": max_amount,
        "allowed_currency": "BDT", "allowed_destination": "card_visa_4242", "expires_in_hours": 1,
    })
    assert res.status_code == 201
    return res.json()["scope"]["scope_id"]


def test_me_reports_role_and_rejects_bad_tokens():
    assert admin.get("/api/me").json() == {"role": "admin"}
    assert user.get("/api/me").json() == {"role": "user"}
    assert TestClient(app).get("/api/me").status_code == 401
    assert TestClient(app, headers={"Authorization": "Bearer wrong"}).get("/api/me").status_code == 401


def test_user_is_denied_every_route_outside_the_allowlist():
    # Walks the real route table, so a newly added route is admin-only unless allowlisted.
    checked = 0
    for template, operations in app.openapi()["paths"].items():
        if not template.startswith("/api/") or template == "/api/health":
            continue
        path = template.replace("{", "").replace("}", "")
        for method in (m.upper() for m in operations):
            if (method, path) in USER_ROUTES:
                continue
            res = user.request(method, path)
            assert res.status_code == 403, (method, path)
            assert res.json() == {"detail": "Admin access required"}
            checked += 1
    assert checked >= 10


def test_user_allowlist_routes_reach_the_app():
    assert user.get("/api/sandbox/orders").status_code == 200
    assert user.get("/api/governance/policy").status_code == 200
    assert user.get("/api/governance/actions/lookup", params={"idempotency_key": "none"}).status_code != 403


def test_user_cannot_change_admin_state():
    before = admin.get("/api/governance/policy").json()
    assert user.put("/api/governance/policy", json={"auto_allow_threshold": 9_000_000}).status_code == 403
    assert user.patch("/api/sandbox/orders/ORD-101", json={"paid_amount": 1}).status_code == 403
    assert user.post("/api/sandbox/reset").status_code == 403
    assert admin.get("/api/governance/policy").json() == before


def test_user_small_refund_executes_within_policy():
    trace = user.post("/api/agent/process-ticket", json={
        "ticket_text": "Refund ৳4,000 for ORD-101 to card_visa_4242",
        "scope_id": _user_scope(), "idempotency_key": "role-small",
    }).json()["trace"]
    assert trace["boundary_verdict"] == "ALLOWED" and trace["executed"] is True
    assert user.get("/api/governance/actions/lookup", params={"idempotency_key": "role-small"}).status_code == 200


def test_user_large_refund_needs_admin_approval():
    trace = user.post("/api/agent/process-ticket", json={
        "ticket_text": "Refund ৳25,000 for ORD-101 to card_visa_4242",
        "scope_id": _user_scope(), "idempotency_key": "role-large",
    }).json()["trace"]
    assert trace["boundary_verdict"] == "APPROVAL_REQUIRED" and not trace["executed"]

    assert user.get("/api/governance/pending-approvals").status_code == 403
    pending = admin.get("/api/governance/pending-approvals").json()["pending_actions"]
    assert len(pending) == 1
    action_id = pending[0]["action_id"]

    decision = {"decision": "approve", "reviewer_id": "demo_operator"}
    assert user.post(f"/api/governance/approvals/{action_id}/decide", json=decision).status_code == 403
    assert admin.get("/api/sandbox/orders/ORD-101").json()["order"]["refundable_amount"] == 2_500_000

    assert admin.post(f"/api/governance/approvals/{action_id}/decide", json=decision).status_code == 200
    assert admin.get("/api/sandbox/orders/ORD-101").json()["order"]["refundable_amount"] == 0
