"""Sandbox API Routes for Orders, Refunds, and Reset"""
from fastapi import APIRouter, HTTPException
from typing import Optional
import uuid
from app.sandbox.db import get_connection, init_db
from app.sandbox.service import (
    get_order,
    list_orders,
    list_refunds,
    reset_synthetic_data,
)

router = APIRouter(prefix="/api/sandbox", tags=["Sandbox"])

# Ensure DB initialized on module import
init_db()

@router.get("/orders")
async def get_all_orders():
    """List all synthetic orders in the sandbox."""
    conn = get_connection()
    try:
        orders = list_orders(conn)
        return {"orders": orders}
    finally:
        conn.close()

@router.get("/orders/{order_id}")
async def get_order_by_id(order_id: str):
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
async def get_all_refunds(order_id: Optional[str] = None):
    """List executed refunds in the sandbox."""
    conn = get_connection()
    try:
        refunds = list_refunds(conn, order_id)
        return {"refunds": refunds}
    finally:
        conn.close()

@router.post("/reset")
async def reset_sandbox():
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
