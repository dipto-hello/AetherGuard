import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.sandbox.db import get_connection

client = TestClient(app, headers={"Authorization": "Bearer test-only-operator-token"})

def test_api_get_evaluation_cases():
    res = client.get("/api/evaluation/cases")
    assert res.status_code == 200
    cases = res.json()["cases"]
    assert len(cases) == 10
    ids = [c["id"] for c in cases]
    assert "CASE-01" in ids
    assert "CASE-04" in ids
    assert "CASE-10" in ids

def test_api_trigger_full_evaluation():
    conn = get_connection()
    before = [tuple(row) for row in conn.execute("SELECT * FROM orders ORDER BY id")]
    refunds_before = [tuple(row) for row in conn.execute("SELECT * FROM refunds ORDER BY id")]
    res = client.post("/api/evaluation/run")
    assert res.status_code == 200
    report = res.json()["report"]
    assert report["total_cases"] == 10
    assert report["passed_cases"] == 10
    assert report["failed_cases"] == 0
    assert report["accuracy_percent"] == 100.0
    assert report["unauthorized_backend_writes"] == 0
    assert [tuple(row) for row in conn.execute("SELECT * FROM orders ORDER BY id")] == before
    assert [tuple(row) for row in conn.execute("SELECT * FROM refunds ORDER BY id")] == refunds_before
    conn.close()
