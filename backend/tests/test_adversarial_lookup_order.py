"""
Adversarial Stress Testing & Security Challenge Suite for MCP lookup_order.
Target: backend/app/governance/mcp_server.py: lookup_order

Probes:
1. BOLA / Cross-Scope Access (single and multi-scope)
2. Expired Scopes (seconds, hours, days, timezones)
3. Malformed / Non-Existent Scope IDs
4. SQL Injection Payloads (order_id and scope_id)
5. Audit Log Integrity, non-repudiation, and is_error=True enforcement
6. Concurrency Stress Test under heavy simultaneous queries
"""
import pytest
import json
import sqlite3
import asyncio
from datetime import datetime, timezone, timedelta

from app.sandbox.db import init_db
from app.sandbox.service import reset_synthetic_data, save_task_scope, get_order
from app.governance.mcp_server import create_governed_mcp_server


@pytest.fixture
def mcp_fixture():
    conn = init_db(":memory:")
    reset_synthetic_data(conn)
    server = create_governed_mcp_server(conn, authenticated_caller="op")
    yield conn, server
    conn.close()


# ==============================================================================
# 1. BOLA / Cross-Scope Probing
# ==============================================================================

@pytest.mark.asyncio
async def test_bola_unauthorized_high_value_order(mcp_fixture):
    """
    Operator grants scope strictly for ORD-101 ($250).
    Attacker probes high-value enterprise order ORD-104 ($5,000).
    Must fail with OUTSIDE_TRUSTED_TASK_SCOPE, is_error=True, and log BLOCKED.
    """
    conn, server = mcp_fixture
    expiry = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    save_task_scope(
        conn=conn,
        scope_id="scope-user-101",
        operator_id="operator_dipto",
        order_id="ORD-101",
        allowed_action="refund_order",
        max_amount=5000,
        allowed_currency="USD",
        allowed_destination="card_visa_4242",
        expires_at=expiry
    )

    res = await server.call_tool("lookup_order", {"order_id": "ORD-104", "scope_id": "scope-user-101"})
    assert res.is_error is True, "Cross-scope lookup must set is_error=True"
    body = json.loads(res.content[0].text)
    assert body.get("error") == "OUTSIDE_TRUSTED_TASK_SCOPE"
    assert "Enterprise Client X" not in res.content[0].text
    assert "wire_swift_chase" not in res.content[0].text

    # Audit verification
    row = conn.execute(
        "SELECT verdict, reason, details FROM audit_events WHERE tool = 'lookup_order' ORDER BY rowid DESC LIMIT 1"
    ).fetchone()
    assert row["verdict"] == "BLOCKED"
    assert "OUTSIDE_TRUSTED_TASK_SCOPE" in row["reason"]
    details = json.loads(row["details"])
    assert details["order_id"] == "ORD-104"
    assert details["scope_id"] == "scope-user-101"


@pytest.mark.asyncio
async def test_bola_multi_tenant_multi_scope_isolation(mcp_fixture):
    """
    Test matrix across multiple active scopes:
    scope-A -> ORD-101
    scope-B -> ORD-102
    scope-C -> ORD-104
    Every cross-pair must be BLOCKED; only exact match must be ALLOWED.
    """
    conn, server = mcp_fixture
    expiry = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    scopes = {
        "scope-A": "ORD-101",
        "scope-B": "ORD-102",
        "scope-C": "ORD-104",
    }
    for sid, oid in scopes.items():
        save_task_scope(
            conn=conn,
            scope_id=sid,
            operator_id="op",
            order_id=oid,
            allowed_action="refund_order",
            max_amount=10000,
            allowed_currency="USD",
            allowed_destination="card_visa_4242",
            expires_at=expiry
        )

    for sid, authorized_oid in scopes.items():
        for test_oid in ["ORD-101", "ORD-102", "ORD-104"]:
            res = await server.call_tool("lookup_order", {"order_id": test_oid, "scope_id": sid, "caller_id": "op"})
            if test_oid == authorized_oid:
                assert res.is_error is False, f"Expected {sid} to access {test_oid}"
                data = json.loads(res.content[0].text)
                assert data["order_id"] == authorized_oid
            else:
                assert res.is_error is True, f"Expected {sid} to be BLOCKED from {test_oid}"
                err = json.loads(res.content[0].text)
                assert err.get("error") == "OUTSIDE_TRUSTED_TASK_SCOPE"


@pytest.mark.asyncio
@pytest.mark.parametrize("tampered_id", [
    "ord-101",         # lowercase
    "ORD-101 ",        # trailing space
    " ORD-101",        # leading space
    "ORD-101\n",       # newline
    "ORD-101\x00",     # null byte
    "ORD-101\t",       # tab
])
async def test_bola_order_id_string_variations_blocked(mcp_fixture, tampered_id):
    """
    Ensure exact string equality is enforced; whitespace, casing or null byte
    modifications cannot bypass scope boundary.
    """
    conn, server = mcp_fixture
    expiry = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    save_task_scope(
        conn=conn,
        scope_id="scope-exact",
        operator_id="op",
        order_id="ORD-101",
        allowed_action="refund_order",
        max_amount=5000,
        allowed_currency="USD",
        allowed_destination="card_visa_4242",
        expires_at=expiry
    )

    res = await server.call_tool("lookup_order", {"order_id": tampered_id, "scope_id": "scope-exact"})
    assert res.is_error is True
    body = json.loads(res.content[0].text)
    assert body.get("error") == "OUTSIDE_TRUSTED_TASK_SCOPE"


# ==============================================================================
# 2. Expired Scope Probing
# ==============================================================================

@pytest.mark.asyncio
@pytest.mark.parametrize("delta,label", [
    (timedelta(seconds=1), "expired_1s_ago"),
    (timedelta(minutes=5), "expired_5m_ago"),
    (timedelta(hours=24), "expired_1d_ago"),
    (timedelta(days=365), "expired_1y_ago"),
])
async def test_expired_scope_rejection_at_various_intervals(mcp_fixture, delta, label):
    """
    Scopes past their expiration window must be immediately rejected with TASK_SCOPE_EXPIRED.
    """
    conn, server = mcp_fixture
    past_expiry = (datetime.now(timezone.utc) - delta).isoformat()
    save_task_scope(
        conn=conn,
        scope_id=f"scope-{label}",
        operator_id="op",
        order_id="ORD-101",
        allowed_action="refund_order",
        max_amount=5000,
        allowed_currency="USD",
        allowed_destination="card_visa_4242",
        expires_at=past_expiry
    )

    res = await server.call_tool("lookup_order", {"order_id": "ORD-101", "scope_id": f"scope-{label}"})
    assert res.is_error is True
    body = json.loads(res.content[0].text)
    assert body.get("error") == "TASK_SCOPE_EXPIRED"

    row = conn.execute(
        "SELECT verdict, reason FROM audit_events WHERE tool = 'lookup_order' ORDER BY rowid DESC LIMIT 1"
    ).fetchone()
    assert row["verdict"] == "BLOCKED"
    assert row["reason"] == "TASK_SCOPE_EXPIRED"


@pytest.mark.asyncio
async def test_scope_timezone_offset_handling(mcp_fixture):
    """
    Verify timezone offsets (e.g. UTC+6 or UTC-5) are correctly evaluated against UTC now.
    """
    conn, server = mcp_fixture
    # Expired 1 hour ago in UTC+6
    tz_plus6 = timezone(timedelta(hours=6))
    past_in_tz = (datetime.now(tz_plus6) - timedelta(hours=1)).isoformat()
    save_task_scope(
        conn=conn,
        scope_id="scope-tz-expired",
        operator_id="op",
        order_id="ORD-101",
        allowed_action="refund_order",
        max_amount=5000,
        allowed_currency="USD",
        allowed_destination="card_visa_4242",
        expires_at=past_in_tz
    )
    res = await server.call_tool("lookup_order", {"order_id": "ORD-101", "scope_id": "scope-tz-expired"})
    assert res.is_error is True
    assert json.loads(res.content[0].text)["error"] == "TASK_SCOPE_EXPIRED"

    # Future 1 hour in UTC-5
    tz_minus5 = timezone(timedelta(hours=-5))
    future_in_tz = (datetime.now(tz_minus5) + timedelta(hours=1)).isoformat()
    save_task_scope(
        conn=conn,
        scope_id="scope-tz-future",
        operator_id="op",
        order_id="ORD-101",
        allowed_action="refund_order",
        max_amount=5000,
        allowed_currency="USD",
        allowed_destination="card_visa_4242",
        expires_at=future_in_tz
    )
    res_future = await server.call_tool("lookup_order", {"order_id": "ORD-101", "scope_id": "scope-tz-future", "caller_id": "op"})
    assert res_future.is_error is False
    assert json.loads(res_future.content[0].text)["order_id"] == "ORD-101"


# ==============================================================================
# 3. Malformed / Non-Existent Scope IDs
# ==============================================================================

@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_scope,expected_err", [
    (None, "SCOPE_ID_REQUIRED"),
    ("", "SCOPE_ID_REQUIRED"),
    ("   ", "TASK_SCOPE_EXPIRED"),
    ("scope_does_not_exist_at_all", "TASK_SCOPE_EXPIRED"),
    ("../../../etc/shadow", "TASK_SCOPE_EXPIRED"),
    ("<script>alert(1)</script>", "TASK_SCOPE_EXPIRED"),
    ("!@#$%^&*()_+", "TASK_SCOPE_EXPIRED"),
    ("x" * 5000, "TASK_SCOPE_EXPIRED"),
])
async def test_malformed_and_missing_scope_ids(mcp_fixture, invalid_scope, expected_err):
    """
    When active scopes exist in the database, all malformed, whitespace, missing,
    or non-existent scope IDs must fail closed with is_error=True and be logged as BLOCKED.
    """
    conn, server = mcp_fixture
    expiry = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    save_task_scope(
        conn=conn,
        scope_id="scope-anchor",
        operator_id="op",
        order_id="ORD-101",
        allowed_action="refund_order",
        max_amount=5000,
        allowed_currency="USD",
        allowed_destination="card_visa_4242",
        expires_at=expiry
    )

    args = {"order_id": "ORD-101"}
    if invalid_scope is not None:
        args["scope_id"] = invalid_scope

    res = await server.call_tool("lookup_order", args)
    assert res.is_error is True
    err = json.loads(res.content[0].text)
    assert err.get("error") == expected_err

    audit = conn.execute(
        "SELECT verdict, reason FROM audit_events WHERE tool = 'lookup_order' ORDER BY rowid DESC LIMIT 1"
    ).fetchone()
    assert audit["verdict"] == "BLOCKED"


# ==============================================================================
# 4. SQL Injection Payloads
# ==============================================================================

SQLI_PAYLOADS = [
    "' OR '1'='1",
    "'; DROP TABLE orders; --",
    "ORD-101' UNION SELECT id, customer_name, currency, paid_amount, refundable_amount, original_destination, status FROM orders --",
    "1' ORDER BY 1--",
    "admin'--",
    "' OR ''='",
    "ORD-101\"; DROP TABLE task_scopes; --",
    "ORD-101' AND 1=0 UNION ALL SELECT * FROM orders--",
    "1; ATTACH DATABASE ':memory:' AS evil;",
    "ORD-101' AND (SELECT count(*) FROM sqlite_master)>0 --",
]

@pytest.mark.asyncio
@pytest.mark.parametrize("payload", SQLI_PAYLOADS)
async def test_sqli_in_order_id_blocked_and_safe(mcp_fixture, payload):
    """
    Test SQL injection payloads in order_id.
    Must never execute raw SQL, must not drop tables, and must fail safely with is_error=True.
    """
    conn, server = mcp_fixture
    expiry = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    save_task_scope(
        conn=conn,
        scope_id="scope-sqli-test",
        operator_id="op",
        order_id="ORD-101",
        allowed_action="refund_order",
        max_amount=5000,
        allowed_currency="USD",
        allowed_destination="card_visa_4242",
        expires_at=expiry
    )

    res = await server.call_tool("lookup_order", {"order_id": payload, "scope_id": "scope-sqli-test"})
    assert res.is_error is True

    # Confirm tables are intact
    assert conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 4
    assert conn.execute("SELECT COUNT(*) FROM task_scopes").fetchone()[0] >= 1

    # Audit row exists and recorded the attack attempt
    audit = conn.execute(
        "SELECT verdict, reason, details FROM audit_events WHERE tool = 'lookup_order' ORDER BY rowid DESC LIMIT 1"
    ).fetchone()
    assert audit["verdict"] == "BLOCKED"
    details = json.loads(audit["details"])
    assert details["order_id"] == payload


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", SQLI_PAYLOADS)
async def test_sqli_in_scope_id_blocked_and_safe(mcp_fixture, payload):
    """
    Test SQL injection payloads in scope_id.
    Must never execute raw SQL, must not drop tables, and must return TASK_SCOPE_EXPIRED with is_error=True.
    """
    conn, server = mcp_fixture
    expiry = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    save_task_scope(
        conn=conn,
        scope_id="scope-valid",
        operator_id="op",
        order_id="ORD-101",
        allowed_action="refund_order",
        max_amount=5000,
        allowed_currency="USD",
        allowed_destination="card_visa_4242",
        expires_at=expiry
    )

    res = await server.call_tool("lookup_order", {"order_id": "ORD-101", "scope_id": payload})
    assert res.is_error is True
    assert json.loads(res.content[0].text)["error"] == "TASK_SCOPE_EXPIRED"

    # Confirm tables intact
    assert conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 4
    assert conn.execute("SELECT COUNT(*) FROM task_scopes").fetchone()[0] >= 1

    audit = conn.execute(
        "SELECT verdict, reason, details FROM audit_events WHERE tool = 'lookup_order' ORDER BY rowid DESC LIMIT 1"
    ).fetchone()
    assert audit["verdict"] == "BLOCKED"
    assert audit["reason"] == "TASK_SCOPE_EXPIRED"


# ==============================================================================
# 5. Non-Existent Order With Valid Scope
# ==============================================================================

@pytest.mark.asyncio
async def test_nonexistent_order_with_matching_scope(mcp_fixture):
    """
    If a scope is granted for ORD-999 (which does not exist in the orders table),
    the tool must pass scope validation but fail cleanly on get_order with is_error=True
    and log BLOCKED with reason 'Order ORD-999 not found in sandbox'.
    """
    conn, server = mcp_fixture
    expiry = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    save_task_scope(
        conn=conn,
        scope_id="scope-ord-999",
        operator_id="op",
        order_id="ORD-999",
        allowed_action="refund_order",
        max_amount=5000,
        allowed_currency="USD",
        allowed_destination="card_visa_4242",
        expires_at=expiry
    )

    res = await server.call_tool("lookup_order", {"order_id": "ORD-999", "scope_id": "scope-ord-999", "caller_id": "op"})
    assert res.is_error is True
    body = json.loads(res.content[0].text)
    assert "not found in sandbox" in body["error"]

    audit = conn.execute(
        "SELECT verdict, reason FROM audit_events WHERE tool = 'lookup_order' ORDER BY rowid DESC LIMIT 1"
    ).fetchone()
    assert audit["verdict"] == "BLOCKED"
    assert "Order ORD-999 not found in sandbox" in audit["reason"]


# ==============================================================================
# 6. Concurrency Stress Test
# ==============================================================================

@pytest.mark.asyncio
async def test_concurrent_lookup_stress_harness(mcp_fixture):
    """
    Concurrently fire 30 lookup_order calls with mixed scenarios:
    - 10 valid lookups (ORD-101 with scope-101) -> must be ALLOWED
    - 10 BOLA cross-scope lookups (ORD-104 with scope-101) -> must be BLOCKED
    - 10 expired scope lookups (ORD-101 with scope-expired) -> must be BLOCKED

    Assert:
    - Zero deadlocks, zero uncaught exceptions
    - Exact verdict counts match (10 ALLOWED, 20 BLOCKED)
    - Audit log has exactly 30 new entries with matching counts
    """
    conn, server = mcp_fixture
    future_expiry = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    past_expiry = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

    save_task_scope(
        conn=conn,
        scope_id="scope-concurrent-valid",
        operator_id="op",
        order_id="ORD-101",
        allowed_action="refund_order",
        max_amount=5000,
        allowed_currency="USD",
        allowed_destination="card_visa_4242",
        expires_at=future_expiry
    )
    save_task_scope(
        conn=conn,
        scope_id="scope-concurrent-expired",
        operator_id="op",
        order_id="ORD-101",
        allowed_action="refund_order",
        max_amount=5000,
        allowed_currency="USD",
        allowed_destination="card_visa_4242",
        expires_at=past_expiry
    )

    audit_count_before = conn.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]

    async def run_valid():
        return await server.call_tool("lookup_order", {"order_id": "ORD-101", "scope_id": "scope-concurrent-valid", "caller_id": "op"})

    async def run_bola():
        return await server.call_tool("lookup_order", {"order_id": "ORD-104", "scope_id": "scope-concurrent-valid", "caller_id": "op"})

    async def run_expired():
        return await server.call_tool("lookup_order", {"order_id": "ORD-101", "scope_id": "scope-concurrent-expired", "caller_id": "op"})

    tasks = [run_valid() for _ in range(10)] + [run_bola() for _ in range(10)] + [run_expired() for _ in range(10)]
    import random
    random.shuffle(tasks)

    results = await asyncio.gather(*tasks)

    allowed_count = sum(1 for r in results if not r.is_error)
    blocked_count = sum(1 for r in results if r.is_error)

    assert allowed_count == 10, f"Expected 10 allowed, got {allowed_count}"
    assert blocked_count == 20, f"Expected 20 blocked, got {blocked_count}"

    audit_count_after = conn.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
    assert audit_count_after == audit_count_before + 30, f"Expected 30 audit rows, got {audit_count_after - audit_count_before}"

    db_allowed = conn.execute("SELECT COUNT(*) FROM audit_events WHERE verdict = 'ALLOWED'").fetchone()[0]
    db_blocked = conn.execute("SELECT COUNT(*) FROM audit_events WHERE verdict = 'BLOCKED'").fetchone()[0]
    assert db_allowed == 10
    assert db_blocked == 20


# ==============================================================================
# 7. Real Stdio Subprocess Transport Verification
# ==============================================================================

import sys
import os
import tempfile
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.session import ClientSession

@pytest.mark.asyncio
async def test_stdio_lookup_order_bola_blocked_over_transport():
    """
    Verify over real MCP stdio subprocess transport that lookup_order enforces
    task scope and returns is_error=True when attempting BOLA.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    try:
        conn = init_db(db_path)
        reset_synthetic_data(conn)
        expiry = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        save_task_scope(
            conn=conn,
            scope_id="scope-stdio-bola",
            operator_id="test_op",
            order_id="ORD-101",
            allowed_action="refund_order",
            max_amount=5000,
            allowed_currency="USD",
            allowed_destination="card_visa_4242",
            expires_at=expiry
        )
        conn.close()

        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "app.mcp_entrypoint"],
            env={**os.environ, "AETHERGUARD_DB_PATH": db_path, "AETHERGUARD_AUTHENTICATED_OPERATOR": "test_op"}
        )

        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # Attempt BOLA lookup on ORD-104 over stdio
                res = await session.call_tool("lookup_order", {"order_id": "ORD-104", "scope_id": "scope-stdio-bola"})
                assert res.is_error is True
                body = json.loads(res.content[0].text)
                assert body.get("error") == "OUTSIDE_TRUSTED_TASK_SCOPE"

                # Attempt legitimate lookup on ORD-101 over stdio
                valid_res = await session.call_tool("lookup_order", {"order_id": "ORD-101", "scope_id": "scope-stdio-bola", "caller_id": "test_op"})
                assert valid_res.is_error is False
                valid_body = json.loads(valid_res.content[0].text)
                assert valid_body["order_id"] == "ORD-101"
                assert valid_body["paid_amount"] == 25000

        # Check audit trail in physical SQLite file
        conn = init_db(db_path)
        events = conn.execute("SELECT verdict, reason FROM audit_events WHERE tool = 'lookup_order' ORDER BY rowid ASC").fetchall()
        assert len(events) >= 2
        assert events[-2]["verdict"] == "BLOCKED"
        assert "OUTSIDE_TRUSTED_TASK_SCOPE" in events[-2]["reason"]
        assert events[-1]["verdict"] == "ALLOWED"
        assert events[-1]["reason"] == "Order lookup succeeded"
        conn.close()
    finally:
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except OSError:
                pass


# ==============================================================================
# 8. Extreme Buffer Sizes
# ==============================================================================

@pytest.mark.asyncio
async def test_extreme_buffer_sizes_fail_safely(mcp_fixture):
    """
    Passing 50,000-char string payloads in order_id or scope_id must not crash the process.
    """
    conn, server = mcp_fixture
    huge_str = "A" * 50000

    expiry = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    save_task_scope(
        conn=conn,
        scope_id="scope-huge-test",
        operator_id="test_op",
        order_id="ORD-101",
        allowed_action="refund_order",
        max_amount=5000,
        allowed_currency="USD",
        allowed_destination="card_visa_4242",
        expires_at=expiry
    )

    # Huge order_id
    res1 = await server.call_tool("lookup_order", {"order_id": huge_str, "scope_id": "scope-huge-test"})
    assert res1.is_error is True

    # Huge scope_id
    res2 = await server.call_tool("lookup_order", {"order_id": "ORD-101", "scope_id": huge_str})
    assert res2.is_error is True


# ==============================================================================
# 9. Acceptance Criteria Hardening Regressions (R2)
# ==============================================================================

@pytest.mark.asyncio
async def test_lookup_order_fails_closed_when_policy_missing(mcp_fixture):
    """Q1: Missing policy configuration must fail closed with is_error=True."""
    conn, server = mcp_fixture
    # Delete policy config
    conn.execute("DELETE FROM policy_config")
    res = await server.call_tool("lookup_order", {"order_id": "ORD-101", "scope_id": "any-scope"})
    assert res.is_error is True
    assert json.loads(res.content[0].text)["error"] == "POLICY_UNAVAILABLE"


@pytest.mark.asyncio
async def test_lookup_order_fails_closed_when_task_scopes_empty(mcp_fixture):
    """Q1: Unscoped lookup must fail closed even when task_scopes table is completely empty."""
    conn, server = mcp_fixture
    # Ensure task_scopes is completely empty
    conn.execute("DELETE FROM task_scopes")
    res = await server.call_tool("lookup_order", {"order_id": "ORD-101"})
    assert res.is_error is True
    assert json.loads(res.content[0].text)["error"] == "SCOPE_ID_REQUIRED"


@pytest.mark.asyncio
async def test_lookup_order_fails_closed_when_tool_not_allowed(mcp_fixture):
    """Q2: If lookup_order is excluded from policy.allowed_tools, it must fail closed."""
    conn, server = mcp_fixture
    # Update policy to disallow lookup_order
    restricted_policy = json.dumps({
        "version": "1.0.0",
        "allowed_tools": ["refund_order"],
        "auto_allow_threshold": 5000,
        "hard_ceiling_threshold": 100000,
        "enforce_task_scope": True,
        "require_exact_destination_match": True
    })
    conn.execute("UPDATE policy_config SET config = ? WHERE id = 1", (restricted_policy,))
    res = await server.call_tool("lookup_order", {"order_id": "ORD-101", "scope_id": "scope-test"})
    assert res.is_error is True
    assert json.loads(res.content[0].text)["error"] == "TOOL_NOT_ALLOWED"


@pytest.mark.asyncio
async def test_lookup_order_fails_closed_on_audit_failure(mcp_fixture):
    """Q3: If audit-event insertion fails, tool must fail closed and NOT return sensitive data."""
    conn, server = mcp_fixture
    expiry = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    save_task_scope(
        conn=conn, scope_id="scope-audit-fail", operator_id="op", order_id="ORD-101",
        allowed_action="refund_order", max_amount=5000, allowed_currency="USD",
        allowed_destination="card_visa_4242", expires_at=expiry
    )
    # Simulate DB write failure on audit_events using native SQLite trigger
    conn.execute("""
        CREATE TRIGGER fail_allowed_audit BEFORE INSERT ON audit_events
        WHEN NEW.verdict = 'ALLOWED'
        BEGIN
            SELECT RAISE(ABORT, 'disk I/O error or database locked');
        END;
    """)
    res = await server.call_tool("lookup_order", {"order_id": "ORD-101", "scope_id": "scope-audit-fail", "caller_id": "op"})
    assert res.is_error is True
    body = json.loads(res.content[0].text)
    assert body["error"] == "AUDIT_LOGGING_FAILED"
    assert "Rahim Chowdhury" not in res.content[0].text
    assert "card_visa_4242" not in res.content[0].text


@pytest.mark.asyncio
async def test_lookup_order_caller_identity_binding(mcp_fixture):
    """Q4: Scope ID bound to operator_A cannot be queried by operator_B."""
    conn, server = mcp_fixture
    expiry = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    save_task_scope(
        conn=conn, scope_id="scope-bound-op", operator_id="operator_alice", order_id="ORD-101",
        allowed_action="refund_order", max_amount=5000, allowed_currency="USD",
        allowed_destination="card_visa_4242", expires_at=expiry
    )
    # Legitimate caller on Alice's authenticated session
    server_alice = create_governed_mcp_server(conn, authenticated_caller="operator_alice")
    res_valid = await server_alice.call_tool("lookup_order", {
        "order_id": "ORD-101", "scope_id": "scope-bound-op"
    })
    assert res_valid.is_error is False

    # Impersonating caller: Bob authenticated session attempting to query Alice's scope
    server_bob = create_governed_mcp_server(conn, authenticated_caller="operator_bob")
    res_spoof = await server_bob.call_tool("lookup_order", {
        "order_id": "ORD-101", "scope_id": "scope-bound-op", "caller_id": "operator_alice"
    })
    assert res_spoof.is_error is True
    assert json.loads(res_spoof.content[0].text)["error"] == "CALLER_IDENTITY_MISMATCH"

    # Anonymous caller: unauthenticated session attempting to query Alice's scope
    server_anon = create_governed_mcp_server(conn, authenticated_caller=None)
    res_anon = await server_anon.call_tool("lookup_order", {
        "order_id": "ORD-101", "scope_id": "scope-bound-op", "caller_id": "operator_alice"
    })
    assert res_anon.is_error is True
    assert json.loads(res_anon.content[0].text)["error"] == "CALLER_IDENTITY_MISMATCH"

