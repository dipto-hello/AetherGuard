import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app, headers={"Authorization": "Bearer test-only-operator-token"})

@pytest.fixture(autouse=True)
def reset_sandbox():
    client.post("/api/sandbox/reset")


def test_audit_log_limit_rejects_unbounded_queries():
    assert client.get('/api/governance/audit-logs', params={'limit': -1}).status_code == 422
    assert client.get('/api/governance/audit-logs', params={'limit': 201}).status_code == 422
    assert client.get('/api/governance/audit-logs', params={'limit': 200}).status_code == 200


def test_evaluate_requires_stable_idempotency_key():
    response = client.post('/api/governance/evaluate', json={'tool': 'refund_order', 'arguments': {}})
    assert response.status_code == 422

def test_evaluate_blocks_and_audits_non_text_order_id():
    scope = client.post("/api/governance/scopes", json={
        "operator_id": "operator_dipto", "order_id": "ORD-101", "max_amount": 10000,
        "allowed_destination": "card_visa_4242",
    }).json()["scope"]
    res = client.post('/api/governance/evaluate', json={
        'tool': 'refund_order', 'scope_id': scope['scope_id'], 'idempotency_key': 'bad-order-id',
        'arguments': {'order_id': {'x': 1}, 'amount': 100, 'currency': 'USD', 'destination': 'card_visa_4242'},
    })
    assert res.status_code == 200
    result = res.json()['result']
    assert result['verdict'] == 'BLOCKED' and result['executed'] is False
    logs = client.get('/api/governance/audit-logs').json()['logs']
    assert any(log['action_id'] == result['action_id'] and log['verdict'] == 'BLOCKED' for log in logs)


def test_api_create_and_get_task_scope():
    payload = {
        "operator_id": "operator_dipto",
        "order_id": "ORD-101",
        "allowed_action": "refund_order",
        "max_amount": 10000,  # $100.00
        "allowed_currency": "USD",
        "allowed_destination": "card_visa_4242",
        "expires_in_hours": 3
    }
    res = client.post("/api/governance/scopes", json=payload)
    assert res.status_code == 201
    scope = res.json()["scope"]
    assert scope["scope_id"].startswith("scope_")
    assert scope["order_id"] == "ORD-101"
    assert scope["max_amount"] == 10000

    # Retrieve scope
    get_res = client.get(f"/api/governance/scopes/{scope['scope_id']}")
    assert get_res.status_code == 200
    assert get_res.json()["scope"]["operator_id"] == "demo_operator"

def test_api_evaluate_allowed_action():
    # Create scope
    scope_res = client.post("/api/governance/scopes", json={
        "operator_id": "operator_dipto",
        "order_id": "ORD-101",
        "allowed_action": "refund_order",
        "max_amount": 5000,
        "allowed_currency": "USD",
        "allowed_destination": "card_visa_4242",
        "expires_in_hours": 1
    })
    scope_id = scope_res.json()["scope"]["scope_id"]

    eval_res = client.post("/api/governance/evaluate", json={
        "tool": "refund_order",
        "arguments": {
            "order_id": "ORD-101",
            "amount": 3500,  # $35.00
            "currency": "USD",
            "destination": "card_visa_4242",
            "reason": "Late shipment apology"
        },
        "scope_id": scope_id,
        "idempotency_key": "api-eval-01"
    })
    assert eval_res.status_code == 200
    result = eval_res.json()["result"]
    assert result["verdict"] == "ALLOWED"
    assert result["executed"] is True
    assert result["refund"]["amount"] == 3500

    # Verify audit log recorded
    logs_res = client.get("/api/governance/audit-logs")
    assert logs_res.status_code == 200
    logs = logs_res.json()["logs"]
    assert len(logs) >= 1
    assert logs[0]["verdict"] == "ALLOWED"

def test_api_evaluate_blocked_action():
    # Attempt refund on un-scoped order
    eval_res = client.post("/api/governance/evaluate", json={
        "tool": "refund_order",
        "arguments": {
            "order_id": "ORD-102",
            "amount": 1000,
            "currency": "USD",
            "destination": "card_mc_5555",
            "reason": "Un-scoped small refund"
        },
        "scope_id": None, "idempotency_key": "unscoped"  # Missing scope!
    })
    assert eval_res.status_code == 200
    result = eval_res.json()["result"]
    assert result["verdict"] == "BLOCKED"
    assert result["executed"] is False
    assert "OUTSIDE_TRUSTED_TASK_SCOPE" in result["reason"]

def test_api_policy_crud():
    get_res = client.get("/api/governance/policy")
    assert get_res.status_code == 200
    assert "auto_allow_threshold" in get_res.json()["policy"]

    update_res = client.put("/api/governance/policy", json={
        "auto_allow_threshold": 6000
    })
    assert update_res.status_code == 200
    assert update_res.json()["policy"]["auto_allow_threshold"] == 6000
    assert any(item['verdict'] == 'POLICY_UPDATED' for item in client.get('/api/governance/audit-logs?limit=100').json()['logs'])

    # Reset back to 5000
    client.put("/api/governance/policy", json={"auto_allow_threshold": 5000})


def test_policy_rejects_unsupported_tools():
    res = client.put('/api/governance/policy', json={'allowed_tools': ['refund_order', 'arbitrary_write']})
    assert res.status_code == 422

def test_api_approval_flow_via_rest():
    # 1. Create task scope for $300 on ORD-101
    scope_res = client.post("/api/governance/scopes", json={
        "operator_id": "operator_dipto",
        "order_id": "ORD-101",
        "allowed_action": "refund_order",
        "max_amount": 30000,
        "allowed_currency": "USD",
        "allowed_destination": "card_visa_4242",
        "expires_in_hours": 1
    })
    scope_id = scope_res.json()["scope"]["scope_id"]

    # 2. Trigger $250 refund -> APPROVAL_REQUIRED
    eval_res = client.post("/api/governance/evaluate", json={
        "tool": "refund_order",
        "arguments": {
            "order_id": "ORD-101",
            "amount": 25000,
            "currency": "USD",
            "destination": "card_visa_4242",
            "reason": "REST approval flow test"
        },
        "scope_id": scope_id,
        "idempotency_key": "api-eval-appr-01"
    })
    result = eval_res.json()["result"]
    assert result["verdict"] == "APPROVAL_REQUIRED"
    action_id = result["action_id"]

    # 3. Check pending approvals list
    pending_res = client.get("/api/governance/pending-approvals")
    assert pending_res.status_code == 200
    actions = pending_res.json()["pending_actions"]
    assert any(a["action_id"] == action_id for a in actions)

    # 4. Reviewer approves
    approve_res = client.post(f"/api/governance/approvals/{action_id}/decide", json={
        "decision": "approve",
        "reviewer_id": "reviewer_dipto"
    })
    assert approve_res.status_code == 200
    assert approve_res.json()["result"]["status"] == "executed"
    assert approve_res.json()["result"]["reviewer_id"] == "demo_operator"
    assert approve_res.json()["result"]["refund"]["amount"] == 25000

    # 5. Verify sandbox balance dropped
    order_res = client.get("/api/sandbox/orders/ORD-101")
    assert order_res.json()["order"]["refundable_amount"] == 0
    lookup = client.get('/api/governance/actions/lookup', params={'idempotency_key': 'api-eval-appr-01'})
    assert lookup.status_code == 200
    assert lookup.json()['action']['status'] == 'executed'
    assert lookup.json()['action']['action_id'] == action_id

    # 6. Replay attempt returns 409 Conflict
    replay_res = client.post(f"/api/governance/approvals/{action_id}/decide", json={
        "decision": "approve",
        "reviewer_id": "reviewer_dipto"
    })
    assert replay_res.status_code == 409
    assert replay_res.json()["detail"]["code"] == "ALREADY_PROCESSED"


@pytest.mark.parametrize("change, status, code", [
    ({"order_id": "ORD-999"}, 404, "ORDER_NOT_FOUND"),
    ({"allowed_currency": "BDT"}, 422, "CURRENCY_MISMATCH"),
    ({"allowed_destination": "card_other_0000"}, 422, "DESTINATION_MISMATCH"),
])
def test_scope_rejects_invalid_order_permission(change, status, code):
    payload = {"operator_id": "demo_operator", "order_id": "ORD-101",
               "max_amount": 5000, "allowed_currency": "USD",
               "allowed_destination": "card_visa_4242"}
    response = client.post("/api/governance/scopes", json={**payload, **change})
    assert response.status_code == status
    assert response.json()["detail"]["code"] == code
