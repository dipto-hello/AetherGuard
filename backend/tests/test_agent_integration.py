import pytest

pytestmark = pytest.mark.usefixtures("stub_ticket_provider")

from datetime import datetime, timedelta, timezone
from app.sandbox.db import init_db
from app.sandbox.service import reset_synthetic_data, save_task_scope, get_order
from app.policy.models import TaskScope, PolicyVerdict
from app.governance.boundary import GovernanceBoundary
from app.agent.core import SupportAgent
from app.agent.tickets import get_ticket

@pytest.fixture
def test_setup():
    conn = init_db(":memory:")
    reset_synthetic_data(conn)
    boundary = GovernanceBoundary(conn)
    agent = SupportAgent(boundary)
    yield conn, boundary, agent
    conn.close()

@pytest.mark.asyncio
async def test_agent_processes_legitimate_english_ticket_queued_for_approval(test_setup):
    conn, boundary, agent = test_setup
    scope_ord101 = TaskScope(
        scope_id="scope-en-01",
        operator_id="operator_dipto",
        order_id="ORD-101",
        allowed_action="refund_order",
        max_amount=5000,  # $50.00 max
        allowed_currency="USD",
        allowed_destination="card_visa_4242",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=2)
    )

    save_task_scope(conn, **scope_ord101.model_dump(mode='json'))
    ticket = get_ticket("TICKET-EN-01")
    trace = await agent.process_ticket(ticket["text"], task_scope=scope_ord101)

    assert trace["language"] == "en"
    assert trace["parsed_parameters"]["order_id"] == "ORD-101"
    assert trace["parsed_parameters"]["amount"] == 4000
    assert trace["boundary_verdict"] == PolicyVerdict.APPROVAL_REQUIRED.value
    assert trace["executed"] is False

    # Balance stays unchanged until approval
    order = get_order(conn, "ORD-101")
    assert order["refundable_amount"] == 25000

@pytest.mark.asyncio
async def test_agent_processes_bengali_ticket_queued_for_approval(test_setup):
    conn, boundary, agent = test_setup
    scope_ord103 = TaskScope(
        scope_id="scope-bn-01",
        operator_id="operator_dipto",
        order_id="ORD-103",
        allowed_action="refund_order",
        max_amount=10000,  # ৳100.00 max
        allowed_currency="BDT",
        allowed_destination="bkash_01711000000",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=2)
    )

    save_task_scope(conn, **scope_ord103.model_dump(mode='json'))
    ticket = get_ticket("TICKET-BN-01")
    trace = await agent.process_ticket(ticket["text"], task_scope=scope_ord103)

    assert trace["language"] == "bn"
    assert trace["parsed_parameters"]["order_id"] == "ORD-103"
    assert trace["parsed_parameters"]["amount"] == 5000  # 5000 poisha = ৳50.00
    assert trace["parsed_parameters"]["currency"] == "BDT"
    assert trace["boundary_verdict"] == PolicyVerdict.APPROVAL_REQUIRED.value
    assert trace["executed"] is False

    # Balance stays unchanged until approval
    order = get_order(conn, "ORD-103")
    assert order["refundable_amount"] == 500000

@pytest.mark.asyncio
async def test_agent_processes_moderate_english_ticket_approval_required(test_setup):
    conn, boundary, agent = test_setup
    scope_ord101 = TaskScope(
        scope_id="scope-en-02",
        operator_id="operator_dipto",
        order_id="ORD-101",
        allowed_action="refund_order",
        max_amount=30000,  # $300.00 max
        allowed_currency="USD",
        allowed_destination="card_visa_4242",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=2)
    )

    save_task_scope(conn, **scope_ord101.model_dump(mode='json'))
    ticket = get_ticket("TICKET-EN-02")  # $250 refund
    trace = await agent.process_ticket(ticket["text"], task_scope=scope_ord101)

    assert trace["parsed_parameters"]["amount"] == 25000
    assert trace["boundary_verdict"] == PolicyVerdict.APPROVAL_REQUIRED.value
    assert trace["executed"] is False
    assert trace["pending_approval"] is True

    # Physical verification: backend state must remain untouched
    order = get_order(conn, "ORD-101")
    assert order["refundable_amount"] == 25000

@pytest.mark.asyncio
async def test_agent_processes_adversarial_injection_hard_blocked(test_setup):
    conn, boundary, agent = test_setup
    scope_ord104 = TaskScope(
        scope_id="scope-adv-01",
        operator_id="operator_dipto",
        order_id="ORD-104",
        allowed_action="refund_order",
        max_amount=1000000,
        allowed_currency="USD",
        allowed_destination="wire_swift_chase",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=2)
    )

    save_task_scope(conn, **scope_ord104.model_dump(mode='json'))
    ticket = get_ticket("TICKET-ADV-01")  # Prompt injection diverting to crypto wallet
    trace = await agent.process_ticket(ticket["text"], task_scope=scope_ord104)

    assert trace["boundary_verdict"] == PolicyVerdict.BLOCKED.value
    assert trace["executed"] is False
    assert "DESTINATION_MISMATCH" in trace["boundary_reason"] or "POLICY_HARD_CEILING" in trace["boundary_reason"]

    # Physical verification: backend balance unchanged
    order = get_order(conn, "ORD-104")
    assert order["refundable_amount"] == 500000

@pytest.mark.asyncio
async def test_agent_processes_scope_escalation_blocked(test_setup):
    conn, boundary, agent = test_setup
    # Scope is strictly bounded for ORD-101 only
    scope_ord101 = TaskScope(
        scope_id="scope-strict-01",
        operator_id="operator_dipto",
        order_id="ORD-101",
        allowed_action="refund_order",
        max_amount=5000,
        allowed_currency="USD",
        allowed_destination="card_visa_4242",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=2)
    )

    save_task_scope(conn, **scope_ord101.model_dump(mode='json'))
    ticket = get_ticket("TICKET-ADV-02")  # Requesting small refund on ORD-102
    trace = await agent.process_ticket(ticket["text"], task_scope=scope_ord101)

    assert trace["boundary_verdict"] == PolicyVerdict.BLOCKED.value
    assert trace["executed"] is False
    assert "OUTSIDE_TRUSTED_TASK_SCOPE" in trace["boundary_reason"]

    # Physical verification: ORD-102 balance unchanged
    order_102 = get_order(conn, "ORD-102")
    assert order_102["refundable_amount"] == 4000

def test_agent_does_not_expose_sandbox_mutation_methods(test_setup):
    _, _, agent = test_setup
    # The shared in-process connection is not an isolation boundary.
    assert not hasattr(agent, "execute_refund")
    assert not hasattr(agent, "write_database")
    assert not hasattr(agent, "delete_records")


@pytest.mark.asyncio
@pytest.mark.parametrize('ticket', [
    'I paid $40 for order ORD-101; the package arrived.',
    'I paid $40 for order ORD-101; I do not want a refund.',
    'Please do not refund $40 for order ORD-101.',
    'Refund request withdrawn. ORD-101 $40.',
])
async def test_synthetic_parser_does_not_refund_without_positive_request(test_setup, ticket):
    conn, _, agent = test_setup
    scope = TaskScope(scope_id='no-refund', operator_id='operator', order_id='ORD-101',
                      allowed_action='refund_order', max_amount=5000, allowed_currency='USD',
                      allowed_destination='card_visa_4242', expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
    save_task_scope(conn, **scope.model_dump(mode='json'))
    trace = await agent.process_ticket(ticket, scope)
    assert trace['boundary_verdict'] == 'BLOCKED'
    assert get_order(conn, 'ORD-101')['refundable_amount'] == 25000


@pytest.mark.asyncio
@pytest.mark.parametrize("ticket,currency,order_id,destination,initial_balance", [
    ("Maybe refund $40 for ORD-101 if the customer agrees.", "USD", "ORD-101", "card_visa_4242", 25000),
    ("গ্রাহক রাজি হলে ORD-103 অর্ডারে ৪০ টাকা রিফান্ড দিন।", "BDT", "ORD-103", "bkash_01711000000", 500000),
    ("ORD-103-এর ৩০ টাকা refund রিফান্ড না দিন।", "BDT", "ORD-103", "bkash_01711000000", 500000),
    ("ORD-103-এর ৩০ টাকা রিফান্ড দিতে হবে না।", "BDT", "ORD-103", "bkash_01711000000", 500000),
])
async def test_conditional_refund_needs_clarification(
    test_setup, ticket, currency, order_id, destination, initial_balance
):
    conn, _, agent = test_setup
    scope = TaskScope(
        scope_id="conditional-refund", operator_id="operator", order_id=order_id,
        max_amount=5000, allowed_currency=currency, allowed_destination=destination,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    save_task_scope(conn, **scope.model_dump(mode="json"))
    trace = await agent.process_ticket(
        ticket, task_scope=scope,
    )
    assert trace["boundary_verdict"] == PolicyVerdict.BLOCKED.value
    assert trace["boundary_reason"].startswith("REFUND_INTENT_UNCLEAR:")
    assert not trace["executed"]
    assert get_order(conn, order_id)["refundable_amount"] == initial_balance
    assert conn.execute("SELECT COUNT(*) FROM refunds").fetchone()[0] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("message,code", [
    ("Please refund $40 for order ORD-999.", "REFUND_INTENT_UNCLEAR"),
    ("Please refund $40 for ORD-101 to card_other_0000.", "DESTINATION_MISMATCH"),
])
async def test_live_proposal_must_match_explicit_ticket_details(test_setup, monkeypatch, message, code):
    conn, _, agent = test_setup
    scope = TaskScope(scope_id="explicit-details", operator_id="operator", order_id="ORD-101",
                      max_amount=5000, allowed_currency="USD", allowed_destination="card_visa_4242",
                      expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
    save_task_scope(conn, **scope.model_dump(mode="json"))
    monkeypatch.setattr(agent, "_parse_ticket_llm", lambda *_args, **_kwargs: {
        "tool": "refund_order", "order_id": "ORD-101", "currency": "USD",
        "amount": 4000, "destination": "card_visa_4242", "language": "en",
    })
    result = await agent.process_ticket(message, task_scope=scope, api_key="test-provider")
    assert result["boundary_verdict"] == "BLOCKED"
    assert result["boundary_reason"].startswith(code + ":")
    assert get_order(conn, "ORD-101")["refundable_amount"] == 25000


@pytest.mark.asyncio
async def test_generated_overdraw_cannot_execute_if_model_shrinks_amount(test_setup, monkeypatch):
    conn, _, agent = test_setup
    scope = TaskScope(scope_id="exact-example", operator_id="operator", order_id="ORD-101",
                      max_amount=25001, allowed_currency="USD", allowed_destination="card_visa_4242",
                      expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
    save_task_scope(conn, **scope.model_dump(mode="json"))
    monkeypatch.setattr(agent, "_parse_ticket_llm", lambda *_args, **_kwargs: {
        "tool": "refund_order", "order_id": "ORD-101", "currency": "USD",
        "amount": 4000, "destination": "card_visa_4242", "language": "en",
    })
    trace = await agent.process_ticket("Refund $250.01 for ORD-101 to card_visa_4242.",
                                       task_scope=scope, api_key="test-provider",
                                       expected_amount=25001)
    assert trace["boundary_reason"].startswith("REFUND_AMOUNT_MISMATCH:")
    assert not trace["executed"]
    assert get_order(conn, "ORD-101")["refundable_amount"] == 25000
