"""
Automated Reproduction & Regression Tests for M2 Remediation.
Proves reproduction of confirmed P0/P1 defects before patching,
and serves as regression guard after patching.
"""
import pytest
import sqlite3
import tempfile
import json
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta

from app.agent.core import SupportAgent
from app.governance.boundary import GovernanceBoundary
from app.sandbox.db import init_db, get_connection
from app.sandbox.service import save_task_scope
from app.governance.mcp_server import create_governed_mcp_server
from app.policy.models import TaskScope


# 1. INV-06 Fail-Closed: LLM timeout/failure must NOT fall back to regex refund extraction
@pytest.mark.asyncio
async def test_llm_timeout_fails_closed_without_regex_fallback(monkeypatch):
    conn = init_db(":memory:")
    agent = SupportAgent(GovernanceBoundary(conn), api_key="dummy_api_key")

    def simulate_timeout(*args, **kwargs):
        raise TimeoutError("Model API timed out after 30s")

    monkeypatch.setattr(agent, "_parse_ticket_llm", simulate_timeout)

    try:
        # Pre-authorize scope for ORD-101
        scope = TaskScope(
            scope_id="scope-timeout-test",
            operator_id="test_op",
            order_id="ORD-101",
            allowed_action="refund_order",
            max_amount=5000,
            allowed_currency="USD",
            allowed_destination="card_visa_4242",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        trace = await agent.process_ticket("ORD-101 refund $40", task_scope=scope)

        # Invariant INV-06: Must FAIL CLOSED.
        # It must NOT have parsed $40 via synthetic regex or executed a refund!
        assert trace["parsed_parameters"]["amount"] == 0, "Failed closed: amount must be 0"
        assert trace["executed"] is False, "Failed closed: refund must NOT execute on LLM failure"
        assert trace["boundary_verdict"] == "BLOCKED"
        assert trace["agent_mode"] in ("invalid_model_output", "model_failure_fail_closed")
    finally:
        conn.close()


# 2. SQLite WAL mode & Concurrency PRAGMAs
def test_sqlite_wal_pragmas_configured():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test_wal.db")
        conn = get_connection(db_path)
        try:
            journal_mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
            busy_timeout = conn.execute("PRAGMA busy_timeout;").fetchone()[0]
            synchronous = conn.execute("PRAGMA synchronous;").fetchone()[0]

            assert journal_mode.lower() == "wal", f"Expected WAL mode, got {journal_mode}"
            assert busy_timeout >= 5000, f"Expected busy_timeout >= 5000, got {busy_timeout}"
            assert synchronous in (1, "NORMAL", "normal"), f"Expected NORMAL synchronous, got {synchronous}"
        finally:
            conn.close()


# 3. Production Rate Limiting Default
def test_rate_limit_active_in_production_by_default(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app, _RATE_LIMITS

    monkeypatch.delenv("PYTEST_CURRENT_TEST_BYPASS_RATELIMIT", raising=False)
    monkeypatch.setenv("AETHERGUARD_RATE_LIMIT_PER_MINUTE", "2")
    _RATE_LIMITS.clear()

    client = TestClient(app, headers={"Authorization": "Bearer test-only-operator-token"})

    # Send 2 valid/rate-counted requests
    for i in range(2):
        res = client.post("/api/agent/process-ticket", json={"ticket_text": f"Refund {i}", "idempotency_key": f"prod-k-{i}"})
        assert res.status_code != 429

    # 3rd request MUST be rate limited (429) when default is production-safe
    res3 = client.post("/api/agent/process-ticket", json={"ticket_text": "Refund 3", "idempotency_key": "prod-k-3"})
    assert res3.status_code == 429, f"Rate limit not enforced in production default! Got {res3.status_code}"
    assert "Rate limit exceeded" in res3.json()["detail"]


# 4. MCP lookup_order audit logging & is_error=True on tool errors
@pytest.mark.asyncio
async def test_mcp_lookup_order_audited_and_error_flags():
    conn = init_db(":memory:")
    server = create_governed_mcp_server(conn, authenticated_caller="test_op")

    try:
        # A. lookup_order must write to audit_events
        expiry = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        save_task_scope(
            conn=conn, scope_id="scope-audit-check", operator_id="test_op", order_id="ORD-101",
            allowed_action="refund_order", max_amount=5000, allowed_currency="USD",
            allowed_destination="card_visa_4242", expires_at=expiry
        )
        audit_count_before = conn.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
        res = await server.call_tool("lookup_order", {"order_id": "ORD-101", "scope_id": "scope-audit-check", "caller_id": "test_op"})
        assert not res.is_error
        audit_count_after = conn.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
        assert audit_count_after == audit_count_before + 1, "lookup_order did not write to audit_events"

        # B. lookup_order on non-existent order must return is_error=True
        save_task_scope(
            conn=conn, scope_id="scope-missing-check", operator_id="test_op", order_id="ORD-NONEXISTENT",
            allowed_action="refund_order", max_amount=5000, allowed_currency="USD",
            allowed_destination="card_visa_4242", expires_at=expiry
        )
        missing_res = await server.call_tool("lookup_order", {"order_id": "ORD-NONEXISTENT", "scope_id": "scope-missing-check", "caller_id": "test_op"})
        assert missing_res.is_error is True, "Missing order lookup did not set is_error=True"

        # C. refund_order with missing idempotency key must return is_error=True
        bad_refund = await server.call_tool("refund_order", {
            "order_id": "ORD-101",
            "amount": 1000,
            "currency": "USD",
            "destination": "card_visa_4242",
            "reason": "test",
            "idempotency_key": ""
        })
        assert bad_refund.is_error is True, "Missing idempotency key did not set is_error=True"
        assert json.loads(bad_refund.content[0].text)["error"] == "IDEMPOTENCY_KEY_REQUIRED"
    finally:
        conn.close()


# 5. Bengali Numerals in Order IDs
def test_bengali_numerals_normalized_in_order_id():
    conn = init_db(":memory:")
    agent = SupportAgent(GovernanceBoundary(conn))
    try:
        parsed = agent._parse_ticket_synthetic("আমার অর্ডার ORD-১০৩ এর রিফান্ড ৫০ টাকা দিন")
        assert parsed["order_id"] == "ORD-103", f"Expected ORD-103, got {parsed['order_id']}"
        assert parsed["amount"] == 5000, f"Expected 5000, got {parsed['amount']}"
        assert parsed["currency"] == "BDT"
    finally:
        conn.close()


# 6. Customer Complaint Negation Heuristic
def test_complaint_phrasing_not_suppressed_by_negation_regex():
    conn = init_db(":memory:")
    agent = SupportAgent(GovernanceBoundary(conn))
    try:
        # "not happy" complaint should NOT zero the amount
        parsed1 = agent._parse_ticket_synthetic("I was not happy with order ORD-101, please refund $40")
        assert parsed1["amount"] == 4000, f"Amount was incorrectly zeroed on complaint: {parsed1['amount']}"
        assert parsed1["order_id"] == "ORD-101"

        # "not working" complaint should NOT zero the amount
        parsed2 = agent._parse_ticket_synthetic("Item was not working for ORD-101, please refund $40 to card_visa_4242")
        assert parsed2["amount"] == 4000, f"Amount was incorrectly zeroed on complaint: {parsed2['amount']}"

        # True negation MUST still be zeroed
        parsed_neg = agent._parse_ticket_synthetic("Please do not refund $40 for order ORD-101")
        assert parsed_neg["amount"] == 0, f"True negation was not zeroed: {parsed_neg['amount']}"
    finally:
        conn.close()


# 7. Content-Length Bounds and Malformed Handling
def test_content_length_bounds_and_malformed():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app, headers={"Authorization": "Bearer test-only-operator-token"})

    # Negative content length must return 413
    res_neg = client.post("/api/sandbox/orders", content=b"{}", headers={"Content-Length": "-5"})
    assert res_neg.status_code == 413
    assert "Payload Too Large" in res_neg.json()["detail"]

    # Malformed content length must return 400
    res_mal = client.post("/api/sandbox/orders", content=b"{}", headers={"Content-Length": "not_an_int"})
    assert res_mal.status_code == 400
    assert "Malformed Content-Length" in res_mal.json()["detail"]


# 8. Trusted Proxy IP Resolution
def test_trusted_proxy_ip_resolution(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app, _RATE_LIMITS

    monkeypatch.setenv("PYTEST_CURRENT_TEST_BYPASS_RATELIMIT", "0")
    monkeypatch.setenv("AETHERGUARD_RATE_LIMIT_PER_MINUTE", "2")
    monkeypatch.setenv("AETHERGUARD_TRUSTED_PROXIES", "127.0.0.1,::1,testclient")
    _RATE_LIMITS.clear()

    client = TestClient(app, headers={"Authorization": "Bearer test-only-operator-token"})

    # Requests with X-Forwarded-For through trusted client should be partitioned by forwarded IP
    res1 = client.post(
        "/api/agent/process-ticket",
        json={"ticket_text": "Refund 1", "idempotency_key": "proxy-k-1"},
        headers={"x-forwarded-for": "203.0.113.195, 10.0.0.1"}
    )
    assert res1.status_code != 429

    res2 = client.post(
        "/api/agent/process-ticket",
        json={"ticket_text": "Refund 2", "idempotency_key": "proxy-k-2"},
        headers={"x-forwarded-for": "203.0.113.195, 10.0.0.1"}
    )
    assert res2.status_code != 429

    # 3rd request from same forwarded IP must be 429
    res3 = client.post(
        "/api/agent/process-ticket",
        json={"ticket_text": "Refund 3", "idempotency_key": "proxy-k-3"},
        headers={"x-forwarded-for": "203.0.113.195, 10.0.0.1"}
    )
    assert res3.status_code == 429

    # But request from a DIFFERENT forwarded IP should succeed (not globally blocked!)
    res_diff = client.post(
        "/api/agent/process-ticket",
        json={"ticket_text": "Refund diff", "idempotency_key": "proxy-k-diff"},
        headers={"x-forwarded-for": "198.51.100.42"}
    )
    assert res_diff.status_code != 429

    # When client socket is untrusted, spoofed X-Forwarded-For must be ignored
    monkeypatch.setenv("AETHERGUARD_TRUSTED_PROXIES", "127.0.0.1,::1")
    _RATE_LIMITS.clear()
    res_untrusted = client.post(
        "/api/agent/process-ticket",
        json={"ticket_text": "Refund untrusted", "idempotency_key": "proxy-k-untrusted"},
        headers={"x-forwarded-for": "spoofed.ip.address"}
    )
    assert res_untrusted.status_code != 429
    assert "testclient" in _RATE_LIMITS  # Resolved to immediate socket, spoofed header ignored


# 9. Genuinely Bounded Streaming Request Size & Early Abort Verification
@pytest.mark.asyncio
async def test_streaming_request_size_aborts_early_without_full_buffering():
    """
    Verifies that oversized streaming bodies are rejected mid-stream with HTTP 413
    without consuming or buffering subsequent chunks into memory.
    """
    import httpx
    from app.main import app, MAX_REQUEST_SIZE

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        chunks_yielded = 0

        async def oversized_stream():
            nonlocal chunks_yielded
            # Yield 32 chunks of 64KB (2MB total), exceeding 1MB limit on chunk 17
            for i in range(32):
                chunks_yielded += 1
                yield b"X" * 65536

        res = await ac.post(
            "/api/governance/evaluate",
            content=oversized_stream(),
            headers={
                "Authorization": "Bearer test-only-operator-token",
                "Transfer-Encoding": "chunked",
            }
        )

        assert res.status_code == 413
        assert "Payload Too Large" in res.json()["detail"]
        # Invariant: Streaming enforcement must abort early; chunk count must be <= 18
        assert chunks_yielded <= 18, f"Stream was not aborted early! Consumed {chunks_yielded} chunks."


@pytest.mark.asyncio
async def test_mid_stream_exceedance_with_undersized_content_length_blocked():
    """
    Verifies that a deceptive request with a small Content-Length header that
    attempts to stream an oversized payload is caught and blocked with HTTP 413.
    """
    import httpx
    from app.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        async def lying_stream():
            # Declares 50 bytes, but actually streams 1.2 MB
            for _ in range(20):
                yield b"A" * 65536

        res = await ac.post(
            "/api/governance/evaluate",
            content=lying_stream(),
            headers={
                "Authorization": "Bearer test-only-operator-token",
                "Content-Length": "50",
            }
        )
        assert res.status_code == 413
        assert "Payload Too Large" in res.json()["detail"]


