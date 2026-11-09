"""
Challenger 2 Empirical Adversarial Stress Harness for Milestone 2.
Tests:
1. Request size bounds (negative, zero, 2MB, exact 1MB boundaries, malformed strings, chunked transfer).
2. Reverse proxy IP resolution (untrusted socket spoofing, trusted proxy extraction, whitespace, multi-IP, concurrency).
3. Backend approval concurrency and double-execution race conditions.
"""
import os
import sys
import time
import json
import asyncio
import sqlite3
import tempfile
import threading
import hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from app.main import app, _RATE_LIMITS, MAX_REQUEST_SIZE
from app.sandbox.db import init_db, get_connection
from app.sandbox.service import save_task_scope
from app.approval.service import decide_approval, ApprovalAlreadyProcessedError
from app.policy.models import TaskScope, PolicyConfig
from app.policy.storage import save_policy

client = TestClient(app, headers={"Authorization": "Bearer test-only-operator-token"})

# ==============================================================================
# SECTION 1: REQUEST SIZE BOUNDS ADVERSARIAL CHALLENGES
# ==============================================================================

def test_size_guard_negative_content_length():
    """Probe Content-Length: -1 and other negative values."""
    for neg_val in ["-1", "-5", "-999999", "-0"]:
        res = client.post("/api/sandbox/orders", content=b"{}", headers={"Content-Length": neg_val})
        if neg_val == "-0":
            # -0 in Python int("-0") is 0, which is valid 0 bytes. Reaches router -> 405 Method Not Allowed (since GET only) or 200/422.
            assert res.status_code in (200, 405, 422), f"Expected 200/405/422 for -0, got {res.status_code}"
        else:
            assert res.status_code == 413, f"Expected 413 for negative Content-Length {neg_val}, got {res.status_code}"
            assert "Payload Too Large" in res.json()["detail"]

def test_size_guard_zero_content_length():
    """Probe Content-Length: 0."""
    res = client.post("/api/sandbox/orders", content=b"", headers={"Content-Length": "0"})
    # Should not be blocked by size guard (returns 422 validation error or 400 due to empty body, but NOT 413)
    assert res.status_code != 413, f"Content-Length: 0 was blocked by size guard: {res.status_code}"

def test_size_guard_oversized_content_length():
    """Probe Content-Length: 2000000 and larger."""
    for size in ["1048577", "2000000", "50000000", "999999999999"]:
        res = client.post("/api/sandbox/orders", content=b"x" * 10, headers={"Content-Length": size})
        assert res.status_code == 413, f"Expected 413 for size {size}, got {res.status_code}"
        assert "Payload Too Large" in res.json()["detail"]

def test_size_guard_exact_one_megabyte_boundary():
    """Probe exact 1MB (1048576) boundary."""
    # Exactly 1MB should pass size guard
    res_exact = client.post("/api/sandbox/orders", content=b"{}", headers={"Content-Length": str(MAX_REQUEST_SIZE)})
    assert res_exact.status_code != 413, "Exact 1MB was incorrectly blocked as too large"

    # 1MB + 1 byte should be blocked with 413
    res_plus_one = client.post("/api/sandbox/orders", content=b"{}", headers={"Content-Length": str(MAX_REQUEST_SIZE + 1)})
    assert res_plus_one.status_code == 413, "1MB + 1 byte was not blocked by size guard"

def test_size_guard_malformed_content_length():
    """Probe malformed Content-Length strings."""
    malformed_cases = [
        "abc",
        "1.5",
        "NaN",
        "inf",
        "-Infinity",
        "--1",
        "0x10",
        "10 20",
        "10, 20",
        "null",
        "",
        " ",
        "\x00",
        "2e6",
    ]
    for case in malformed_cases:
        res = client.post("/api/sandbox/orders", content=b"{}", headers={"Content-Length": case})
        assert res.status_code == 400, f"Expected 400 for malformed Content-Length '{case}', got {res.status_code}: {res.text}"
        assert "Malformed Content-Length" in res.json()["detail"]

def test_size_guard_chunked_or_streaming_transfer():
    """
    Probe chunked transfer requests or requests without Content-Length header.
    Tests whether omitting Content-Length can bypass the 1MB payload ceiling.
    """
    # 1. Normal small chunked request without Content-Length to a valid POST route
    def small_generator():
        yield b"{}"

    res_chunked = client.post(
        "/api/sandbox/reset",
        content=small_generator(),
        headers={"Transfer-Encoding": "chunked"}
    )
    # Small chunked payload should be accepted by the app
    assert res_chunked.status_code == 200, f"Small chunked request failed: {res_chunked.status_code}: {res_chunked.text}"

    # 2. Large 2MB body without Content-Length sent to /api/governance/evaluate
    chunk = b"A" * 65536  # 64KB
    def large_generator():
        # Valid JSON with 2MB of padding inside reason field
        yield b'{"tool": "refund_order", "idempotency_key": "chunk-bypass-1", "arguments": {"order_id": "ORD-101", "amount": 100, "currency": "USD", "destination": "card_visa_4242", "reason": "'
        for _ in range(32):  # 32 * 64KB = 2MB
            yield chunk
        yield b'"}}'

    res_large = client.post(
        "/api/governance/evaluate",
        content=large_generator(),
        headers={"Transfer-Encoding": "chunked"}
    )
    # Empirical verification: 2MB chunked stream MUST be blocked with HTTP 413
    print(f"\n[Adversarial Probe] 2MB chunked to /api/governance/evaluate status: {res_large.status_code}: {res_large.text}")
    is_bypassed = res_large.status_code != 413
    print(f"[Adversarial Probe] 1MB size guard bypassed via chunked encoding: {is_bypassed}")
    assert res_large.status_code == 413, f"Expected 413 for oversized chunked payload, got {res_large.status_code}: {res_large.text}"
    assert "Payload Too Large" in res_large.json()["detail"]
    assert not is_bypassed

# ==============================================================================
# SECTION 2: PROXY IP RESOLUTION & RATE LIMIT ADVERSARIAL CHALLENGES
# ==============================================================================

def test_proxy_untrusted_socket_spoofing_blocked(monkeypatch):
    """
    Adversarial test: An attacker from an untrusted socket tries spoofing
    different X-Forwarded-For headers to evade the 20 rpm rate limit.
    """
    monkeypatch.setenv("PYTEST_CURRENT_TEST_BYPASS_RATELIMIT", "0")
    monkeypatch.setenv("AETHERGUARD_RATE_LIMIT_PER_MINUTE", "5")
    # Trusted proxies only loopback
    monkeypatch.setenv("AETHERGUARD_TRUSTED_PROXIES", "127.0.0.1,::1")
    _RATE_LIMITS.clear()

    # Client socket is 'testclient', which is NOT in trusted_proxies!
    # Send 5 requests with 5 different spoofed IPs
    for i in range(5):
        spoofed_ip = f"198.51.100.{i+1}"
        res = client.post(
            "/api/agent/process-ticket",
            json={"ticket_text": f"Refund {i}", "idempotency_key": f"spoof-key-{i}"},
            headers={"X-Forwarded-For": spoofed_ip}
        )
        assert res.status_code != 429, f"Premature 429 on request {i}"

    # 6th request with yet another spoofed IP MUST be blocked (429)!
    # Because all requests belong to socket 'testclient', spoofing fails!
    res_blocked = client.post(
        "/api/agent/process-ticket",
        json={"ticket_text": "Refund 6", "idempotency_key": "spoof-key-6"},
        headers={"X-Forwarded-For": "8.8.8.8"}
    )
    assert res_blocked.status_code == 429, f"Bypass succeeded! Spoofed X-Forwarded-For evaded rate limit: {res_blocked.status_code}"
    assert "Rate limit exceeded" in res_blocked.json()["detail"]
    assert "testclient" in _RATE_LIMITS

def test_proxy_trusted_socket_honors_forwarded_ip(monkeypatch):
    """
    When socket IS trusted, X-Forwarded-For partitions rate limits properly.
    """
    monkeypatch.setenv("PYTEST_CURRENT_TEST_BYPASS_RATELIMIT", "0")
    monkeypatch.setenv("AETHERGUARD_RATE_LIMIT_PER_MINUTE", "2")
    monkeypatch.setenv("AETHERGUARD_TRUSTED_PROXIES", "127.0.0.1,::1,testclient")
    _RATE_LIMITS.clear()

    # User A sends 2 requests
    for i in range(2):
        res = client.post(
            "/api/agent/process-ticket",
            json={"ticket_text": f"A {i}", "idempotency_key": f"userA-{i}"},
            headers={"X-Forwarded-For": "203.0.113.10"}
        )
        assert res.status_code != 429

    # User A 3rd request is blocked
    res_a3 = client.post(
        "/api/agent/process-ticket",
        json={"ticket_text": "A 3", "idempotency_key": "userA-3"},
        headers={"X-Forwarded-For": "203.0.113.10"}
    )
    assert res_a3.status_code == 429

    # User B is NOT blocked
    res_b = client.post(
        "/api/agent/process-ticket",
        json={"ticket_text": "B 1", "idempotency_key": "userB-1"},
        headers={"X-Forwarded-For": "203.0.113.20"}
    )
    assert res_b.status_code != 429

def test_proxy_forwarded_header_edge_cases(monkeypatch):
    """
    Probe unusual X-Forwarded-For header values from trusted proxy socket.
    """
    monkeypatch.setenv("PYTEST_CURRENT_TEST_BYPASS_RATELIMIT", "0")
    monkeypatch.setenv("AETHERGUARD_RATE_LIMIT_PER_MINUTE", "10")
    monkeypatch.setenv("AETHERGUARD_TRUSTED_PROXIES", "testclient")
    _RATE_LIMITS.clear()

    edge_cases = [
        # Leading/trailing whitespace
        ("  203.0.113.50  ", "203.0.113.50"),
        # Multi-proxy chain: client, proxy1, proxy2
        ("203.0.113.60, 10.0.0.1, 192.168.1.1", "203.0.113.60"),
        # Empty string
        ("", "testclient"),
        # Whitespace only
        ("   ", "testclient"),
        # Commas only
        (", , ,", "testclient"),
    ]

    for raw_header, expected_key in edge_cases:
        _RATE_LIMITS.clear()
        res = client.post(
            "/api/agent/process-ticket",
            json={"ticket_text": "Edge case test", "idempotency_key": f"edge-{raw_header[:10]}"},
            headers={"X-Forwarded-For": raw_header}
        )
        assert res.status_code != 429
        assert expected_key in _RATE_LIMITS, f"Expected key '{expected_key}' in _RATE_LIMITS for header '{raw_header}', found {_RATE_LIMITS.keys()}"

# ==============================================================================
# SECTION 3: BACKEND CONCURRENCY & RACE CONDITIONS
# ==============================================================================

def test_backend_concurrent_approval_double_execution_race_condition():
    """
    Adversarial stress test: Multiple threads race to approve the EXACT SAME
    quarantined action concurrently.
    Backend SQLite transaction MUST ensure that:
    1. Exactly ONE thread succeeds.
    2. All other threads fail with 409 Conflict (ApprovalAlreadyProcessedError).
    3. The refund is executed EXACTLY ONCE.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "race_test.db")
        conn = init_db(db_path)
        try:
            # Setup order with $500
            conn.execute(
                "INSERT INTO orders (id, customer_name, currency, paid_amount, refundable_amount, original_destination, status) "
                "VALUES (?, ?, ?, ?, ?, ?, 'paid')",
                ("ORD-RACE-1", "Client Race", "USD", 50000, 50000, "card_visa_4242")
            )
            # Setup task scope
            scope_id = "scope-race-1"
            save_task_scope(
                conn, scope_id, "demo_operator", "ORD-RACE-1", "refund_order",
                50000, "USD", "card_visa_4242",
                (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
            )
            # Create a pending action for $200 refund
            action_id = "act-race-1"
            args = {
                "order_id": "ORD-RACE-1",
                "amount": 20000,
                "currency": "USD",
                "destination": "card_visa_4242",
                "reason": "Adversarial race test",
                "idempotency_key": "idemp-race-1"
            }
            canonical = json.dumps({"tool": "refund_order", "arguments": args}, sort_keys=True)
            fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

            conn.execute(
                """
                INSERT INTO pending_actions (action_id, tool, arguments, fingerprint, task_scope_id, status)
                VALUES (?, 'refund_order', ?, ?, ?, 'pending')
                """,
                (action_id, json.dumps(args), fingerprint, scope_id)
            )
            conn.execute(
                """
                INSERT INTO action_requests (idempotency_key, action_id, fingerprint, scope_id)
                VALUES (?, ?, ?, ?)
                """,
                ("idemp-race-1", action_id, fingerprint, scope_id)
            )
            conn.commit()
        finally:
            conn.close()

        # Now launch 10 parallel threads attempting to decide_approval on action_id
        results = []
        errors = []

        def worker_attempt(worker_idx):
            w_conn = get_connection(db_path)
            try:
                res = decide_approval(w_conn, action_id, "approve", f"operator_{worker_idx}")
                results.append((worker_idx, res))
            except Exception as e:
                errors.append((worker_idx, type(e).__name__, str(e)))
            finally:
                w_conn.close()

        threads = [threading.Thread(target=worker_attempt, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # EMPIRICAL ORACLE ASSERTIONS:
        print(f"\n[Adversarial Race Test] Successes: {len(results)}, Errors: {len(errors)}")
        for e in errors[:5]:
            print(f"  Worker error sample: {e}")
        assert len(results) == 1, f"CRITICAL RACE CONDITION! Expected 1 successful approval, got {len(results)}: {results}. Errors: {errors}"
        assert len(errors) == 9, f"Expected 9 failed workers, got {len(errors)}: {errors}"

        # Verify all failed workers encountered ApprovalAlreadyProcessedError or database lock
        for w_idx, err_type, err_msg in errors:
            assert err_type in ("ApprovalAlreadyProcessedError", "OperationalError"), f"Unexpected error type: {err_type}: {err_msg}"

        # Verify database state integrity
        verify_conn = get_connection(db_path)
        try:
            # Check refund count in refunds table
            refund_count = verify_conn.execute("SELECT COUNT(*) FROM refunds WHERE order_id = 'ORD-RACE-1'").fetchone()[0]
            assert refund_count == 1, f"CRITICAL DOUBLE SPEND! Expected 1 refund row, found {refund_count}"

            # Check order balance: originally 50000, refunded 20000 -> refundable must be 30000
            order_row = verify_conn.execute("SELECT refundable_amount FROM orders WHERE id = 'ORD-RACE-1'").fetchone()
            assert order_row[0] == 30000, f"Balance corruption! Expected 30000, got {order_row[0]}"

            # Check pending action status
            action_row = verify_conn.execute("SELECT status FROM pending_actions WHERE action_id = ?", (action_id,)).fetchone()
            assert action_row[0] == "executed", f"Action status was {action_row[0]}"
        finally:
            verify_conn.close()
