"""
Focused Regression Test Suite: MCP Caller Identity, Refund Authorization & Data Minimization.
Directly verifies remediation of vulnerabilities A1, A2, and A3:
1. Missing authenticated caller fails closed.
2. Spoofed matching caller_id parameter fails closed.
3. Valid scope ID belonging to a different operator fails closed.
4. Anonymous refund execution attempt fails closed.
5. Policy missing or tool excluded fails closed.
6. Failed audit insertion fails closed without data leakage.
7. Sensitive response fields (customer PII and unmasked destination) are omitted.
8. Authorized MCP tool execution succeeds for legitimate matching operator.
9. Concurrent duplicate refund attempts with matching idempotency keys are safely deduplicated.
"""
import json
import sqlite3
import pytest
import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from app.sandbox.db import init_db
from app.sandbox.service import save_task_scope, get_order, reset_synthetic_data
from app.policy.storage import save_policy
from app.policy.models import PolicyConfig
from app.governance.mcp_server import create_governed_mcp_server

@pytest.fixture
def clean_db():
    conn = init_db(":memory:")
    reset_synthetic_data(conn)
    return conn

@pytest.fixture
def active_scope(clean_db):
    expiry = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    return save_task_scope(
        conn=clean_db,
        scope_id="scope-alice-final",
        operator_id="operator_alice",
        order_id="ORD-101",
        allowed_action="refund_order",
        max_amount=5000,
        allowed_currency="USD",
        allowed_destination="card_visa_4242",
        expires_at=expiry
    )

# 1. Missing authenticated caller fails closed
@pytest.mark.asyncio
async def test_regression_01_missing_authenticated_caller_fails_closed(clean_db, active_scope):
    """An unauthenticated session (authenticated_caller=None) must fail closed when querying an operator scope."""
    server_anon = create_governed_mcp_server(clean_db, authenticated_caller=None)
    res = await server_anon.call_tool("lookup_order", {
        "order_id": "ORD-101",
        "scope_id": active_scope["scope_id"]
    })
    assert res.is_error is True
    data = json.loads(res.content[0].text)
    assert data.get("error") == "CALLER_IDENTITY_MISMATCH"
    assert "Rahim Chowdhury" not in res.content[0].text
    assert "card_visa_4242" not in res.content[0].text

# 2. Spoofed matching caller_id fails closed
@pytest.mark.asyncio
async def test_regression_02_spoofed_matching_caller_id_fails_closed(clean_db, active_scope):
    """An unauthenticated client supplying caller_id='operator_alice' must NOT be accepted as Alice."""
    server_anon = create_governed_mcp_server(clean_db, authenticated_caller=None)
    res = await server_anon.call_tool("lookup_order", {
        "order_id": "ORD-101",
        "scope_id": active_scope["scope_id"],
        "caller_id": "operator_alice"
    })
    assert res.is_error is True
    data = json.loads(res.content[0].text)
    assert data.get("error") == "CALLER_IDENTITY_MISMATCH"
    assert "Rahim Chowdhury" not in res.content[0].text

# 3. Valid scope ID belonging to a different operator fails closed
@pytest.mark.asyncio
async def test_regression_03_scope_belonging_to_different_operator_fails_closed(clean_db, active_scope):
    """An authenticated session for Bob must NOT be able to access Alice's task scope."""
    server_bob = create_governed_mcp_server(clean_db, authenticated_caller="operator_bob")
    res = await server_bob.call_tool("lookup_order", {
        "order_id": "ORD-101",
        "scope_id": active_scope["scope_id"],
        "caller_id": "operator_bob"
    })
    assert res.is_error is True
    data = json.loads(res.content[0].text)
    assert data.get("error") == "CALLER_IDENTITY_MISMATCH"

# 4. Anonymous refund execution attempt fails closed
@pytest.mark.asyncio
async def test_regression_04_anonymous_refund_execution_attempt_fails_closed(clean_db, active_scope):
    """Scope possession alone must NOT allow executing refunds from an unauthenticated session."""
    server_anon = create_governed_mcp_server(clean_db, authenticated_caller=None)
    res = await server_anon.call_tool("refund_order", {
        "order_id": "ORD-101",
        "amount": 1000,
        "currency": "USD",
        "destination": "card_visa_4242",
        "reason": "Unauthorized refund attempt",
        "scope_id": active_scope["scope_id"],
        "idempotency_key": "idemp_anon_refund_01"
    })
    assert res.is_error is True
    data = json.loads(res.content[0].text)
    assert data.get("error") == "CALLER_IDENTITY_MISMATCH"
    # Verify zero backend deduction
    order = get_order(clean_db, "ORD-101")
    assert order["refundable_amount"] == 25000

# 5. Malicious client presenting another operator's valid scope ID for refund
@pytest.mark.asyncio
async def test_regression_05_malicious_operator_cross_scope_refund_fails_closed(clean_db, active_scope):
    """Operator Bob presenting Alice's valid scope ID must be blocked immediately."""
    server_bob = create_governed_mcp_server(clean_db, authenticated_caller="operator_bob")
    res = await server_bob.call_tool("refund_order", {
        "order_id": "ORD-101",
        "amount": 1000,
        "currency": "USD",
        "destination": "card_visa_4242",
        "reason": "Bob stealing Alice's scope",
        "scope_id": active_scope["scope_id"],
        "idempotency_key": "idemp_bob_refund_steal_01"
    })
    assert res.is_error is True
    data = json.loads(res.content[0].text)
    assert data.get("error") == "CALLER_IDENTITY_MISMATCH"
    # Verify zero backend deduction
    order = get_order(clean_db, "ORD-101")
    assert order["refundable_amount"] == 25000

# 6. Policy missing or tool excluded fails closed
@pytest.mark.asyncio
async def test_regression_06_policy_missing_or_tool_excluded_fails_closed(clean_db, active_scope):
    """When policy is missing or tool is excluded, MCP tools must fail closed."""
    # A. Corrupt/missing policy
    clean_db.execute("UPDATE policy_config SET config = 'INVALID_JSON{' WHERE id = 1")
    server_alice = create_governed_mcp_server(clean_db, authenticated_caller="operator_alice")
    
    r_lookup = await server_alice.call_tool("lookup_order", {
        "order_id": "ORD-101",
        "scope_id": active_scope["scope_id"]
    })
    assert r_lookup.is_error is True
    assert json.loads(r_lookup.content[0].text).get("error") == "POLICY_UNAVAILABLE"

    r_refund = await server_alice.call_tool("refund_order", {
        "order_id": "ORD-101",
        "amount": 1000,
        "currency": "USD",
        "destination": "card_visa_4242",
        "reason": "test",
        "scope_id": active_scope["scope_id"],
        "idempotency_key": "idemp_pol_miss"
    })
    assert r_refund.is_error is True
    assert json.loads(r_refund.content[0].text).get("error") == "POLICY_UNAVAILABLE"

    # B. Tool excluded from allowed_tools (refund_order excluded)
    save_policy(clean_db, PolicyConfig(allowed_tools=["lookup_order"]))
    r_refund_ex = await server_alice.call_tool("refund_order", {
        "order_id": "ORD-101",
        "amount": 1000,
        "currency": "USD",
        "destination": "card_visa_4242",
        "reason": "test",
        "scope_id": active_scope["scope_id"],
        "idempotency_key": "idemp_tool_ex"
    })
    assert r_refund_ex.is_error is True
    assert json.loads(r_refund_ex.content[0].text).get("error") == "TOOL_NOT_ALLOWED"

    # lookup_order excluded
    save_policy(clean_db, PolicyConfig(allowed_tools=["refund_order"]))
    r_lookup_ex = await server_alice.call_tool("lookup_order", {
        "order_id": "ORD-101",
        "scope_id": active_scope["scope_id"]
    })
    assert r_lookup_ex.is_error is True
    assert json.loads(r_lookup_ex.content[0].text).get("error") == "TOOL_NOT_ALLOWED"

# 7. Failed audit insertion fails closed
@pytest.mark.asyncio
async def test_regression_07_failed_audit_insertion_fails_closed(clean_db, active_scope):
    """If audit log write fails, lookup_order and refund_order must fail closed without returning data."""
    server_alice = create_governed_mcp_server(clean_db, authenticated_caller="operator_alice")
    clean_db.execute("DROP TABLE audit_events")
    
    r_lookup = await server_alice.call_tool("lookup_order", {
        "order_id": "ORD-101",
        "scope_id": active_scope["scope_id"]
    })
    assert r_lookup.is_error is True
    assert json.loads(r_lookup.content[0].text).get("error") == "AUDIT_LOGGING_FAILED"

    r_refund = await server_alice.call_tool("refund_order", {
        "order_id": "ORD-101",
        "amount": 1000,
        "currency": "USD",
        "destination": "card_visa_4242",
        "reason": "test",
        "scope_id": active_scope["scope_id"],
        "idempotency_key": "idemp_audit_fail"
    })
    assert r_refund.is_error is True
    assert json.loads(r_refund.content[0].text).get("error") == "AUDIT_LOGGING_FAILED"

# 8. Sensitive response fields minimized (Zero PII, Zero Unmasked Destinations)
@pytest.mark.asyncio
async def test_regression_08_sensitive_response_fields_minimized(clean_db, active_scope):
    """Authorized lookup_order must return order status and masked destination, with zero customer PII."""
    server_alice = create_governed_mcp_server(clean_db, authenticated_caller="operator_alice")
    res = await server_alice.call_tool("lookup_order", {
        "order_id": "ORD-101",
        "scope_id": active_scope["scope_id"]
    })
    assert res.is_error is False
    data = json.loads(res.content[0].text)
    
    # Must NOT contain customer PII
    assert "customer_name" not in data, f"Leaked customer_name: {data}"
    # Must NOT contain unmasked original destination
    assert "original_destination" not in data, f"Leaked original_destination: {data}"
    # Must contain masked destination
    assert data["masked_destination"] == "card...4242"
    # Must contain essential balance information
    assert data["order_id"] == "ORD-101"
    assert data["currency"] == "USD"
    assert data["paid_amount"] == 25000
    assert data["refundable_amount"] == 25000
    assert data["status"] == "paid"

# 9. Authorized MCP tool execution succeeds for matching operator
@pytest.mark.asyncio
async def test_regression_09_authorized_mcp_tool_execution(clean_db, active_scope):
    """Legitimate operator Alice executing within bounds must succeed."""
    server_alice = create_governed_mcp_server(clean_db, authenticated_caller="operator_alice")
    
    # Lookup
    r_lookup = await server_alice.call_tool("lookup_order", {
        "order_id": "ORD-101",
        "scope_id": active_scope["scope_id"]
    })
    assert r_lookup.is_error is False
    
    # Refund under auto-allow
    r_refund = await server_alice.call_tool("refund_order", {
        "order_id": "ORD-101",
        "amount": 2500,
        "currency": "USD",
        "destination": "card_visa_4242",
        "reason": "Authorized legitimate refund",
        "scope_id": active_scope["scope_id"],
        "idempotency_key": "idemp_alice_auth_01"
    })
    assert r_refund.is_error is False
    eval_res = json.loads(r_refund.content[0].text)
    assert eval_res["verdict"] == "ALLOWED"
    assert eval_res["executed"] is True
    
    # Verify balance was updated
    order = get_order(clean_db, "ORD-101")
    assert order["refundable_amount"] == 22500

# 10. Concurrent duplicate refund attempts with matching idempotency keys
@pytest.mark.asyncio
async def test_regression_10_concurrent_duplicate_refund_attempts(clean_db, active_scope):
    """Multiple concurrent refund calls with the same idempotency key must not double-refund."""
    server_alice = create_governed_mcp_server(clean_db, authenticated_caller="operator_alice")
    shared_key = f"concurrent_idemp_{uuid.uuid4().hex}"

    async def call_refund():
        return await server_alice.call_tool("refund_order", {
            "order_id": "ORD-101",
            "amount": 1000,
            "currency": "USD",
            "destination": "card_visa_4242",
            "reason": "Concurrent stress test",
            "scope_id": active_scope["scope_id"],
            "idempotency_key": shared_key
        })

    results = await asyncio.gather(*[call_refund() for _ in range(5)])
    success_count = 0
    duplicate_count = 0

    for r in results:
        data = json.loads(r.content[0].text)
        if not r.is_error and data.get("verdict") == "ALLOWED":
            success_count += 1
        elif r.is_error and data.get("error") == "IDEMPOTENCY_KEY_REUSED":
            duplicate_count += 1

    assert success_count == 1, f"Expected exactly 1 success, got {success_count}"
    assert duplicate_count == 4, f"Expected 4 duplicate rejections, got {duplicate_count}"
    
    # Assert exact deduction occurred once
    order = get_order(clean_db, "ORD-101")
    assert order["refundable_amount"] == 24000
