"""
Challenger 1 Empirical Adversarial Stress Harness for Milestone 2 Closeout.
Target: AetherGuard/backend/app/governance/mcp_server.py (lookup_order)

Probes:
1. Scope bypass when task scopes are empty, missing, or policy is missing.
2. Tool call when excluded from policy.allowed_tools.
3. Order data extraction when audit event logging fails.
4. Caller identity spoofing and anonymous bypass.
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
from mcp.server.mcpserver.exceptions import UnexpectedToolError


@pytest.fixture
def clean_db():
    conn = init_db(":memory:")
    reset_synthetic_data(conn)
    yield conn
    conn.close()


# ==============================================================================
# SECTION 1: TASK SCOPE & POLICY FAIL-CLOSED ADVERSARIAL PROBES
# ==============================================================================

@pytest.mark.asyncio
async def test_probe_missing_policy_table_fails_closed(clean_db):
    """When policy table is deleted, lookup_order must fail closed."""
    clean_db.execute("DROP TABLE policy_config")
    server = create_governed_mcp_server(clean_db, authenticated_caller="op")
    res = await server.call_tool("lookup_order", {"order_id": "ORD-101", "scope_id": "scope-any"})
    assert res.is_error is True, "Must return is_error=True when policy table is missing"
    body = json.loads(res.content[0].text)
    assert body.get("error") == "POLICY_UNAVAILABLE"


@pytest.mark.asyncio
async def test_probe_empty_policy_table_fails_closed(clean_db):
    """When policy_config is empty, lookup_order must fail closed."""
    clean_db.execute("DELETE FROM policy_config")
    server = create_governed_mcp_server(clean_db, authenticated_caller="op")
    res = await server.call_tool("lookup_order", {"order_id": "ORD-101", "scope_id": "scope-any"})
    assert res.is_error is True
    body = json.loads(res.content[0].text)
    assert body.get("error") == "POLICY_UNAVAILABLE"


@pytest.mark.asyncio
@pytest.mark.parametrize("corrupted_payload", [
    "NOT_VALID_JSON{",
    json.dumps({"auto_allow_threshold": -50}),  # Violates _valid threshold > 0
    json.dumps({"hard_ceiling_threshold": 100, "auto_allow_threshold": 500}),  # Ceiling < threshold
    json.dumps({"enforce_task_scope": False}),  # Required control disabled
])
async def test_probe_corrupted_policy_fails_closed(clean_db, corrupted_payload):
    """When policy_config contains corrupt JSON or schema/threshold violations, lookup_order must fail closed."""
    clean_db.execute("UPDATE policy_config SET config = ? WHERE id = 1", (corrupted_payload,))
    server = create_governed_mcp_server(clean_db, authenticated_caller="op")
    res = await server.call_tool("lookup_order", {"order_id": "ORD-101", "scope_id": "scope-any"})
    assert res.is_error is True
    body = json.loads(res.content[0].text)
    assert body.get("error") == "POLICY_UNAVAILABLE"


@pytest.mark.asyncio
async def test_probe_empty_task_scopes_omitted_scope_id_fails_closed(clean_db):
    """When task_scopes table is empty and no scope_id is provided, must fail closed."""
    clean_db.execute("DELETE FROM task_scopes")
    server = create_governed_mcp_server(clean_db, authenticated_caller="op")
    res = await server.call_tool("lookup_order", {"order_id": "ORD-101"})
    assert res.is_error is True
    body = json.loads(res.content[0].text)
    assert body.get("error") == "SCOPE_ID_REQUIRED"


@pytest.mark.asyncio
async def test_probe_empty_task_scopes_arbitrary_scope_id_fails_closed(clean_db):
    """When task_scopes table is empty and arbitrary scope_id is provided, must fail closed."""
    clean_db.execute("DELETE FROM task_scopes")
    server = create_governed_mcp_server(clean_db, authenticated_caller="op")
    res = await server.call_tool("lookup_order", {"order_id": "ORD-101", "scope_id": "nonexistent-scope"})
    assert res.is_error is True
    body = json.loads(res.content[0].text)
    assert body.get("error") == "TASK_SCOPE_EXPIRED"


@pytest.mark.asyncio
async def test_probe_active_scopes_exist_missing_scope_id_fails_closed(clean_db):
    """When active scopes exist in DB but caller omits scope_id, must fail closed."""
    expiry = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    save_task_scope(
        clean_db, "scope-active", "op", "ORD-101", "refund_order",
        5000, "USD", "card_visa_4242", expiry
    )
    server = create_governed_mcp_server(clean_db, authenticated_caller="op")
    res = await server.call_tool("lookup_order", {"order_id": "ORD-101"})
    assert res.is_error is True
    body = json.loads(res.content[0].text)
    assert body.get("error") == "SCOPE_ID_REQUIRED"


@pytest.mark.asyncio
async def test_probe_empty_string_and_whitespace_scope_id_fails_closed(clean_db):
    """Empty string or whitespace-only scope_id must fail closed."""
    server = create_governed_mcp_server(clean_db, authenticated_caller="op")
    # Empty string -> SCOPE_ID_REQUIRED
    res_empty = await server.call_tool("lookup_order", {"order_id": "ORD-101", "scope_id": ""})
    assert res_empty.is_error is True
    assert json.loads(res_empty.content[0].text).get("error") == "SCOPE_ID_REQUIRED"

    # Whitespace only -> TASK_SCOPE_EXPIRED (non-existent)
    res_ws = await server.call_tool("lookup_order", {"order_id": "ORD-101", "scope_id": "   "})
    assert res_ws.is_error is True
    assert json.loads(res_ws.content[0].text).get("error") == "TASK_SCOPE_EXPIRED"


@pytest.mark.asyncio
async def test_probe_expired_task_scope_fails_closed(clean_db):
    """Expired scope must immediately fail closed with TASK_SCOPE_EXPIRED."""
    past_expiry = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    save_task_scope(
        clean_db, "scope-past", "op", "ORD-101", "refund_order",
        5000, "USD", "card_visa_4242", past_expiry
    )
    server = create_governed_mcp_server(clean_db, authenticated_caller="op")
    res = await server.call_tool("lookup_order", {"order_id": "ORD-101", "scope_id": "scope-past"})
    assert res.is_error is True
    assert json.loads(res.content[0].text).get("error") == "TASK_SCOPE_EXPIRED"


@pytest.mark.asyncio
async def test_probe_cross_order_scope_tampering_fails_closed(clean_db):
    """Scope valid for ORD-101 used to query ORD-104 must fail closed."""
    expiry = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    save_task_scope(
        clean_db, "scope-101", "op", "ORD-101", "refund_order",
        5000, "USD", "card_visa_4242", expiry
    )
    server = create_governed_mcp_server(clean_db, authenticated_caller="op")
    res = await server.call_tool("lookup_order", {"order_id": "ORD-104", "scope_id": "scope-101"})
    assert res.is_error is True
    assert json.loads(res.content[0].text).get("error") == "OUTSIDE_TRUSTED_TASK_SCOPE"


@pytest.mark.asyncio
async def test_probe_corrupt_expires_at_fails_closed(clean_db):
    """Malformed expires_at timestamp in database must not leak order data."""
    clean_db.execute(
        "INSERT INTO task_scopes (scope_id, operator_id, order_id, allowed_action, max_amount, allowed_currency, allowed_destination, expires_at) "
        "VALUES ('scope-bad-ts', 'op', 'ORD-101', 'refund_order', 5000, 'USD', 'card_visa_4242', 'NOT_AN_ISO_DATE')"
    )
    server = create_governed_mcp_server(clean_db, authenticated_caller="op")
    # Pydantic validation failure inside TaskScope must be caught and fail closed
    try:
        res = await server.call_tool("lookup_order", {"order_id": "ORD-101", "scope_id": "scope-bad-ts"})
        assert res.is_error is True
    except UnexpectedToolError:
        # MCPServer framework-level error also fails closed (zero data leaked)
        pass


# ==============================================================================
# SECTION 2: TOOL ALLOWLIST (policy.allowed_tools) PROBES
# ==============================================================================

@pytest.mark.asyncio
async def test_probe_tool_excluded_when_allowed_tools_empty(clean_db):
    """When policy.allowed_tools is empty, lookup_order must fail closed."""
    config = json.dumps({
        "version": "1.0.0",
        "allowed_tools": [],
        "auto_allow_threshold": 5000,
        "hard_ceiling_threshold": 100000,
        "enforce_task_scope": True,
        "require_exact_destination_match": True
    })
    clean_db.execute("UPDATE policy_config SET config = ? WHERE id = 1", (config,))
    server = create_governed_mcp_server(clean_db, authenticated_caller="op")
    res = await server.call_tool("lookup_order", {"order_id": "ORD-101", "scope_id": "scope-any"})
    assert res.is_error is True
    assert json.loads(res.content[0].text).get("error") == "TOOL_NOT_ALLOWED"


@pytest.mark.asyncio
async def test_probe_tool_excluded_when_only_other_tools_allowed(clean_db):
    """When allowed_tools contains only refund_order, lookup_order must fail closed."""
    config = json.dumps({
        "version": "1.0.0",
        "allowed_tools": ["refund_order"],
        "auto_allow_threshold": 5000,
        "hard_ceiling_threshold": 100000,
        "enforce_task_scope": True,
        "require_exact_destination_match": True
    })
    clean_db.execute("UPDATE policy_config SET config = ? WHERE id = 1", (config,))
    server = create_governed_mcp_server(clean_db, authenticated_caller="op")
    res = await server.call_tool("lookup_order", {"order_id": "ORD-101", "scope_id": "scope-any"})
    assert res.is_error is True
    assert json.loads(res.content[0].text).get("error") == "TOOL_NOT_ALLOWED"


@pytest.mark.asyncio
async def test_probe_tool_case_and_whitespace_variations_fail_closed(clean_db):
    """
    Exact string matching in policy.allowed_tools must be enforced.
    Non-standard tool names violate policy validation (_valid), causing policy loader to reject
    the policy configuration, failing closed with POLICY_UNAVAILABLE.
    """
    for variation in ["LOOKUP_ORDER", "lookup_order ", " lookup_order", "lookup_order\x00"]:
        config = json.dumps({
            "version": "1.0.0",
            "allowed_tools": [variation],
            "auto_allow_threshold": 5000,
            "hard_ceiling_threshold": 100000,
            "enforce_task_scope": True,
            "require_exact_destination_match": True
        })
        clean_db.execute("UPDATE policy_config SET config = ? WHERE id = 1", (config,))
        server = create_governed_mcp_server(clean_db, authenticated_caller="op")
        res = await server.call_tool("lookup_order", {"order_id": "ORD-101", "scope_id": "scope-any"})
        assert res.is_error is True
        # Both POLICY_UNAVAILABLE and TOOL_NOT_ALLOWED are fail-closed error responses
        err = json.loads(res.content[0].text).get("error")
        assert err in ("POLICY_UNAVAILABLE", "TOOL_NOT_ALLOWED")


# ==============================================================================
# SECTION 3: AUDIT EVENT LOGGING FAILURE & DATA EXFILTRATION PROBES
# ==============================================================================

@pytest.mark.asyncio
async def test_probe_audit_write_failure_fails_closed_zero_leakage(clean_db):
    """
    If writing to audit_events fails (simulated via native SQLite ABORT trigger),
    the tool MUST fail closed with is_error=True and NEVER return order data.
    """
    expiry = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    save_task_scope(
        clean_db, "scope-audit-fail", "op", "ORD-101", "refund_order",
        5000, "USD", "card_visa_4242", expiry
    )
    clean_db.execute("""
        CREATE TRIGGER abort_audit_insert BEFORE INSERT ON audit_events
        WHEN NEW.verdict = 'ALLOWED'
        BEGIN
            SELECT RAISE(ABORT, 'Simulated disk failure or database lock');
        END;
    """)
    server = create_governed_mcp_server(clean_db, authenticated_caller="op")
    res = await server.call_tool("lookup_order", {"order_id": "ORD-101", "scope_id": "scope-audit-fail", "caller_id": "op"})
    assert res.is_error is True, "Must set is_error=True on audit logging failure"
    body = json.loads(res.content[0].text)
    assert body.get("error") == "AUDIT_LOGGING_FAILED"

    # Strict exfiltration oracle: No sensitive order fields leaked in payload
    raw_response = res.content[0].text
    assert "Rahim Chowdhury" not in raw_response
    assert "card_visa_4242" not in raw_response
    assert "25000" not in raw_response
    assert "paid" not in raw_response


@pytest.mark.asyncio
async def test_probe_audit_table_dropped_fails_closed(clean_db):
    """If audit_events table is dropped entirely, lookup_order must fail closed."""
    expiry = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    save_task_scope(
        clean_db, "scope-drop-audit", "op", "ORD-101", "refund_order",
        5000, "USD", "card_visa_4242", expiry
    )
    clean_db.execute("DROP TABLE audit_events")
    server = create_governed_mcp_server(clean_db, authenticated_caller="op")
    res = await server.call_tool("lookup_order", {"order_id": "ORD-101", "scope_id": "scope-drop-audit", "caller_id": "op"})
    assert res.is_error is True
    body = json.loads(res.content[0].text)
    assert body.get("error") == "AUDIT_LOGGING_FAILED"


# ==============================================================================
# SECTION 4: CALLER IDENTITY BINDING & SPOOFING ADVERSARIAL PROBES
# ==============================================================================

@pytest.mark.asyncio
async def test_probe_honest_caller_mismatch_blocked(clean_db):
    """
    Control check: When operator_bob truthfully reports caller_id='operator_bob'
    for a scope bound to operator_alice, he is blocked.
    """
    expiry = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    save_task_scope(
        clean_db, "scope-alice", "operator_alice", "ORD-101", "refund_order",
        5000, "USD", "card_visa_4242", expiry
    )
    server = create_governed_mcp_server(clean_db, authenticated_caller="op")
    res = await server.call_tool("lookup_order", {
        "order_id": "ORD-101",
        "scope_id": "scope-alice",
        "caller_id": "operator_bob"
    })
    assert res.is_error is True
    assert json.loads(res.content[0].text).get("error") == "CALLER_IDENTITY_MISMATCH"


@pytest.mark.asyncio
async def test_probe_authenticated_session_caller_mismatch_blocked(clean_db):
    """
    Control check: When server is initialized with authenticated_caller='operator_bob',
    and caller passes no caller_id, Bob is blocked from Alice's scope.
    """
    expiry = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    save_task_scope(
        clean_db, "scope-alice-2", "operator_alice", "ORD-101", "refund_order",
        5000, "USD", "card_visa_4242", expiry
    )
    server_bob = create_governed_mcp_server(clean_db, authenticated_caller="operator_bob")
    res = await server_bob.call_tool("lookup_order", {
        "order_id": "ORD-101",
        "scope_id": "scope-alice-2"
    })
    assert res.is_error is True
    assert json.loads(res.content[0].text).get("error") == "CALLER_IDENTITY_MISMATCH"


@pytest.mark.asyncio
async def test_probe_adversarial_caller_identity_spoofing_hole(clean_db):
    """
    ADVERSARIAL ATTACK PROBE (REMEDIATED):
    Examines whether client-supplied caller_id can override transport authenticated_caller.
    Scenario:
    - Server session was authenticated as 'operator_bob' (e.g. Bob's connection).
    - Scope belongs strictly to 'operator_alice'.
    - Bob passes caller_id='operator_alice' in the tool arguments.
    In mcp_server.py line 102:
        effective_caller = authenticated_caller or caller_id
    Client cannot override verified transport identity; Bob must be blocked.
    """
    expiry = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    save_task_scope(
        clean_db, "scope-alice-spoof", "operator_alice", "ORD-101", "refund_order",
        5000, "USD", "card_visa_4242", expiry
    )
    # Server transport identity is authenticated as Bob
    server_bob = create_governed_mcp_server(clean_db, authenticated_caller="operator_bob")

    # Bob attempts to spoof Alice by supplying caller_id='operator_alice'
    res_spoof = await server_bob.call_tool("lookup_order", {
        "order_id": "ORD-101",
        "scope_id": "scope-alice-spoof",
        "caller_id": "operator_alice"
    })

    # Fail-closed enforcement check: Spoofing MUST be blocked with CALLER_IDENTITY_MISMATCH
    assert res_spoof.is_error is True, "Must set is_error=True when authenticated_caller != scope operator"
    body = json.loads(res_spoof.content[0].text)
    assert body.get("error") == "CALLER_IDENTITY_MISMATCH", f"Expected CALLER_IDENTITY_MISMATCH, got {body}"
    assert "Rahim Chowdhury" not in res_spoof.content[0].text
    assert "card_visa_4242" not in res_spoof.content[0].text


@pytest.mark.asyncio
async def test_probe_adversarial_anonymous_omission_bypass_hole(clean_db):
    """
    ADVERSARIAL ATTACK PROBE (REMEDIATED):
    Examines whether omitting caller_id entirely against a scope with operator_id bypasses identity check.
    Scenario:
    - Server has authenticated_caller=None (default when launched as standalone or agent).
    - Scope belongs strictly to 'operator_alice'.
    - Caller passes caller_id=None (omitted).
    In mcp_server.py:
        if expected_operator and expected_operator != effective_caller:
    When caller is omitted / None, it MUST fail closed.
    """
    expiry = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    save_task_scope(
        clean_db, "scope-alice-anon", "operator_alice", "ORD-101", "refund_order",
        5000, "USD", "card_visa_4242", expiry
    )
    # Standard server instance without authenticated_caller
    server_anon = create_governed_mcp_server(clean_db)

    # Anonymous caller calls lookup_order without caller_id
    res_anon = await server_anon.call_tool("lookup_order", {
        "order_id": "ORD-101",
        "scope_id": "scope-alice-anon"
    })

    # Fail-closed enforcement check: Anonymous access to scoped task MUST be blocked
    assert res_anon.is_error is True, "Must set is_error=True when caller is omitted for scoped operator"
    body = json.loads(res_anon.content[0].text)
    assert body.get("error") == "CALLER_IDENTITY_MISMATCH", f"Expected CALLER_IDENTITY_MISMATCH, got {body}"
    assert "Rahim Chowdhury" not in res_anon.content[0].text
    assert "card_visa_4242" not in res_anon.content[0].text

