import pytest
import json
from datetime import datetime, timedelta, timezone
from app.sandbox.db import init_db
from app.sandbox.service import reset_synthetic_data, save_task_scope, get_order
from app.governance.mcp_server import create_governed_mcp_server

@pytest.fixture
def test_setup():
    conn = init_db(":memory:")
    reset_synthetic_data(conn)
    server = create_governed_mcp_server(conn, authenticated_caller="operator_dipto")
    yield conn, server
    conn.close()

@pytest.mark.asyncio
async def test_mcp_tools_list(test_setup):
    conn, server = test_setup
    tools = await server.list_tools()
    tool_names = [t.name for t in tools]
    assert "lookup_order" in tool_names
    assert "refund_order" in tool_names

@pytest.mark.asyncio
async def test_mcp_lookup_order(test_setup):
    conn, server = test_setup
    expiry = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    save_task_scope(
        conn=conn, scope_id="scope-mcp-lookup", operator_id="operator_dipto", order_id="ORD-101",
        allowed_action="refund_order", max_amount=5000, allowed_currency="USD",
        allowed_destination="card_visa_4242", expires_at=expiry
    )
    call_res = await server.call_tool("lookup_order", {"order_id": "ORD-101", "scope_id": "scope-mcp-lookup", "caller_id": "operator_dipto"})
    assert not call_res.is_error
    data = json.loads(call_res.content[0].text)
    assert data["order_id"] == "ORD-101"
    assert data["paid_amount"] == 25000
    assert "customer_name" not in data
    assert "original_destination" not in data
    assert data["masked_destination"] == "card...4242"


@pytest.mark.asyncio
async def test_mcp_refund_requires_stable_idempotency_key(test_setup):
    conn, server = test_setup
    expiry = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    save_task_scope(conn=conn, scope_id='require-key', operator_id='operator_dipto', order_id='ORD-101',
                    allowed_action='refund_order', max_amount=5000, allowed_currency='USD',
                    allowed_destination='card_visa_4242', expires_at=expiry)
    args = {'order_id': 'ORD-101', 'amount': 4000, 'currency': 'USD',
            'destination': 'card_visa_4242', 'reason': 'synthetic', 'scope_id': 'require-key'}
    for key in (None, '', '   ', 'x' * 129):
        result = await server.call_tool('refund_order', {**args, 'idempotency_key': key})
        assert json.loads(result.content[0].text)['error'] == 'IDEMPOTENCY_KEY_REQUIRED'
    assert get_order(conn, 'ORD-101')['refundable_amount'] == 25000

@pytest.mark.asyncio
async def test_mcp_refund_within_task_scope_allowed(test_setup):
    conn, server = test_setup
    # Operator grants task scope for ORD-101
    expiry = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    save_task_scope(
        conn=conn,
        scope_id="scope-mcp-01",
        operator_id="operator_dipto",
        order_id="ORD-101",
        allowed_action="refund_order",
        max_amount=5000,  # $50.00
        allowed_currency="USD",
        allowed_destination="card_visa_4242",
        expires_at=expiry
    )

    # Agent calls refund_order through MCP
    call_res = await server.call_tool(
        "refund_order",
        {
            "order_id": "ORD-101",
            "amount": 4000,  # $40.00
            "currency": "USD",
            "destination": "card_visa_4242",
            "reason": "Late delivery apology refund",
            "scope_id": "scope-mcp-01", "idempotency_key": "mcp-allow"
        }
    )
    assert not call_res.is_error
    result = json.loads(call_res.content[0].text)
    assert result["verdict"] == "ALLOWED"
    assert result["executed"] is True
    assert result["refund"]["amount"] == 4000

    # Verify physical sandbox state
    order = get_order(conn, "ORD-101")
    assert order["refundable_amount"] == 21000

@pytest.mark.asyncio
async def test_mcp_small_refund_outside_scope_is_blocked(test_setup):
    conn, server = test_setup
    # Operator grants scope for ORD-101 only
    expiry = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    save_task_scope(
        conn=conn,
        scope_id="scope-mcp-02",
        operator_id="operator_dipto",
        order_id="ORD-101",
        allowed_action="refund_order",
        max_amount=5000,
        allowed_currency="USD",
        allowed_destination="card_visa_4242",
        expires_at=expiry
    )

    # Rogue agent attempts to refund ORD-102 (even for just $10 = 1000 cents)
    call_res = await server.call_tool(
        "refund_order",
        {
            "order_id": "ORD-102",  # VIOLATION: Not authorized by scope!
            "amount": 1000,
            "currency": "USD",
            "destination": "card_mc_5555",
            "reason": "Unauthorized refund",
            "scope_id": "scope-mcp-02", "idempotency_key": "mcp-block"
        }
    )
    result = json.loads(call_res.content[0].text)
    assert result["verdict"] == "BLOCKED"
    assert result["executed"] is False
    assert "OUTSIDE_TRUSTED_TASK_SCOPE" in result["reason"]

    # Verify physical sandbox state: ORD-102 balance MUST NOT CHANGE
    order_102 = get_order(conn, "ORD-102")
    assert order_102["refundable_amount"] == 4000

@pytest.mark.asyncio
async def test_mcp_refund_requiring_human_approval(test_setup):
    conn, server = test_setup
    # Operator grants scope for up to $300
    expiry = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    save_task_scope(
        conn=conn,
        scope_id="scope-mcp-03",
        operator_id="operator_dipto",
        order_id="ORD-101",
        allowed_action="refund_order",
        max_amount=30000,
        allowed_currency="USD",
        allowed_destination="card_visa_4242",
        expires_at=expiry
    )

    # Agent calls refund for $250
    call_res = await server.call_tool(
        "refund_order",
        {
            "order_id": "ORD-101",
            "amount": 25000,
            "currency": "USD",
            "destination": "card_visa_4242",
            "reason": "Customer cancellation",
            "scope_id": "scope-mcp-03", "idempotency_key": "mcp-approval"
        }
    )
    result = json.loads(call_res.content[0].text)
    assert result["verdict"] == "APPROVAL_REQUIRED"
    assert result["executed"] is False
    assert result["pending_approval"] is True

    # Backend balance MUST NOT be deducted
    order = get_order(conn, "ORD-101")
    assert order["refundable_amount"] == 25000


@pytest.mark.asyncio
async def test_lookup_order_requires_valid_scope(test_setup):
    conn, server = test_setup
    expiry = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    save_task_scope(
        conn=conn,
        scope_id="scope-lookup-req",
        operator_id="operator_dipto",
        order_id="ORD-101",
        allowed_action="refund_order",
        max_amount=5000,
        allowed_currency="USD",
        allowed_destination="card_visa_4242",
        expires_at=expiry
    )
    # When active scopes exist, lookup_order without scope_id must be blocked
    call_res = await server.call_tool("lookup_order", {"order_id": "ORD-101"})
    assert call_res.is_error is True
    err = json.loads(call_res.content[0].text)
    assert err["error"] == "SCOPE_ID_REQUIRED"

    audit = conn.execute("SELECT verdict, reason FROM audit_events WHERE tool = 'lookup_order' ORDER BY rowid DESC LIMIT 1").fetchone()
    assert audit["verdict"] == "BLOCKED"
    assert "OUTSIDE_TRUSTED_TASK_SCOPE: Scope ID required for lookup" in audit["reason"]


@pytest.mark.asyncio
async def test_lookup_order_cross_scope_blocked(test_setup):
    conn, server = test_setup
    expiry = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    save_task_scope(
        conn=conn,
        scope_id="scope-lookup-cross",
        operator_id="operator_dipto",
        order_id="ORD-101",
        allowed_action="refund_order",
        max_amount=5000,
        allowed_currency="USD",
        allowed_destination="card_visa_4242",
        expires_at=expiry
    )
    # Scope is for ORD-101, agent attempts to read ORD-104 (enterprise order)
    call_res = await server.call_tool("lookup_order", {"order_id": "ORD-104", "scope_id": "scope-lookup-cross", "caller_id": "operator_dipto"})
    assert call_res.is_error is True
    err = json.loads(call_res.content[0].text)
    assert err["error"] == "OUTSIDE_TRUSTED_TASK_SCOPE"

    audit = conn.execute("SELECT verdict, reason FROM audit_events WHERE tool = 'lookup_order' ORDER BY rowid DESC LIMIT 1").fetchone()
    assert audit["verdict"] == "BLOCKED"
    assert "OUTSIDE_TRUSTED_TASK_SCOPE: Scope authorized order 'ORD-101', attempted 'ORD-104'" in audit["reason"]


@pytest.mark.asyncio
async def test_lookup_order_expired_scope_blocked(test_setup):
    conn, server = test_setup
    past_expiry = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    save_task_scope(
        conn=conn,
        scope_id="scope-lookup-expired",
        operator_id="operator_dipto",
        order_id="ORD-101",
        allowed_action="refund_order",
        max_amount=5000,
        allowed_currency="USD",
        allowed_destination="card_visa_4242",
        expires_at=past_expiry
    )
    call_res = await server.call_tool("lookup_order", {"order_id": "ORD-101", "scope_id": "scope-lookup-expired", "caller_id": "operator_dipto"})
    assert call_res.is_error is True
    err = json.loads(call_res.content[0].text)
    assert err["error"] == "TASK_SCOPE_EXPIRED"

    audit = conn.execute("SELECT verdict, reason FROM audit_events WHERE tool = 'lookup_order' ORDER BY rowid DESC LIMIT 1").fetchone()
    assert audit["verdict"] == "BLOCKED"
    assert audit["reason"] == "TASK_SCOPE_EXPIRED"


@pytest.mark.asyncio
async def test_lookup_order_within_scope_allowed(test_setup):
    conn, server = test_setup
    expiry = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    save_task_scope(
        conn=conn,
        scope_id="scope-lookup-valid",
        operator_id="operator_dipto",
        order_id="ORD-101",
        allowed_action="refund_order",
        max_amount=5000,
        allowed_currency="USD",
        allowed_destination="card_visa_4242",
        expires_at=expiry
    )
    call_res = await server.call_tool("lookup_order", {"order_id": "ORD-101", "scope_id": "scope-lookup-valid", "caller_id": "operator_dipto"})
    assert call_res.is_error is False
    data = json.loads(call_res.content[0].text)
    assert data["order_id"] == "ORD-101"
    assert data["paid_amount"] == 25000
    assert "customer_name" not in data
    assert "original_destination" not in data
    assert data["masked_destination"] == "card...4242"

    audit = conn.execute("SELECT verdict, reason FROM audit_events WHERE tool = 'lookup_order' ORDER BY rowid DESC LIMIT 1").fetchone()
    assert audit["verdict"] == "ALLOWED"
    assert audit["reason"] == "Order lookup succeeded"

