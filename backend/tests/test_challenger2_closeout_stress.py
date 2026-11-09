"""
Challenger 2 Empirical Adversarial Stress Test Suite (Milestone 2 Closeout).
Targets: AetherGuard/backend/app/main.py

Verifies:
1. True chunked streaming with oversized payload (>1MB) — early abort without reading entire stream into memory.
2. Deceptive small Content-Length with oversized body — verify HTTP 413.
3. Negative and malformed Content-Length handling (HTTP 413 and 400).
4. Spoofed X-Forwarded-For headers from untrusted socket — verify ignored.
"""
import os
import sys
import time
import asyncio
import pytest
import httpx
from fastapi.testclient import TestClient
from app.main import app, _RATE_LIMITS, MAX_REQUEST_SIZE

client = TestClient(app, headers={"Authorization": "Bearer test-only-operator-token"})

# ==============================================================================
# 1. TRUE CHUNKED STREAMING OVERSIZED PAYLOAD & EARLY ABORT ORACLE
# ==============================================================================

@pytest.mark.asyncio
async def test_chunked_streaming_oversized_payload_aborts_early():
    """
    Empirical oracle:
    Stream a 6.4 MB payload (100 chunks of 64 KB) with Transfer-Encoding: chunked.
    The server MUST return HTTP 413 on chunk 17 (1.06 MB > 1 MB) and terminate
    the stream immediately without reading or buffering subsequent chunks.
    """
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        chunks_yielded = 0

        async def oversized_stream():
            nonlocal chunks_yielded
            for i in range(100):
                chunks_yielded += 1
                yield b"C" * 65536

        res = await ac.post(
            "/api/governance/evaluate",
            content=oversized_stream(),
            headers={
                "Authorization": "Bearer test-only-operator-token",
                "Transfer-Encoding": "chunked",
            }
        )

        assert res.status_code == 413, f"Expected 413, got {res.status_code}: {res.text}"
        detail = res.json().get("detail", "")
        assert "Payload Too Large" in detail
        assert "1MB" in detail

        # Oracle check: Must abort early (at chunk 17 or 18 max), NOT all 100 chunks!
        assert chunks_yielded <= 18, (
            f"FAIL: Server read {chunks_yielded} chunks into memory! Early abort did not halt generator."
        )


@pytest.mark.asyncio
async def test_chunked_streaming_infinite_generator_failsafe():
    """
    Empirical oracle with fail-dead tripwire:
    If the server fails to abort early and continues pulling beyond 20 chunks,
    the generator deliberately trips an exception.
    """
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        tripwire_hit = False

        async def infinite_chunk_generator():
            nonlocal tripwire_hit
            count = 0
            while True:
                count += 1
                if count > 20:
                    tripwire_hit = True
                    raise RuntimeError("TRIPWIRE TRIGGERED: Server consumed more than 20 chunks without early abort!")
                yield b"D" * 65536

        res = await ac.post(
            "/api/governance/evaluate",
            content=infinite_chunk_generator(),
            headers={
                "Authorization": "Bearer test-only-operator-token",
                "Transfer-Encoding": "chunked",
            }
        )

        assert res.status_code == 413
        assert tripwire_hit is False, "Tripwire was hit! The server attempted to read past the 1MB boundary."


@pytest.mark.asyncio
async def test_chunked_streaming_valid_payload_succeeds():
    """
    Verify that a legitimate chunked stream under 1MB is accepted and fully read into request._body.
    """
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        async def legitimate_stream():
            # 8 chunks of 32KB = 256KB total (well under 1MB)
            for _ in range(8):
                yield b"E" * 32768

        res = await ac.post(
            "/api/sandbox/reset",
            content=legitimate_stream(),
            headers={
                "Authorization": "Bearer test-only-operator-token",
                "Transfer-Encoding": "chunked",
            }
        )
        assert res.status_code == 200, f"Valid chunked stream failed: {res.status_code}: {res.text}"


# ==============================================================================
# 2. DECEPTIVE SMALL CONTENT-LENGTH WITH OVERSIZED BODY
# ==============================================================================

@pytest.mark.asyncio
async def test_deceptive_small_content_length_with_oversized_body_blocked():
    """
    Adversarial probe: Attacker declares Content-Length: 10, but actually streams 2MB.
    The server MUST inspect the actual incoming stream and return HTTP 413.
    """
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        async def deceptive_stream():
            for _ in range(32):
                yield b"L" * 65536

        res = await ac.post(
            "/api/governance/evaluate",
            content=deceptive_stream(),
            headers={
                "Authorization": "Bearer test-only-operator-token",
                "Content-Length": "10",
            }
        )
        assert res.status_code == 413, f"Bypass succeeded! Deceptive Content-Length returned {res.status_code}"
        assert "Payload Too Large" in res.json().get("detail", "")


@pytest.mark.asyncio
async def test_deceptive_zero_content_length_with_oversized_body_blocked():
    """
    Adversarial probe: Attacker declares Content-Length: 0, but streams 1.5MB.
    Must return HTTP 413.
    """
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        async def deceptive_stream():
            for _ in range(25):
                yield b"Z" * 65536

        res = await ac.post(
            "/api/governance/evaluate",
            content=deceptive_stream(),
            headers={
                "Authorization": "Bearer test-only-operator-token",
                "Content-Length": "0",
            }
        )
        assert res.status_code == 413, f"Bypass succeeded! Content-Length 0 with body returned {res.status_code}"
        assert "Payload Too Large" in res.json().get("detail", "")


@pytest.mark.asyncio
async def test_deceptive_exact_boundary_one_byte_over_blocked():
    """
    Adversarial probe: Content-Length declares exact 1MB (1048576), but body streams 1,048,577 bytes.
    Must return HTTP 413.
    """
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        async def stream_one_byte_over():
            yield b"A" * 1_048_576
            yield b"B"  # 1 byte over

        res = await ac.post(
            "/api/governance/evaluate",
            content=stream_one_byte_over(),
            headers={
                "Authorization": "Bearer test-only-operator-token",
                "Content-Length": str(MAX_REQUEST_SIZE),
            }
        )
        assert res.status_code == 413
        assert "Payload Too Large" in res.json().get("detail", "")


# ==============================================================================
# 3. NEGATIVE AND MALFORMED CONTENT-LENGTH HANDLING
# ==============================================================================

def test_negative_content_length_returns_413():
    """
    Negative Content-Length values must be rejected with HTTP 413.
    """
    negatives = ["-1", "-2", "-100", "-1048576", "-999999999999999"]
    for val in negatives:
        res = client.post("/api/sandbox/orders", content=b"{}", headers={"Content-Length": val})
        assert res.status_code == 413, f"Negative Content-Length {val} returned {res.status_code}: {res.text}"
        assert "Payload Too Large" in res.json().get("detail", "")


def test_malformed_content_length_returns_400():
    """
    Malformed Content-Length headers must be rejected with HTTP 400.
    """
    malformed_values = [
        "abc",
        "1.5",
        "NaN",
        "Infinity",
        "-Infinity",
        "10 20",
        "10, 20",
        "0x10",
        "1e6",
        "--1",
        "",
        "   ",
        "\x00",
        "null",
        "None",
    ]
    for val in malformed_values:
        res = client.post("/api/sandbox/orders", content=b"{}", headers={"Content-Length": val})
        assert res.status_code == 400, f"Malformed Content-Length '{val}' returned {res.status_code}: {res.text}"
        assert "Malformed Content-Length" in res.json().get("detail", "")


def test_oversized_content_length_header_returns_413_instantly():
    """
    Oversized Content-Length headers must be rejected with HTTP 413 without reading body.
    """
    oversized = ["1048577", "2000000", "50000000", "999999999999999"]
    for val in oversized:
        res = client.post("/api/sandbox/orders", content=b"x", headers={"Content-Length": val})
        assert res.status_code == 413, f"Oversized Content-Length {val} returned {res.status_code}: {res.text}"
        assert "Payload Too Large" in res.json().get("detail", "")


# ==============================================================================
# 4. SPOOFED X-FORWARDED-FOR HEADERS FROM UNTRUSTED SOCKET
# ==============================================================================

def test_spoofed_x_forwarded_for_from_untrusted_socket_ignored(monkeypatch):
    """
    Adversarial test:
    An untrusted client socket attempts to evade the rate limiter by rotating
    X-Forwarded-For headers on each request.
    The server MUST ignore X-Forwarded-For because the immediate socket is not trusted,
    and MUST enforce the rate limit against the socket host ('testclient').
    """
    monkeypatch.setenv("PYTEST_CURRENT_TEST_BYPASS_RATELIMIT", "0")
    monkeypatch.setenv("AETHERGUARD_RATE_LIMIT_PER_MINUTE", "4")
    # Only loopback is trusted; 'testclient' is NOT trusted
    monkeypatch.setenv("AETHERGUARD_TRUSTED_PROXIES", "127.0.0.1,::1")
    _RATE_LIMITS.clear()

    # 4 requests with distinct spoofed IPs
    for i in range(4):
        spoofed = f"198.51.100.{i+10}"
        res = client.post(
            "/api/agent/process-ticket",
            json={"ticket_text": f"Refund {i}", "idempotency_key": f"untrusted-spoof-{i}"},
            headers={"X-Forwarded-For": spoofed}
        )
        assert res.status_code != 429, f"Premature 429 on request {i}"

    # 5th request with yet another spoofed IP MUST be blocked (429)!
    res_blocked = client.post(
        "/api/agent/process-ticket",
        json={"ticket_text": "Refund 5", "idempotency_key": "untrusted-spoof-5"},
        headers={"X-Forwarded-For": "203.0.113.99"}
    )
    assert res_blocked.status_code == 429, (
        f"VULNERABILITY CONFIRMED: Untrusted socket bypassed rate limit via spoofed X-Forwarded-For! Status: {res_blocked.status_code}"
    )
    assert "Rate limit exceeded" in res_blocked.json().get("detail", "")
    assert res_blocked.headers.get("Retry-After") == "60"

    # Verify that the socket was tracked as 'testclient' and spoofed IPs are absent
    assert "testclient" in _RATE_LIMITS
    assert "203.0.113.99" not in _RATE_LIMITS
    for i in range(4):
        assert f"198.51.100.{i+10}" not in _RATE_LIMITS


def test_trusted_proxy_socket_resolves_client_ip_correctly(monkeypatch):
    """
    When the socket IS in AETHERGUARD_TRUSTED_PROXIES, X-Forwarded-For is properly parsed,
    isolating rate limit quotas per upstream client IP.
    """
    monkeypatch.setenv("PYTEST_CURRENT_TEST_BYPASS_RATELIMIT", "0")
    monkeypatch.setenv("AETHERGUARD_RATE_LIMIT_PER_MINUTE", "2")
    # Mark 'testclient' as trusted reverse proxy
    monkeypatch.setenv("AETHERGUARD_TRUSTED_PROXIES", "127.0.0.1,::1,testclient")
    _RATE_LIMITS.clear()

    # Client Alpha sends 2 requests through proxy
    for i in range(2):
        res = client.post(
            "/api/agent/process-ticket",
            json={"ticket_text": f"Alpha {i}", "idempotency_key": f"alpha-{i}"},
            headers={"X-Forwarded-For": "192.0.2.1, 10.0.0.1"}
        )
        assert res.status_code != 429

    # Client Alpha's 3rd request is rate-limited
    res_a3 = client.post(
        "/api/agent/process-ticket",
        json={"ticket_text": "Alpha 3", "idempotency_key": "alpha-3"},
        headers={"X-Forwarded-For": "192.0.2.1, 10.0.0.1"}
    )
    assert res_a3.status_code == 429

    # Client Beta (different client behind same proxy) is NOT blocked
    res_b = client.post(
        "/api/agent/process-ticket",
        json={"ticket_text": "Beta 1", "idempotency_key": "beta-1"},
        headers={"X-Forwarded-For": "192.0.2.2, 10.0.0.1"}
    )
    assert res_b.status_code != 429
    assert "192.0.2.1" in _RATE_LIMITS
    assert "192.0.2.2" in _RATE_LIMITS


def test_rate_limit_cleanup_prunes_empty_keys(monkeypatch):
    """
    Verify that expired timestamps are pruned and empty keys are deleted from _RATE_LIMITS,
    preventing unbounded memory growth.
    """
    monkeypatch.setenv("PYTEST_CURRENT_TEST_BYPASS_RATELIMIT", "0")
    monkeypatch.setenv("AETHERGUARD_RATE_LIMIT_PER_MINUTE", "10")
    monkeypatch.setenv("AETHERGUARD_TRUSTED_PROXIES", "127.0.0.1,::1,testclient")
    _RATE_LIMITS.clear()

    # Pre-populate an expired entry (70 seconds ago)
    past = time.time() - 70.0
    _RATE_LIMITS["stale_client"] = [past]

    # Trigger request to process-ticket from active client
    res = client.post(
        "/api/agent/process-ticket",
        json={"ticket_text": "Test cleanup", "idempotency_key": "cleanup-1"},
        headers={"X-Forwarded-For": "stale_client"}
    )
    assert res.status_code != 429

    # Stale timestamp should be pruned, and only the current request timestamp retained
    assert len(_RATE_LIMITS["stale_client"]) == 1
    assert _RATE_LIMITS["stale_client"][0] > past + 60.0
