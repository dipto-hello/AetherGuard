"""Sandbox API Routes for Orders, Refunds, and Reset"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
import json
import uuid
from app.sandbox.db import get_connection, init_db
from app.sandbox.exchange_rate import get_display_quote
from app.sandbox.service import (
    get_order,
    list_orders,
    list_refunds,
    reset_synthetic_data,
)

router = APIRouter(prefix="/api/sandbox", tags=["Sandbox"])

# Ensure DB initialized on module import
init_db()

class UpdatePaidAmount(BaseModel):
    paid_amount: int = Field(strict=True, gt=0, le=999_999_999_999)
    expected_paid_amount: int = Field(strict=True, gt=0, le=2**53 - 1)
    expected_refundable_amount: int = Field(strict=True, ge=0, le=2**53 - 1)


@router.patch("/orders/{order_id}")
def update_paid_amount(order_id: str, req: UpdatePaidAmount):
    conn = get_connection()
    try:
        with conn:
            conn.execute("BEGIN IMMEDIATE")
            order = get_order(conn, order_id)
            if order is None:
                raise HTTPException(404, detail="Order not found.")
            paid, remaining = order["paid_amount"], order["refundable_amount"]
            if (paid, remaining) != (req.expected_paid_amount, req.expected_refundable_amount):
                raise HTTPException(409, detail="The order changed. Refresh and reopen the editor.")
            refunded = paid - remaining
            if req.paid_amount < refunded:
                raise HTTPException(422, detail="Paid total cannot be below the amount already refunded.")
            if req.paid_amount == paid:
                return {"order": order}
            new_remaining = req.paid_amount - refunded
            status = "paid" if not refunded else "partially_refunded" if new_remaining else "fully_refunded"
            conn.execute(
                "UPDATE orders SET paid_amount = ?, refundable_amount = ?, status = ? WHERE id = ?",
                (req.paid_amount, new_remaining, status, order_id),
            )
            conn.execute(
                """INSERT INTO audit_events (id, tool, verdict, reason, details)
                   VALUES (?, 'sandbox', 'ORDER_BALANCE_UPDATED', ?, ?)""",
                (f"audit_{uuid.uuid4().hex}", f"Updated paid total for {order_id} ({order['currency']})",
                 json.dumps({"order_id": order_id, "currency": order["currency"], "old_paid": paid,
                             "new_paid": req.paid_amount, "old_remaining": remaining, "new_remaining": new_remaining})),
            )
            return {"order": get_order(conn, order_id)}
    finally:
        conn.close()

@router.get("/exchange-rate")
def get_exchange_rate():
    return get_display_quote()

@router.get("/orders")
def get_all_orders():
    """List all synthetic orders in the sandbox."""
    conn = get_connection()
    try:
        orders = list_orders(conn)
        return {"orders": orders}
    finally:
        conn.close()

@router.get("/orders/{order_id}")
def get_order_by_id(order_id: str):
    """Get single synthetic order details."""
    conn = get_connection()
    try:
        order = get_order(conn, order_id)
        if not order:
            raise HTTPException(
                status_code=404,
                detail={"code": "ORDER_NOT_FOUND", "message": f"Order {order_id} does not exist in sandbox"}
            )
        return {"order": order}
    finally:
        conn.close()

@router.get("/refunds")
def get_all_refunds(order_id: Optional[str] = None):
    """List executed refunds in the sandbox."""
    conn = get_connection()
    try:
        refunds = list_refunds(conn, order_id)
        return {"refunds": refunds}
    finally:
        conn.close()

@router.post("/reset")
def reset_sandbox():
    """Reset all synthetic orders and clear sandbox refunds."""
    conn = get_connection()
    try:
        with conn:
            conn.execute('BEGIN IMMEDIATE')
            reset_synthetic_data(conn)
            conn.execute("INSERT INTO audit_events (id, tool, verdict, reason) VALUES (?, 'sandbox', 'SANDBOX_RESET', ?)",
                         (f'audit_{uuid.uuid4().hex}', 'Synthetic sandbox reset by demo operator'))
        return {"status": "success", "message": "Sandbox synthetic data successfully restored to baseline"}
    finally:
        conn.close()
