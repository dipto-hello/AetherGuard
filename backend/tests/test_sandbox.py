import pytest
from app.sandbox.db import init_db, get_connection
from app.sandbox.service import (
    reset_synthetic_data,
    get_order,
    execute_sandbox_refund,
    SandboxError,
    OrderNotFoundError,
    InsufficientBalanceError,
    DestinationMismatchError,
    DuplicateIdempotencyError
)

@pytest.fixture(autouse=True)
def setup_database():
    # Use in-memory SQLite database for clean test isolation
    conn = init_db(":memory:")
    reset_synthetic_data(conn)
    yield conn
    conn.close()

def test_initial_synthetic_orders_seeded(setup_database):
    conn = setup_database
    order = get_order(conn, "ORD-101")
    assert order is not None
    assert order["id"] == "ORD-101"
    assert order["paid_amount"] == 25000  # $250.00
    assert order["refundable_amount"] == 25000
    assert order["currency"] == "USD"
    assert order["original_destination"] == "card_visa_4242"
    assert order["status"] == "paid"

def test_valid_refund_persists_once_and_updates_balance(setup_database):
    conn = setup_database
    refund = execute_sandbox_refund(
        conn=conn,
        order_id="ORD-101",
        amount=5000,  # $50.00
        currency="USD",
        destination="card_visa_4242",
        idempotency_key="idemp-test-001",
        action_id="act-001"
    )
    assert refund["id"] is not None
    assert refund["amount"] == 5000
    assert refund["status"] == "succeeded"

    # Verify order state updated atomically
    order = get_order(conn, "ORD-101")
    assert order["refundable_amount"] == 20000  # $200.00 remaining
    assert order["status"] == "partially_refunded"

def test_idempotent_refund_does_not_deduct_twice(setup_database):
    conn = setup_database
    refund1 = execute_sandbox_refund(
        conn=conn,
        order_id="ORD-101",
        amount=5000,
        currency="USD",
        destination="card_visa_4242",
        idempotency_key="idemp-test-002",
        action_id="act-002"
    )
    refund2 = execute_sandbox_refund(
        conn=conn,
        order_id="ORD-101",
        amount=5000,
        currency="USD",
        destination="card_visa_4242",
        idempotency_key="idemp-test-002",
        action_id="act-002"
    )
    assert refund1["id"] == refund2["id"]

    # Balance must only be deducted once ($250 - $50 = $200)
    order = get_order(conn, "ORD-101")
    assert order["refundable_amount"] == 20000

def test_reject_nonexistent_order(setup_database):
    conn = setup_database
    with pytest.raises(OrderNotFoundError):
        execute_sandbox_refund(
            conn=conn,
            order_id="ORD-999-DOES-NOT-EXIST",
            amount=1000,
            currency="USD",
            destination="card_visa_4242",
            idempotency_key="idemp-test-003",
            action_id="act-003"
        )

def test_reject_excess_amount(setup_database):
    conn = setup_database
    with pytest.raises(InsufficientBalanceError):
        execute_sandbox_refund(
            conn=conn,
            order_id="ORD-101",
            amount=30000,  # $300.00 > $250.00 balance
            currency="USD",
            destination="card_visa_4242",
            idempotency_key="idemp-test-004",
            action_id="act-004"
        )

def test_reject_destination_mismatch(setup_database):
    conn = setup_database
    with pytest.raises(DestinationMismatchError):
        execute_sandbox_refund(
            conn=conn,
            order_id="ORD-101",
            amount=5000,
            currency="USD",
            destination="attacker_crypto_wallet",
            idempotency_key="idemp-test-005",
            action_id="act-005"
        )

def test_safe_reset_restores_synthetic_data_cleanly(setup_database):
    conn = setup_database
    # Make a refund first
    execute_sandbox_refund(
        conn=conn,
        order_id="ORD-101",
        amount=25000,
        currency="USD",
        destination="card_visa_4242",
        idempotency_key="idemp-test-006",
        action_id="act-006"
    )
    order = get_order(conn, "ORD-101")
    assert order["refundable_amount"] == 0
    assert order["status"] == "fully_refunded"

    # Reset
    reset_synthetic_data(conn)

    # Restored
    reset_order = get_order(conn, "ORD-101")
    assert reset_order["refundable_amount"] == 25000
    assert reset_order["status"] == "paid"
