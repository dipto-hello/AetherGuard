"""AetherGuard Governed MCP Server using official Model Context Protocol SDK"""
import json
import sqlite3
import uuid
import os
from threading import RLock
from typing import Optional, Dict, Any
import mcp.types as types
from mcp.server.mcpserver import MCPServer
from app.governance.boundary import GovernanceBoundary
from app.sandbox.service import get_order, get_task_scope, DuplicateIdempotencyError
from app.policy.models import TaskScope
from app.policy.storage import load_policy


def _error(code: str) -> types.CallToolResult:
    return types.CallToolResult(is_error=True, content=[types.TextContent(type="text", text=json.dumps({"error": code}))])


def create_governed_mcp_server(
    conn: sqlite3.Connection,
    boundary: Optional[GovernanceBoundary] = None,
    authenticated_caller: Optional[str] = None,
    *,
    require_refund_approval: bool = False,
) -> MCPServer:
    """
    Factory creating an MCP Server whose tool calls are governed by AetherGuard.
    Enforces Zero-Trust caller authentication, scope authorization, and data minimization.
    """
    gov_boundary = boundary or GovernanceBoundary(conn)
    connection_lock = RLock()
    server = MCPServer("aetherguard-governance-mesh")
    # Resolve server-verified principal: explicit argument or verified environment binding
    trusted_principal = authenticated_caller or os.environ.get("AETHERGUARD_AUTHENTICATED_OPERATOR")

    def audit(tool: str, verdict: str, reason: str, details: Dict[str, Any]) -> None:
        with conn:
            conn.execute(
                "INSERT INTO audit_events (id, action_id, tool, verdict, reason, fingerprint, details) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (f"audit_{uuid.uuid4().hex[:12]}", f"act_{uuid.uuid4().hex}", tool, verdict, reason, "", json.dumps(details)),
            )

    def deny(tool: str, reason: str, code: str, details: Dict[str, Any]) -> types.CallToolResult:
        try:
            audit(tool, "BLOCKED", reason, details)
        except Exception:
            pass  # The call is refused either way; a failed block audit must not turn into success.
        return _error(code)

    def check_policy(tool: str, order_id: str) -> tuple:
        """Return (policy, None) or (policy, refusal); fails closed when the policy is missing or disallows the tool."""
        policy = load_policy(conn)
        if not policy:
            return policy, deny(tool, "FAIL_CLOSED: Policy configuration unavailable or corrupt", "POLICY_UNAVAILABLE", {"order_id": order_id})
        if tool not in policy.allowed_tools:
            return policy, deny(tool, f"UNKNOWN_TOOL: Tool '{tool}' is not in policy allowlist", "TOOL_NOT_ALLOWED", {"order_id": order_id})
        return policy, None

    def check_scope(tool: str, order_id: str, scope_id: Optional[str], caller_id: Optional[str],
                    scoped_order_only: bool) -> tuple:
        """Return (stored scope, None) or (None, refusal). Scope possession alone does not grant authority."""
        if not scope_id:
            noun = "lookup" if tool == "lookup_order" else "refund"
            return None, deny(tool, f"OUTSIDE_TRUSTED_TASK_SCOPE: Scope ID required for {noun}", "SCOPE_ID_REQUIRED", {"order_id": order_id})
        details = {"order_id": order_id, "scope_id": scope_id}
        raw_scope = get_task_scope(conn, scope_id)
        if not raw_scope or TaskScope(**raw_scope).is_expired():
            return None, deny(tool, "TASK_SCOPE_EXPIRED", "TASK_SCOPE_EXPIRED", details)
        if scoped_order_only and raw_scope["order_id"] != order_id:
            return None, deny(tool, f"OUTSIDE_TRUSTED_TASK_SCOPE: Scope authorized order '{raw_scope['order_id']}', attempted '{order_id}'",
                              "OUTSIDE_TRUSTED_TASK_SCOPE", details)
        # Untrusted client parameter 'caller_id' is NEVER accepted as authentication.
        expected_operator = raw_scope.get("operator_id")
        if expected_operator:
            details = {**details, "caller_id": caller_id, "authenticated_caller": trusted_principal}
            if not trusted_principal:
                reason = f"OUTSIDE_TRUSTED_TASK_SCOPE: Anonymous/unauthenticated caller cannot access scope bound to operator '{expected_operator}'"
            elif trusted_principal != expected_operator:
                reason = f"OUTSIDE_TRUSTED_TASK_SCOPE: Scope operator '{expected_operator}' does not match authenticated principal '{trusted_principal}'"
            elif caller_id and caller_id != trusted_principal:
                reason = f"OUTSIDE_TRUSTED_TASK_SCOPE: Client parameter caller_id '{caller_id}' does not match authenticated principal '{trusted_principal}'"
            else:
                reason = None
            if reason:
                return None, deny(tool, reason, "CALLER_IDENTITY_MISMATCH", details)
        return raw_scope, None

    @server.tool(
        name="lookup_order",
        description="Lookup synthetic order balance, status and masked destination subject to task scope."
    )
    def lookup_order(
        order_id: str,
        scope_id: Optional[str] = None,
        caller_id: Optional[str] = None
    ) -> types.CallToolResult:
        with connection_lock:
            policy, refusal = check_policy("lookup_order", order_id)
            if refusal:
                return refusal
            if policy.enforce_task_scope:
                _, refusal = check_scope("lookup_order", order_id, scope_id, caller_id, scoped_order_only=True)
                if refusal:
                    return refusal

            order = get_order(conn, order_id)
            if not order:
                return deny("lookup_order", f"Order {order_id} not found in sandbox",
                            "ORDER_NOT_FOUND", {"order_id": order_id})

            # FAIL-CLOSED: never return data if the audit insert fails.
            try:
                audit("lookup_order", "ALLOWED", "Order lookup succeeded", {"order_id": order_id})
            except Exception:
                return _error("AUDIT_LOGGING_FAILED")

            # Minimized Data Delivery: Zero Customer PII & Masked Destination Only
            dest = order["original_destination"]
            masked_dest = dest if len(dest) <= 8 else f"{dest[:4]}...{dest[-4:]}"
            return types.CallToolResult(
                is_error=False,
                content=[types.TextContent(type="text", text=json.dumps({
                    "order_id": order["id"],
                    "currency": order["currency"],
                    "paid_amount": order["paid_amount"],
                    "refundable_amount": order["refundable_amount"],
                    "masked_destination": masked_dest,
                    "status": order["status"]
                }))]
            )

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
        idempotency_key: Optional[str] = None,
        caller_id: Optional[str] = None
    ) -> types.CallToolResult:
        with connection_lock:
            policy, refusal = check_policy("refund_order", order_id)
            if refusal:
                return refusal

            if not idempotency_key or not idempotency_key.strip() or len(idempotency_key) > 128:
                return _error("IDEMPOTENCY_KEY_REQUIRED")

            task_scope = None
            if policy.enforce_task_scope:
                raw_scope, refusal = check_scope("refund_order", order_id, scope_id, caller_id, scoped_order_only=False)
                if refusal:
                    return refusal
                task_scope = TaskScope(**raw_scope)

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
                evaluation = gov_boundary.intercept_and_evaluate(
                    action_payload, task_scope=task_scope, require_refund_approval=require_refund_approval,
                )
            except DuplicateIdempotencyError:
                return _error("IDEMPOTENCY_KEY_REUSED")
            except sqlite3.Error:
                return _error("AUDIT_LOGGING_FAILED")
            except Exception:
                return _error("INTERNAL_ERROR")

            return types.CallToolResult(
                is_error=False,
                content=[types.TextContent(type="text", text=json.dumps(evaluation))]
            )

    return server
