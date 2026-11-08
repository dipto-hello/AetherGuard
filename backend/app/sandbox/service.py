"""Synthetic Sandbox Data Service & Execution Engine"""
import sqlite3
import uuid
from contextlib import nullcontext
from typing import Optional, Dict, Any, List
from .db import DEFAULT_SYNTHETIC_ORDERS

class SandboxError(Exception):
    """Base exception for sandbox operations"""
    pass

class OrderNotFoundError(SandboxError):
    pass

class InsufficientBalanceError(SandboxError):
    pass

class DestinationMismatchError(SandboxError):
    pass

class DuplicateIdempotencyError(SandboxError):
    pass

def reset_synthetic_data(conn: sqlite3.Connection) -> None:
    """Safely reset ONLY the synthetic sandbox data to its initial baseline."""
    with nullcontext() if conn.in_transaction else conn:
        conn.execute("UPDATE pending_actions SET status = 'expired' WHERE status = 'pending';")
        conn.execute("DELETE FROM task_scopes;")
        conn.execute("DELETE FROM refunds;")
        conn.execute("DELETE FROM orders;")
        for order in DEFAULT_SYNTHETIC_ORDERS:
            conn.execute(
                """
                INSERT INTO orders (id, customer_name, currency, paid_amount, refundable_amount, original_destination, status)
                VALUES (:id, :customer_name, :currency, :paid_amount, :refundable_amount, :original_destination, :status);
                """,
                order
            )

def get_order(conn: sqlite3.Connection, order_id: str) -> Optional[Dict[str, Any]]:
    """Look up an order by ID."""
    cur = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    row = cur.fetchone()
    if not row:
        return None
    return dict(row)

def list_orders(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """List all synthetic orders."""
    cur = conn.execute("SELECT * FROM orders ORDER BY id ASC")
    return [dict(row) for row in cur.fetchall()]

def list_refunds(conn: sqlite3.Connection, order_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """List all executed refunds, optionally filtered by order_id."""
    if order_id:
        cur = conn.execute("SELECT * FROM refunds WHERE order_id = ? ORDER BY created_at DESC", (order_id,))
    else:
        cur = conn.execute("SELECT * FROM refunds ORDER BY created_at DESC")
    return [dict(row) for row in cur.fetchall()]


def scope_refunded_amount(conn: sqlite3.Connection, scope_id: str) -> int:
    row = conn.execute(
        """SELECT COALESCE(SUM(refunds.amount), 0) FROM refunds
           JOIN action_requests ON refunds.action_id = action_requests.action_id
           WHERE action_requests.scope_id = ? AND refunds.status = 'succeeded'""",
        (scope_id,),
    ).fetchone()
    return row[0]

def save_task_scope(
    conn: sqlite3.Connection,
    scope_id: str,
    operator_id: str,
    order_id: str,
    allowed_action: str,
    max_amount: int,
    allowed_currency: str,
    allowed_destination: str,
    expires_at: str
) -> Dict[str, Any]:
    """Persist an operator-authorized task scope."""
    with conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO task_scopes (scope_id, operator_id, order_id, allowed_action, max_amount, allowed_currency, allowed_destination, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (scope_id, operator_id, order_id, allowed_action, max_amount, allowed_currency, allowed_destination, expires_at)
        )
    return get_task_scope(conn, scope_id)

def get_task_scope(conn: sqlite3.Connection, scope_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a task scope by ID."""
    cur = conn.execute("SELECT * FROM task_scopes WHERE scope_id = ?", (scope_id,))
    row = cur.fetchone()
    if not row:
        return None
    return dict(row)

def execute_sandbox_refund(
    conn: sqlite3.Connection,
    order_id: str,
    amount: int,
    currency: str,
    destination: str,
    idempotency_key: str,
    action_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Atomically execute a refund against synthetic order state.
    Strictly verifies:
    - Amount > 0
    - Order existence
    - Currency match
    - Sufficient refundable balance
    - Destination match with original_destination
    - Idempotency key (returns existing record without double deduction)
    """
    if amount <= 0:
        raise SandboxError(f"Refund amount must be positive integer minor units, got {amount}")

    # Check idempotency first
    cur = conn.execute("SELECT * FROM refunds WHERE idempotency_key = ?", (idempotency_key,))
    existing = cur.fetchone()
    if existing:
        if any(existing[key] != value for key, value in (
            ("order_id", order_id), ("amount", amount), ("currency", currency),
            ("destination", destination), ("action_id", action_id)
        )):
            raise DuplicateIdempotencyError("Idempotency key was already used for a different refund")
        return dict(existing)

    # Begin atomic transaction
    with nullcontext() if conn.in_transaction else conn:
        cur = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
        order_row = cur.fetchone()
        if not order_row:
            raise OrderNotFoundError(f"Order {order_id} not found in sandbox")

        order = dict(order_row)

        if order["currency"] != currency:
            raise SandboxError(f"Currency mismatch: expected {order['currency']}, got {currency}")

        if destination != order["original_destination"]:
            raise DestinationMismatchError(
                f"Destination mismatch: cannot refund to {destination}; original is {order['original_destination']}"
            )

        if amount > order["refundable_amount"]:
            raise InsufficientBalanceError(
                f"Requested amount {amount} exceeds refundable balance {order['refundable_amount']}"
            )

        cursor = conn.execute(
            """
            UPDATE orders
            SET refundable_amount = refundable_amount - ?,
                status = CASE WHEN refundable_amount = ? THEN 'fully_refunded' ELSE 'partially_refunded' END
            WHERE id = ? AND refundable_amount >= ?
            """,
            (amount, amount, order_id, amount)
        )
        if cursor.rowcount != 1:
            raise InsufficientBalanceError("Refund exceeds current refundable balance")

        refund_id = f"ref_{uuid.uuid4().hex[:12]}"
        conn.execute(
            """
            INSERT INTO refunds (id, order_id, amount, currency, destination, idempotency_key, action_id, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'succeeded')
            """,
            (refund_id, order_id, amount, currency, destination, idempotency_key, action_id)
        )

        cur = conn.execute("SELECT * FROM refunds WHERE id = ?", (refund_id,))
        return dict(cur.fetchone())
