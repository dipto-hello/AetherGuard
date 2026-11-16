"""AI claim judge: only a valid judgment lets a ticket reach the money path."""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.agent.core import SupportAgent
from app.main import app

REAL_JUDGE = SupportAgent._judge_claim_llm  # captured before the autouse offline stub

pytestmark = pytest.mark.usefixtures("stub_ticket_provider")

client = TestClient(app, headers={"Authorization": "Bearer test-only-operator-token"})
TICKET = "My order ORD-101 arrived damaged. Please refund $40 back to my card."


@pytest.fixture(autouse=True)
def reset_sandbox():
    client.post("/api/sandbox/reset")


def _scope():
    res = client.post("/api/governance/scopes", json={
        "operator_id": "operator_dipto", "order_id": "ORD-101", "allowed_action": "refund_order",
        "max_amount": 5000, "allowed_currency": "USD", "allowed_destination": "card_visa_4242",
        "expires_in_hours": 1,
    })
    return res.json()["scope"]["scope_id"]


def _run(key, **extra):
    res = client.post("/api/agent/process-ticket", json={
        "ticket_text": TICKET, "scope_id": _scope(), "idempotency_key": key, **extra,
    })
    assert res.status_code == 200, res.text
    return res.json()["trace"]


def _refundable():
    return client.get("/api/sandbox/orders/ORD-101").json()["order"]["refundable_amount"]


def _judge(monkeypatch, verdict, reason):
    monkeypatch.setattr(SupportAgent, "_judge_claim_llm",
                        lambda self, text, evidence=None, *, api_key=None: {"verdict": verdict, "reason": reason})


def _pending():
    return client.get("/api/governance/pending-approvals").json()["pending_actions"]


def test_unsure_claim_waits_for_human_approval(monkeypatch):
    _judge(monkeypatch, "unsure", "Photo is too blurry to see the crack")
    trace = _run("judge-unsure")
    assert trace["boundary_verdict"] == "APPROVAL_REQUIRED"
    assert trace["pending_approval"] is True
    assert trace["executed"] is False
    assert trace["boundary_reason"] == "CLAIM_NEEDS_REVIEW: Photo is too blurry to see the crack"
    assert _refundable() == 25000
    [pending] = _pending()
    assert pending["action_id"] == trace["action_id"]
    assert pending["arguments"]["amount"] == 4000
    assert pending["arguments"]["reason"] == "AI judge unsure: Photo is too blurry to see the crack"


def test_approved_unsure_claim_pays_out(monkeypatch):
    _judge(monkeypatch, "unsure", "Cannot verify")
    trace = _run("judge-unsure-approve")
    res = client.post(f"/api/governance/approvals/{trace['action_id']}/decide",
                      json={"decision": "approve", "reviewer_id": "demo_operator"})
    assert res.status_code == 200, res.text
    assert _refundable() == 21000


def test_unsure_claim_cannot_escape_the_rules(monkeypatch):
    _judge(monkeypatch, "unsure", "Cannot verify")
    res = client.post("/api/governance/scopes", json={
        "operator_id": "operator_dipto", "order_id": "ORD-101", "allowed_action": "refund_order",
        "max_amount": 3000, "allowed_currency": "USD", "allowed_destination": "card_visa_4242",
        "expires_in_hours": 1,
    })
    trace = client.post("/api/agent/process-ticket", json={
        "ticket_text": TICKET, "scope_id": res.json()["scope"]["scope_id"], "idempotency_key": "judge-unsure-over",
    }).json()["trace"]
    assert trace["boundary_verdict"] == "BLOCKED"  # $40 is over the $30 permission
    assert _pending() == []
    assert _refundable() == 25000


def test_invalid_claim_is_blocked_without_proposal(monkeypatch):
    _judge(monkeypatch, "invalid", "Photo shows an intact bottle")

    def no_proposal(*args, **kwargs):
        raise AssertionError("proposal must not run for an invalid claim")
    monkeypatch.setattr(SupportAgent, "_parse_ticket_llm", no_proposal)
    trace = _run("judge-invalid")
    assert trace["boundary_verdict"] == "BLOCKED"
    assert trace["executed"] is False
    assert trace["boundary_reason"] == "CLAIM_INVALID: Photo shows an intact bottle"
    assert trace["action_id"] is not None  # the attempt is audited
    assert _pending() == []
    assert _refundable() == 25000


def test_valid_claim_runs_existing_flow(monkeypatch):
    _judge(monkeypatch, "valid", "Coherent damage claim")
    trace = _run("judge-valid")
    assert trace["executed"] is True
    assert trace["claim_judgment"] == {"verdict": "valid", "reason": "Coherent damage claim"}
    assert _refundable() == 21000


def _fake_client(monkeypatch, generate):
    from google import genai
    monkeypatch.setattr(genai, "Client", lambda **kwargs: SimpleNamespace(
        models=SimpleNamespace(generate_content=generate)))


def test_judge_failure_is_unsure(monkeypatch):
    def boom(**kwargs):
        raise RuntimeError("network down")
    _fake_client(monkeypatch, boom)
    result = REAL_JUDGE(SupportAgent(boundary=None, api_key="k"), TICKET)
    assert result["verdict"] == "unsure"


def test_photo_skips_text_only_models(monkeypatch):
    seen = []

    def record(**kwargs):
        seen.append(kwargs["model"])
        raise RuntimeError("quota")
    _fake_client(monkeypatch, record)
    result = REAL_JUDGE(SupportAgent(boundary=None, api_key="k"), TICKET, (b"\xff\xd8\xff", "image/jpeg"))
    assert seen and "gemma-4-31b-it" not in seen
    assert result["verdict"] == "unsure"


def test_bad_judge_output_is_unsure(monkeypatch):
    _fake_client(monkeypatch, lambda **kwargs: SimpleNamespace(function_calls=[
        SimpleNamespace(name="judge_claim", args={"verdict": "maybe", "reason": "x"})]))
    result = REAL_JUDGE(SupportAgent(boundary=None, api_key="k"), TICKET)
    assert result["verdict"] == "unsure"


def test_well_formed_judge_output_is_returned(monkeypatch):
    _fake_client(monkeypatch, lambda **kwargs: SimpleNamespace(function_calls=[
        SimpleNamespace(name="judge_claim", args={"verdict": "invalid", "reason": "Photo shows an intact box"})]))
    result = REAL_JUDGE(SupportAgent(boundary=None, api_key="k"), TICKET)
    assert result == {"verdict": "invalid", "reason": "Photo shows an intact box"}


import base64

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 16


@pytest.mark.parametrize("extra", [
    {"evidence_image": "not base64!!", "evidence_mime_type": "image/png"},
    {"evidence_image": "data:image/png;base64," + base64.b64encode(PNG).decode(), "evidence_mime_type": "image/png"},
    {"evidence_image": base64.b64encode(PNG).decode(), "evidence_mime_type": "image/jpeg"},
    {"evidence_image": base64.b64encode(PNG).decode(), "evidence_mime_type": "image/gif"},
    {"evidence_image": base64.b64encode(PNG).decode()},
    {"evidence_mime_type": "image/png"},
])
def test_evidence_rejects_bad_input(extra):
    res = client.post("/api/agent/process-ticket", json={"ticket_text": TICKET, "idempotency_key": "bad-photo", **extra})
    assert res.status_code == 422


def test_evidence_reaches_judge(monkeypatch):
    seen = {}

    def capture(self, text, evidence=None, *, api_key=None):
        seen["evidence"] = evidence
        return {"verdict": "valid", "reason": "ok"}
    monkeypatch.setattr(SupportAgent, "_judge_claim_llm", capture)
    _run("good-photo", evidence_image=base64.b64encode(PNG).decode(), evidence_mime_type="image/png")
    assert seen["evidence"] == (PNG, "image/png")
