import os
import pytest
from fastapi.testclient import TestClient
from app.main import app, _RATE_LIMITS

client = TestClient(app, headers={"Authorization": "Bearer test-only-operator-token"})

def test_payload_size_limit_blocks_oversized_request():
    headers = {
        "Authorization": "Bearer test-only-operator-token",
        "Content-Length": str(2 * 1024 * 1024)  # 2 MB
    }
    response = client.post("/api/sandbox/orders", content=b"x" * 10, headers=headers)
    assert response.status_code == 413
    assert "Payload Too Large" in response.json()["detail"]

def test_rate_limit_triggers_429_on_burst(monkeypatch):
    monkeypatch.setenv("PYTEST_CURRENT_TEST_BYPASS_RATELIMIT", "0")
    monkeypatch.setenv("AETHERGUARD_RATE_LIMIT_PER_MINUTE", "3")
    _RATE_LIMITS.clear()

    # Requests 1, 2, 3 should pass rate check
    # Note: ticket text is empty or invalid so it may return 422, but not 429!
    for i in range(3):
        res = client.post("/api/agent/process-ticket", json={"ticket_text": f"Refund {i}", "idempotency_key": f"key-{i}"})
        assert res.status_code != 429

    # Request 4 should be rate-limited with 429 and Retry-After
    res4 = client.post("/api/agent/process-ticket", json={"ticket_text": "Refund 4", "idempotency_key": "key-4"})
    assert res4.status_code == 429
    assert res4.headers.get("retry-after") == "60"
    assert "Rate limit exceeded" in res4.json()["detail"]
