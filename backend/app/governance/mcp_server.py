"""AetherGuard Governed MCP Server using official Model Context Protocol SDK"""
import json
import sqlite3
from threading import RLock
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from mcp.server.mcpserver import MCPServer
from app.governance.boundary import GovernanceBoundary
from app.sandbox.service import get_order, get_task_scope, DuplicateIdempotencyError
from app.policy.models import TaskScope

def create_governed_mcp_server(conn: sqlite3.Connection, boundary: Optional[GovernanceBoundary] = None) -> MCPServer:
    """
    Factory creating an MCP Server whose tool calls are governed by AetherGuard.
    """
    gov_boundary = boundary or GovernanceBoundary(conn)
    connection_lock = RLock()
    server = MCPServer("aetherguard-governance-mesh")

    @server.tool(
        name="lookup_order",
        description="Lookup synthetic order balance, status and original destination."
    )
    def lookup_order(order_id: str) -> str:
        with connection_lock:
            order = get_order(conn, order_id)
            if not order:
                return json.dumps({"error": f"Order {order_id} not found in sandbox"})
            return json.dumps({
                "order_id": order["id"],
                "customer_name": order["customer_name"],
                "currency": order["currency"],
                "paid_amount": order["paid_amount"],
                "refundable_amount": order["refundable_amount"],
                "original_destination": order["original_destination"],
                "status": order["status"]
            })

    @server.tool(
        name="refund_order",
        description="Propose a customer refund. Subject to AetherGuard zero-trust policy and task scope."
    )
    def refund_order(
        order_id: str,
        amount: int,
        currency: str,
        destination: str,
        reason: str,
        scope_id: Optional[str] = None,
        idempotency_key: Optional[str] = None
    ) -> str:
        with connection_lock:
            if not idempotency_key or not idempotency_key.strip() or len(idempotency_key) > 128:
                return json.dumps({"error": "IDEMPOTENCY_KEY_REQUIRED"})
            # Load task scope if provided
            task_scope = None
            if scope_id:
                raw_scope = get_task_scope(conn, scope_id)
                if raw_scope:
                    task_scope = TaskScope(
                        scope_id=raw_scope["scope_id"],
                        operator_id=raw_scope["operator_id"],
                        order_id=raw_scope["order_id"],
                        allowed_action=raw_scope["allowed_action"],
                        max_amount=raw_scope["max_amount"],
                        allowed_currency=raw_scope["allowed_currency"],
                        allowed_destination=raw_scope["allowed_destination"],
                        expires_at=datetime.fromisoformat(raw_scope["expires_at"])
                    )

            action_payload = {
                "tool": "refund_order",
                "idempotency_key": idempotency_key,
                "arguments": {
                    "order_id": order_id,
                    "amount": amount,
                    "currency": currency,
                    "destination": destination,
                    "reason": reason
                }
            }

            # Route through zero-trust governance boundary
            try:
                evaluation = gov_boundary.intercept_and_evaluate(action_payload, task_scope=task_scope)
            except DuplicateIdempotencyError:
                return json.dumps({"error": "IDEMPOTENCY_KEY_REUSED"})
            return json.dumps(evaluation)

    return server
