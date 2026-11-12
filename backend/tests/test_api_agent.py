import pytest

pytestmark = pytest.mark.usefixtures("stub_ticket_provider")

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app, headers={"Authorization": "Bearer test-only-operator-token"})

@pytest.fixture(autouse=True)
def reset_sandbox():
    client.post("/api/sandbox/reset")

def test_api_get_benchmark_tickets():
    res = client.get("/api/agent/tickets")
    assert res.status_code == 200
    tickets = res.json()["tickets"]
    assert len(tickets) >= 5
    ids = [t["id"] for t in tickets]
    assert "TICKET-EN-01" in ids
    assert "TICKET-BN-01" in ids
    assert "TICKET-ADV-01" in ids


def test_process_ticket_rejects_empty_and_oversized_input():
    for ticket in ('', 'x' * 10001):
        response = client.post('/api/agent/process-ticket', json={'ticket_text': ticket, 'idempotency_key': 'size-test'})
        assert response.status_code == 422


def test_process_ticket_requires_a_stable_key():
    for key in (None, '', '   '):
        response = client.post('/api/agent/process-ticket', json={'ticket_text': 'Refund $40', 'idempotency_key': key})
        assert response.status_code == 422

def test_api_process_ticket_end_to_end(monkeypatch):
    from mcp.client.client import Client
    calls = []
    original = Client.call_tool
    async def observed(self, name, arguments, *args, **kwargs):
        calls.append(name)
        return await original(self, name, arguments, *args, **kwargs)
    monkeypatch.setattr(Client, 'call_tool', observed)
    # 1. Authorize task scope for ORD-101
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

    # 2. Process ticket TICKET-EN-01 via Agent API
    res = client.post("/api/agent/process-ticket", json={
        "ticket_text": "Hello, my order ORD-101 arrived with minor box damage. Please refund $40 back to my card.",
        "scope_id": scope_id,
        "idempotency_key": "agent-e2e"
    })
    assert res.status_code == 200
    trace = res.json()["trace"]
    assert trace["language"] == "en"
    assert trace["parsed_parameters"]["order_id"] == "ORD-101"
    assert trace["parsed_parameters"]["amount"] == 4000
    assert trace["boundary_verdict"] == "APPROVAL_REQUIRED"
    assert trace["executed"] is False
    assert 'refund_order' in calls
    assert trace['transport'] == 'mcp_in_memory'

    assert client.get("/api/sandbox/orders/ORD-101").json()["order"]["refundable_amount"] == 25000
    approved = client.post(f"/api/governance/approvals/{trace['action_id']}/decide", json={
        "decision": "approve", "reviewer_id": "demo_operator",
    })
    assert approved.status_code == 200
    assert approved.json()["result"]["status"] == "executed"
    order_res = client.get("/api/sandbox/orders/ORD-101")
    assert order_res.json()["order"]["refundable_amount"] == 21000


def test_agent_mcp_denial_and_approval_leave_sandbox_unchanged():
    scope = client.post('/api/governance/scopes', json={
        'operator_id': 'demo_operator', 'order_id': 'ORD-101',
        'allowed_action': 'refund_order', 'max_amount': 30000,
        'allowed_currency': 'USD', 'allowed_destination': 'card_visa_4242',
        'expires_in_hours': 1,
    }).json()['scope']['scope_id']
    blocked = client.post('/api/agent/process-ticket', json={
        'ticket_text': 'Refund $10 for ORD-102 to card_mc_5555', 'scope_id': scope,
        'idempotency_key': 'agent-blocked',
    }).json()['trace']
    assert blocked['transport'] == 'mcp_in_memory'
    assert blocked['boundary_verdict'] == 'BLOCKED'
    pending = client.post('/api/agent/process-ticket', json={
        'ticket_text': 'Refund $250 for ORD-101 to card_visa_4242', 'scope_id': scope,
        'idempotency_key': 'agent-pending',
    }).json()['trace']
    assert pending['boundary_verdict'] == 'APPROVAL_REQUIRED'
    assert not pending['executed']
    assert client.get('/api/sandbox/orders/ORD-101').json()['order']['refundable_amount'] == 25000
    assert client.get('/api/sandbox/orders/ORD-102').json()['order']['refundable_amount'] == 4000


def test_agent_mcp_retry_with_same_key_does_not_queue_twice():
    scope = client.post('/api/governance/scopes', json={
        'operator_id': 'demo_operator', 'order_id': 'ORD-101',
        'allowed_action': 'refund_order', 'max_amount': 5000,
        'allowed_currency': 'USD', 'allowed_destination': 'card_visa_4242',
        'expires_in_hours': 1,
    }).json()['scope']['scope_id']
    request = {'ticket_text': 'Refund $10 for ORD-101 to card_visa_4242',
               'scope_id': scope, 'idempotency_key': 'agent-retry-test'}
    assert client.post('/api/agent/process-ticket', json=request).json()['trace']['pending_approval']
    assert client.post('/api/agent/process-ticket', json=request).status_code == 409
    assert client.get('/api/sandbox/orders/ORD-101').json()['order']['refundable_amount'] == 25000


def test_ticket_endpoint_has_no_offline_mode(monkeypatch):
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)
    request = {'ticket_text': 'Please refund $40 for ORD-101.', 'idempotency_key': 'no-offline'}
    trace = client.post('/api/agent/process-ticket', json=request).json()['trace']
    assert trace['agent_mode'] == 'model_not_configured'
    assert not trace['executed']
    assert client.post('/api/agent/process-ticket', json={**request, 'force_mode': 'synthetic'}).status_code == 422


def test_ticket_secret_is_not_copied_to_audit_or_pending_action():
    from app.sandbox.db import get_connection
    scope = client.post('/api/governance/scopes', json={
        'operator_id': 'demo_operator', 'order_id': 'ORD-101',
        'allowed_action': 'refund_order', 'max_amount': 30000,
        'allowed_currency': 'USD', 'allowed_destination': 'card_visa_4242',
        'expires_in_hours': 1,
    }).json()['scope']['scope_id']
    response = client.post('/api/agent/process-ticket', json={
        'ticket_text': 'sensitiveDEMOvalue refund $250 for ORD-101 to card_visa_4242',
        'scope_id': scope, 'idempotency_key': 'agent-private',
    })
    assert response.json()['trace']['boundary_verdict'] == 'APPROVAL_REQUIRED'
    conn = get_connection()
    try:
        assert all('sensitiveDEMOvalue' not in str(tuple(row)) for row in conn.execute('SELECT * FROM audit_events'))
        assert all('sensitiveDEMOvalue' not in str(tuple(row)) for row in conn.execute('SELECT * FROM pending_actions'))
    finally:
        conn.close()
