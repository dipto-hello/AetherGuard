"""
Negative & Positive Regression Tests: Agent Trace Data Minimization & Pre-Scope Protection.
Strictly verifies that:
1. Neither synthetic nor LLM parsers read protected order data before task-scope authorization.
2. No-scope, expired-scope, cross-order, and unpersisted-scope tickets produce ZERO get_order calls.
3. Raw payment destinations and order state are never leaked on blocked/unauthorized traces.
4. Tickets omitting an explicit destination or using generic placeholders ('original payment card')
   are authoritatively enriched ONLY after successful scope authorization.
5. get_order() is instrumented/monkeypatched to empirically assert ZERO unauthorized database reads.
"""
import json
import pytest
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone

import app.sandbox.service
import app.agent.core
from app.sandbox.db import init_db
from app.sandbox.service import reset_synthetic_data, save_task_scope, get_order
from app.policy.models import TaskScope, PolicyVerdict
from app.governance.boundary import GovernanceBoundary
from app.agent.core import SupportAgent


@pytest.fixture
def agent_env():
    conn = init_db(":memory:")
    reset_synthetic_data(conn)
    boundary = GovernanceBoundary(conn)
    agent = SupportAgent(boundary)
    yield conn, agent
    conn.close()


@pytest.fixture
def spy_get_order(monkeypatch):
    """
    Instruments get_order across both sandbox service and agent core
    to verify exact database read counts and detect any unauthorized reads.
    """
    calls = []
    real_get_order = app.sandbox.service.get_order

    def tracked_get_order(conn, order_id):
        calls.append(order_id)
        return real_get_order(conn, order_id)

    monkeypatch.setattr(app.sandbox.service, "get_order", tracked_get_order)
    monkeypatch.setattr(app.agent.core, "get_order", tracked_get_order)
    return calls


# =====================================================================
# 1. NO-SCOPE TESTS (ZERO DB READS & DATA MINIMIZATION)
# =====================================================================

@pytest.mark.asyncio
async def test_no_scope_without_destination_blocks_and_zero_db_reads(agent_env, spy_get_order):
    """
    Ticket references valid order ORD-101 WITHOUT explicit destination,
    and NO task scope is supplied (task_scope=None).
    Must fail closed, return BLOCKED, sanitize destination, and trigger ZERO get_order reads.
    """
    conn, agent = agent_env
    ticket_text = "Please refund $40 for order ORD-101"

    trace = await agent.process_ticket(ticket_text, task_scope=None, force_mode="synthetic")

    # Rejection verification
    assert trace["boundary_verdict"] == PolicyVerdict.BLOCKED.value
    assert trace["executed"] is False
    assert "OUTSIDE_TRUSTED_TASK_SCOPE" in trace["boundary_reason"]

    # Absence of sensitive data in complete returned trace
    assert trace["order_state"] is None, "order_state must be None when no scope is authorized"
    assert trace["parsed_parameters"]["destination"] is None, "Destination must be None on blocked request"
    assert trace["refund"] is None

    # Empirical assertion: ZERO database reads of order state
    assert len(spy_get_order) == 0, f"Unauthorized database read detected! Calls: {spy_get_order}"

    # Database state untouched
    assert get_order(conn, "ORD-101")["refundable_amount"] == 25000


@pytest.mark.asyncio
async def test_no_scope_with_explicit_destination_blocks_and_zero_db_reads(agent_env, spy_get_order):
    """
    Ticket references valid order ORD-101 WITH explicit destination,
    but NO task scope is supplied.
    Must fail closed, return BLOCKED, sanitize raw destination, and trigger ZERO get_order reads.
    """
    conn, agent = agent_env
    ticket_text = "Please refund $40 for order ORD-101 to card_visa_4242"

    trace = await agent.process_ticket(ticket_text, task_scope=None, force_mode="synthetic")

    assert trace["boundary_verdict"] == PolicyVerdict.BLOCKED.value
    assert trace["executed"] is False
    assert trace["order_state"] is None
    assert trace["parsed_parameters"]["destination"] is None

    trace_copy = dict(trace)
    del trace_copy["ticket_text"]
    serialized = json.dumps(trace_copy)
    assert "card_visa_4242" not in serialized, "Raw payment destination leaked in trace JSON"

    assert len(spy_get_order) == 0, f"Unauthorized database read detected! Calls: {spy_get_order}"
    assert get_order(conn, "ORD-101")["refundable_amount"] == 25000


# =====================================================================
# 2. EXPIRED-SCOPE TESTS (ZERO DB READS & DATA MINIMIZATION)
# =====================================================================

@pytest.mark.asyncio
async def test_expired_scope_without_destination_blocks_and_zero_db_reads(agent_env, spy_get_order):
    """
    Ticket references valid order ORD-101 WITHOUT destination,
    supplied scope is expired. Must trigger ZERO get_order reads and return BLOCKED.
    """
    conn, agent = agent_env
    past_expiry = datetime.now(timezone.utc) - timedelta(minutes=15)
    expired_scope = TaskScope(
        scope_id="scope-expired-01",
        operator_id="operator_alice",
        order_id="ORD-101",
        allowed_action="refund_order",
        max_amount=5000,
        allowed_currency="USD",
        allowed_destination="card_visa_4242",
        expires_at=past_expiry
    )
    save_task_scope(conn, **expired_scope.model_dump(mode="json"))

    ticket_text = "Late delivery refund $40 for ORD-101"
    trace = await agent.process_ticket(ticket_text, task_scope=expired_scope, force_mode="synthetic")

    assert trace["boundary_verdict"] == PolicyVerdict.BLOCKED.value
    assert trace["executed"] is False
    assert trace["order_state"] is None
    assert trace["parsed_parameters"]["destination"] is None

    assert len(spy_get_order) == 0, f"Unauthorized database read on expired scope! Calls: {spy_get_order}"
    assert get_order(conn, "ORD-101")["refundable_amount"] == 25000


@pytest.mark.asyncio
async def test_expired_scope_with_destination_blocks_and_zero_db_reads(agent_env, spy_get_order):
    """
    Ticket references valid order ORD-101 WITH explicit destination,
    supplied scope is expired. Must trigger ZERO get_order reads and return BLOCKED.
    """
    conn, agent = agent_env
    past_expiry = datetime.now(timezone.utc) - timedelta(minutes=15)
    expired_scope = TaskScope(
        scope_id="scope-expired-02",
        operator_id="operator_alice",
        order_id="ORD-101",
        allowed_action="refund_order",
        max_amount=5000,
        allowed_currency="USD",
        allowed_destination="card_visa_4242",
        expires_at=past_expiry
    )
    save_task_scope(conn, **expired_scope.model_dump(mode="json"))

    ticket_text = "Late delivery refund $40 for ORD-101 to card_visa_4242"
    trace = await agent.process_ticket(ticket_text, task_scope=expired_scope, force_mode="synthetic")

    assert trace["boundary_verdict"] == PolicyVerdict.BLOCKED.value
    assert trace["executed"] is False
    assert trace["order_state"] is None
    assert trace["parsed_parameters"]["destination"] is None

    trace_copy = dict(trace)
    del trace_copy["ticket_text"]
    assert "card_visa_4242" not in json.dumps(trace_copy)

    assert len(spy_get_order) == 0, f"Unauthorized database read on expired scope! Calls: {spy_get_order}"


# =====================================================================
# 3. CROSS-ORDER TESTS (ZERO TARGET ORDER READS)
# =====================================================================

@pytest.mark.asyncio
async def test_cross_order_without_destination_blocks_and_zero_db_reads(agent_env, spy_get_order):
    """
    Scope is authorized for ORD-101, but ticket targets enterprise order ORD-104 WITHOUT destination.
    Must trigger ZERO get_order reads on ORD-104 and return BLOCKED.
    """
    conn, agent = agent_env
    future_expiry = datetime.now(timezone.utc) + timedelta(hours=2)
    scope_ord101 = TaskScope(
        scope_id="scope-valid-101",
        operator_id="operator_alice",
        order_id="ORD-101",
        allowed_action="refund_order",
        max_amount=5000,
        allowed_currency="USD",
        allowed_destination="card_visa_4242",
        expires_at=future_expiry
    )
    save_task_scope(conn, **scope_ord101.model_dump(mode="json"))

    ticket_text = "Please refund $40 for order ORD-104"
    trace = await agent.process_ticket(ticket_text, task_scope=scope_ord101, force_mode="synthetic")

    assert trace["boundary_verdict"] == PolicyVerdict.BLOCKED.value
    assert trace["executed"] is False
    assert trace["order_state"] is None
    assert trace["parsed_parameters"]["destination"] is None

    assert len(spy_get_order) == 0, f"Unauthorized read on cross-order target! Calls: {spy_get_order}"
    assert get_order(conn, "ORD-104")["refundable_amount"] == 500000


@pytest.mark.asyncio
async def test_cross_order_with_destination_blocks_and_zero_db_reads(agent_env, spy_get_order):
    """
    Scope is authorized for ORD-101, but rogue ticket targets enterprise order ORD-104 to wire_swift_chase.
    Must trigger ZERO get_order reads on ORD-104 and return BLOCKED.
    """
    conn, agent = agent_env
    future_expiry = datetime.now(timezone.utc) + timedelta(hours=2)
    scope_ord101 = TaskScope(
        scope_id="scope-valid-101",
        operator_id="operator_alice",
        order_id="ORD-101",
        allowed_action="refund_order",
        max_amount=5000,
        allowed_currency="USD",
        allowed_destination="card_visa_4242",
        expires_at=future_expiry
    )
    save_task_scope(conn, **scope_ord101.model_dump(mode="json"))

    ticket_text = "Refund $40 for ORD-104 to wire_swift_chase"
    trace = await agent.process_ticket(ticket_text, task_scope=scope_ord101, force_mode="synthetic")

    assert trace["boundary_verdict"] == PolicyVerdict.BLOCKED.value
    assert trace["executed"] is False
    assert trace["order_state"] is None
    assert trace["parsed_parameters"]["destination"] is None

    trace_copy = dict(trace)
    del trace_copy["ticket_text"]
    serialized = json.dumps(trace_copy)
    assert "wire_swift_chase" not in serialized
    assert "500000" not in serialized

    assert len(spy_get_order) == 0, f"Unauthorized read on cross-order target! Calls: {spy_get_order}"
    assert get_order(conn, "ORD-104")["refundable_amount"] == 500000


@pytest.mark.asyncio
async def test_unpersisted_scope_without_destination_blocks_and_zero_db_reads(agent_env, spy_get_order):
    """
    Client passes an unpersisted TaskScope object in memory (not in database).
    Must fail closed, return BLOCKED, and trigger ZERO get_order reads.
    """
    conn, agent = agent_env
    future_expiry = datetime.now(timezone.utc) + timedelta(hours=2)
    unpersisted_scope = TaskScope(
        scope_id="scope-ghost-999",
        operator_id="operator_untrusted",
        order_id="ORD-101",
        allowed_action="refund_order",
        max_amount=5000,
        allowed_currency="USD",
        allowed_destination="card_visa_4242",
        expires_at=future_expiry
    )
    # Notice: save_task_scope is NOT called! Scope does not exist in SQLite table.

    ticket_text = "Please refund $40 for order ORD-101"
    trace = await agent.process_ticket(ticket_text, task_scope=unpersisted_scope, force_mode="synthetic")

    assert trace["boundary_verdict"] == PolicyVerdict.BLOCKED.value
    assert trace["executed"] is False
    assert trace["order_state"] is None
    assert trace["parsed_parameters"]["destination"] is None

    assert len(spy_get_order) == 0, f"Unauthorized read on unpersisted scope! Calls: {spy_get_order}"


# =====================================================================
# 4. AUTHORIZED WORKFLOWS (AUTHORITATIVE DESTINATION ENRICHMENT)
# =====================================================================

@pytest.mark.asyncio
async def test_authorized_ticket_without_destination_enriches_authoritatively(agent_env, spy_get_order):
    """
    Legitimate ticket references ORD-101 WITHOUT destination.
    Valid active scope is persisted in database.
    Agent must verify scope first, then authoritatively enrich destination from order,
    and successfully execute the refund. Exactly ONE authorized get_order call permitted.
    """
    conn, agent = agent_env
    future_expiry = datetime.now(timezone.utc) + timedelta(hours=2)
    scope_ord101 = TaskScope(
        scope_id="scope-valid-101",
        operator_id="operator_alice",
        order_id="ORD-101",
        allowed_action="refund_order",
        max_amount=5000,
        allowed_currency="USD",
        allowed_destination="card_visa_4242",
        expires_at=future_expiry
    )
    save_task_scope(conn, **scope_ord101.model_dump(mode="json"))

    ticket_text = "Please refund $40 for order ORD-101"
    trace = await agent.process_ticket(ticket_text, task_scope=scope_ord101, force_mode="synthetic")

    # 1. Success verification
    assert trace["boundary_verdict"] == PolicyVerdict.ALLOWED.value
    assert trace["executed"] is True
    assert trace["refund"]["amount"] == 4000

    # 2. Authoritative destination enrichment verification
    assert trace["parsed_parameters"]["destination"] == "card_visa_4242"
    assert trace["order_state"] is not None
    assert trace["order_state"]["masked_destination"] == "card...4242"
    assert "original_destination" not in trace["order_state"]

    # 3. Exactly ONE authorized read of the database
    assert len(spy_get_order) == 1, f"Expected exactly 1 authorized read, got {len(spy_get_order)}"
    assert spy_get_order[0] == "ORD-101"

    # 4. Sandbox database mutated correctly
    assert get_order(conn, "ORD-101")["refundable_amount"] == 21000


@pytest.mark.asyncio
async def test_authorized_ticket_with_destination_preserves_workflow_with_minimization(agent_env, spy_get_order):
    """
    Authorized request matching valid scope with explicit destination succeeds.
    Preserves legitimate Agent Arena workflow while ensuring order_state uses masked destination.
    """
    conn, agent = agent_env
    future_expiry = datetime.now(timezone.utc) + timedelta(hours=2)
    scope_ord101 = TaskScope(
        scope_id="scope-valid-101",
        operator_id="operator_alice",
        order_id="ORD-101",
        allowed_action="refund_order",
        max_amount=5000,
        allowed_currency="USD",
        allowed_destination="card_visa_4242",
        expires_at=future_expiry
    )
    save_task_scope(conn, **scope_ord101.model_dump(mode="json"))

    ticket_text = "Refund $40 for ORD-101 to card_visa_4242"
    trace = await agent.process_ticket(ticket_text, task_scope=scope_ord101, force_mode="synthetic")

    assert trace["boundary_verdict"] == PolicyVerdict.ALLOWED.value
    assert trace["executed"] is True
    assert trace["refund"]["amount"] == 4000
    assert trace["parsed_parameters"]["destination"] == "card_visa_4242"
    assert trace["order_state"]["masked_destination"] == "card...4242"

    assert len(spy_get_order) == 1
    assert spy_get_order[0] == "ORD-101"


# =====================================================================
# 5. LLM GENERIC ORIGINAL DESTINATION PROPOSALS
# =====================================================================

@pytest.mark.asyncio
async def test_llm_generic_destination_without_scope_zero_db_reads(agent_env, monkeypatch, spy_get_order):
    """
    LLM proposes a generic destination ('original payment card').
    When NO scope is supplied, parser and agent must trigger ZERO get_order reads,
    and return BLOCKED.
    """
    from google import genai
    conn, agent = agent_env

    def mock_generate_generic(**kwargs):
        return SimpleNamespace(
            function_calls=[
                SimpleNamespace(
                    name="refund_order",
                    args={
                        "order_id": "ORD-101",
                        "currency": "USD",
                        "amount_minor": 4000,
                        "destination": "original payment card"
                    }
                )
            ]
        )

    monkeypatch.setattr(genai, "Client", lambda **kwargs: SimpleNamespace(
        models=SimpleNamespace(generate_content=mock_generate_generic)
    ))

    ticket_text = "I would like a refund of $40 for order ORD-101 to my original card please"
    trace = await agent.process_ticket(ticket_text, task_scope=None, api_key="mock_key")

    assert trace["boundary_verdict"] == PolicyVerdict.BLOCKED.value
    assert trace["executed"] is False
    assert trace["order_state"] is None
    assert trace["parsed_parameters"]["destination"] is None

    # Assert ZERO database reads of protected order state
    assert len(spy_get_order) == 0, f"Unauthorized read on no-scope LLM proposal! Calls: {spy_get_order}"


@pytest.mark.asyncio
async def test_llm_generic_destination_with_authorized_scope_enriches_and_allows(agent_env, monkeypatch, spy_get_order):
    """
    LLM proposes a generic destination ('original payment card').
    When a valid scope is authorized, agent must verify scope first, enrich destination,
    and successfully execute the refund with exactly ONE authorized get_order read.
    """
    from google import genai
    conn, agent = agent_env

    future_expiry = datetime.now(timezone.utc) + timedelta(hours=2)
    scope_ord101 = TaskScope(
        scope_id="scope-valid-101",
        operator_id="operator_alice",
        order_id="ORD-101",
        allowed_action="refund_order",
        max_amount=5000,
        allowed_currency="USD",
        allowed_destination="card_visa_4242",
        expires_at=future_expiry
    )
    save_task_scope(conn, **scope_ord101.model_dump(mode="json"))

    def mock_generate_generic(**kwargs):
        return SimpleNamespace(
            function_calls=[
                SimpleNamespace(
                    name="refund_order",
                    args={
                        "order_id": "ORD-101",
                        "currency": "USD",
                        "amount_minor": 4000,
                        "destination": "original payment card"
                    }
                )
            ]
        )

    monkeypatch.setattr(genai, "Client", lambda **kwargs: SimpleNamespace(
        models=SimpleNamespace(generate_content=mock_generate_generic)
    ))

    ticket_text = "Refund $40 for ORD-101 to original card"
    trace = await agent.process_ticket(ticket_text, task_scope=scope_ord101, api_key="mock_key")

    assert trace["boundary_verdict"] == PolicyVerdict.ALLOWED.value
    assert trace["executed"] is True
    assert trace["refund"]["amount"] == 4000
    assert trace["parsed_parameters"]["destination"] == "card_visa_4242"
    assert trace["order_state"]["masked_destination"] == "card...4242"

    assert len(spy_get_order) == 1, f"Expected exactly 1 authorized read, got {len(spy_get_order)}"
    assert spy_get_order[0] == "ORD-101"
    assert get_order(conn, "ORD-101")["refundable_amount"] == 21000


@pytest.mark.asyncio
async def test_llm_bengali_generic_destination_with_authorized_scope(agent_env, monkeypatch, spy_get_order):
    """
    LLM proposes a Bengali generic destination ('আগের বিকাশ একাউন্টে').
    When a valid scope is authorized for ORD-103, agent enriches destination to bkash_01711000000.
    """
    from google import genai
    conn, agent = agent_env

    future_expiry = datetime.now(timezone.utc) + timedelta(hours=2)
    scope_ord103 = TaskScope(
        scope_id="scope-valid-103",
        operator_id="operator_alice",
        order_id="ORD-103",
        allowed_action="refund_order",
        max_amount=10000,
        allowed_currency="BDT",
        allowed_destination="bkash_01711000000",
        expires_at=future_expiry
    )
    save_task_scope(conn, **scope_ord103.model_dump(mode="json"))

    def mock_generate_bengali(**kwargs):
        return SimpleNamespace(
            function_calls=[
                SimpleNamespace(
                    name="refund_order",
                    args={
                        "order_id": "ORD-103",
                        "currency": "BDT",
                        "amount_minor": 5000,
                        "destination": "আগের বিকাশ একাউন্টে"
                    }
                )
            ]
        )

    monkeypatch.setattr(genai, "Client", lambda **kwargs: SimpleNamespace(
        models=SimpleNamespace(generate_content=mock_generate_bengali)
    ))

    ticket_text = "ORD-103 ৫০ টাকা রিফান্ড দিন"
    trace = await agent.process_ticket(ticket_text, task_scope=scope_ord103, api_key="mock_key")

    assert trace["boundary_verdict"] == PolicyVerdict.ALLOWED.value
    assert trace["executed"] is True
    assert trace["parsed_parameters"]["destination"] == "bkash_01711000000"
    assert trace["order_state"]["masked_destination"] == "bkas...0000"

    assert len(spy_get_order) == 1
    assert spy_get_order[0] == "ORD-103"


# =====================================================================
# 6. DIRECT PARSER ISOLATION (ZERO DB READS BY PARSERS ALONE)
# =====================================================================

def test_parser_methods_never_call_get_order_directly(agent_env, monkeypatch, spy_get_order):
    """
    Directly invokes parser methods on tickets with and without explicit destinations.
    Parsers alone MUST NEVER query get_order() under any circumstance.
    """
    from google import genai
    conn, agent = agent_env

    # 1. Synthetic English ticket without destination
    p1 = agent._parse_ticket_synthetic("Please refund $40 for order ORD-101")
    assert p1["order_id"] == "ORD-101"
    assert p1["amount"] == 4000
    assert p1["destination"] is None
    assert len(spy_get_order) == 0

    # 2. Synthetic Bengali ticket without destination
    p2 = agent._parse_ticket_synthetic("আমার অর্ডার ORD-103 এর রিফান্ড ৫০ টাকা দিন")
    assert p2["order_id"] == "ORD-103"
    assert p2["amount"] == 5000
    assert p2["destination"] is None
    assert len(spy_get_order) == 0

    # 3. Synthetic ticket with generic destination text
    p3 = agent._parse_ticket_synthetic("Please refund $40 for order ORD-101 to my card")
    assert p3["destination"] is None
    assert len(spy_get_order) == 0

    # 4. LLM parser with generic destination
    def mock_generate_generic(**kwargs):
        return SimpleNamespace(
            function_calls=[
                SimpleNamespace(
                    name="refund_order",
                    args={
                        "order_id": "ORD-101",
                        "currency": "USD",
                        "amount_minor": 4000,
                        "destination": "original payment card"
                    }
                )
            ]
        )

    monkeypatch.setattr(genai, "Client", lambda **kwargs: SimpleNamespace(
        models=SimpleNamespace(generate_content=mock_generate_generic)
    ))

    p4 = agent._parse_ticket_llm("Refund $40 for ORD-101", api_key="dummy")
    assert p4["destination"] is None
    assert len(spy_get_order) == 0, f"Parser alone called get_order! Calls: {spy_get_order}"
