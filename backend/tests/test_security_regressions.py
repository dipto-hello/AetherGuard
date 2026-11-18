from datetime import datetime, timedelta, timezone

import pytest

from app.policy.engine import evaluate_policy
from app.policy.models import PolicyConfig, PolicyVerdict, TaskScope
from app.sandbox.db import init_db
from app.sandbox.service import (
    DuplicateIdempotencyError,
    execute_sandbox_refund,
    get_order,
    reset_synthetic_data,
)


@pytest.fixture
def scope():
    return TaskScope(
        scope_id="scope-test", operator_id="operator", order_id="ORD-101",
        allowed_action="refund_order", max_amount=500000, allowed_currency="BDT",
        allowed_destination="card_visa_4242",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )


@pytest.fixture
def sandbox():
    conn = init_db(":memory:")
    reset_synthetic_data(conn)
    yield conn
    conn.close()


@pytest.mark.parametrize("field,value", [
    ("allowed_currency", "USD"),
    ("allowed_destination", "different_destination"),
])
def test_scope_constraints_are_enforced(sandbox, scope, field, value):
    setattr(scope, field, value)
    verdict, _ = evaluate_policy(
        "refund_order",
        {"order_id": "ORD-101", "amount": 100000, "currency": "BDT", "destination": "card_visa_4242"},
        get_order(sandbox, "ORD-101"), scope, PolicyConfig(),
    )
    assert verdict == PolicyVerdict.BLOCKED
    assert get_order(sandbox, "ORD-101")["refundable_amount"] == 2500000


@pytest.mark.parametrize("amount", [True, 1000.5, "100000"])
def test_amount_must_be_an_integer_minor_unit(sandbox, scope, amount):
    verdict, _ = evaluate_policy(
        "refund_order",
        {"order_id": "ORD-101", "amount": amount, "currency": "BDT", "destination": "card_visa_4242"},
        get_order(sandbox, "ORD-101"), scope, PolicyConfig(),
    )
    assert verdict == PolicyVerdict.BLOCKED


def test_reused_key_with_different_payload_is_rejected(sandbox):
    execute_sandbox_refund(sandbox, "ORD-101", 100000, "BDT", "card_visa_4242", "same-key")
    with pytest.raises(DuplicateIdempotencyError):
        execute_sandbox_refund(sandbox, "ORD-101", 200000, "BDT", "card_visa_4242", "same-key")
    assert get_order(sandbox, "ORD-101")["refundable_amount"] == 2400000


def test_allowlist_cannot_authorize_unimplemented_tool(sandbox, scope):
    policy = PolicyConfig(allowed_tools=["unimplemented_tool"])
    verdict, _ = evaluate_policy("unimplemented_tool", {}, None, scope, policy)
    assert verdict == PolicyVerdict.BLOCKED
