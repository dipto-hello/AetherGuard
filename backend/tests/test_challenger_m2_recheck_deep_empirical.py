"""
Challenger 1 Recheck Deep Empirical Verification Suite.
Target: AetherGuard/backend/app/governance/mcp_server.py

Tests:
1. Authenticated Bob cannot spoof Alice under any caller_id variation.
2. Anonymous caller omitting caller_id cannot access Alice's scope.
3. Information leakage check (zero sensitive data leaked on error).
4. Audit events check (every blocked attempt creates a BLOCKED audit record).
5. Legitimate authorized caller (Alice) succeeds with data minimization.
6. Empty operator_id handling.
"""
import pytest
import json
import sqlite3
import asyncio
from datetime import datetime, timezone, timedelta
from app.sandbox.db import init_db
from app.sandbox.service import reset_synthetic_data, save_task_scope, get_order
from app.governance.mcp_server import create_governed_mcp_server
import mcp.types as types

@pytest.fixture
def clean_db():
    conn = init_db(":memory:")
    reset_synthetic_data(conn)
    expiry = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    # Create scope bound to operator_alice
    save_task_scope(
        conn, "scope-alice-deep", "operator_alice", "ORD-101", "refund_order",
        5000, "USD", "card_visa_4242", expiry
    )
    yield conn
    conn.close()

@pytest.mark.asyncio
@pytest.mark.parametrize("spoofed_caller_id", [
    "operator_alice",
    "operator_bob",
    None,
    "",
    "   ",
    "admin",
    "root",
    "operator_alice\x00",
    "OPERATOR_ALICE",
    "operator_alice ",
    " operator_alice",
])
async def test_authenticated_bob_spoofing_matrix_blocked(clean_db, spoofed_caller_id):
    """
    Authenticated Bob (authenticated_caller='operator_bob') must NEVER access Alice's scope,
    regardless of what caller_id parameter he supplies.
    """
    server_bob = create_governed_mcp_server(clean_db, authenticated_caller="operator_bob")
    args = {"order_id": "ORD-101", "scope_id": "scope-alice-deep"}
    if spoofed_caller_id is not None:
        args["caller_id"] = spoofed_caller_id

    res = await server_bob.call_tool("lookup_order", args)
    assert res.is_error is True, f"Failed to block spoofed_caller_id={spoofed_caller_id}"
    body = json.loads(res.content[0].text)
    assert body.get("error") == "CALLER_IDENTITY_MISMATCH"
    
    # Exfiltration check
    raw_text = res.content[0].text
    assert "Rahim Chowdhury" not in raw_text
    assert "card_visa_4242" not in raw_text
    assert "25000" not in raw_text

@pytest.mark.asyncio
@pytest.mark.parametrize("anon_caller_id", [
    None,
    "",
    "   ",
    "operator_bob",
    "random_attacker",
    "anonymous",
])
async def test_anonymous_caller_omission_matrix_blocked(clean_db, anon_caller_id):
    """
    Anonymous caller (authenticated_caller=None) omitting caller_id or providing non-Alice caller_id
    must NEVER access Alice's scope.
    """
    server_anon = create_governed_mcp_server(clean_db, authenticated_caller=None)
    args = {"order_id": "ORD-101", "scope_id": "scope-alice-deep"}
    if anon_caller_id is not None:
        args["caller_id"] = anon_caller_id

    res = await server_anon.call_tool("lookup_order", args)
    assert res.is_error is True, f"Failed to block anon_caller_id={anon_caller_id}"
    body = json.loads(res.content[0].text)
    assert body.get("error") == "CALLER_IDENTITY_MISMATCH"

    # Exfiltration check
    raw_text = res.content[0].text
    assert "Rahim Chowdhury" not in raw_text
    assert "card_visa_4242" not in raw_text

@pytest.mark.asyncio
async def test_audit_event_logged_on_caller_identity_mismatch(clean_db):
    """
    Verify that blocked attempts write proper audit_events records.
    """
    server_bob = create_governed_mcp_server(clean_db, authenticated_caller="operator_bob")
    res = await server_bob.call_tool("lookup_order", {
        "order_id": "ORD-101",
        "scope_id": "scope-alice-deep",
        "caller_id": "operator_alice"
    })
    assert res.is_error is True

    cur = clean_db.cursor()
    cur.execute("SELECT verdict, reason, details FROM audit_events WHERE verdict = 'BLOCKED' ORDER BY rowid DESC LIMIT 1")
    row = cur.fetchone()
    assert row is not None
    assert row[0] == "BLOCKED"
    assert "Scope operator 'operator_alice' does not match authenticated principal 'operator_bob'" in row[1]
    details = json.loads(row[2])
    assert details["order_id"] == "ORD-101"
    assert details["scope_id"] == "scope-alice-deep"
    assert details.get("authenticated_caller") == "operator_bob"

@pytest.mark.asyncio
async def test_authorized_caller_alice_succeeds_with_minimization(clean_db):
    """
    Verify that Alice on authenticated session can access her scope, and data is minimized.
    """
    server_alice = create_governed_mcp_server(clean_db, authenticated_caller="operator_alice")
    res = await server_alice.call_tool("lookup_order", {
        "order_id": "ORD-101",
        "scope_id": "scope-alice-deep"
    })
    assert res.is_error is False
    body = json.loads(res.content[0].text)
    assert body["order_id"] == "ORD-101"
    assert body["status"] == "paid"
    assert body["masked_destination"] == "card...4242"
    assert body["refundable_amount"] == 25000
    assert "customer_name" not in body
    assert "original_destination" not in body
