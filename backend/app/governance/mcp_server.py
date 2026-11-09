"""AetherGuard Governed MCP Server using official Model Context Protocol SDK"""
import json
import sqlite3
import uuid
import os
from threading import RLock
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import mcp.types as types
from mcp.server.mcpserver import MCPServer
from app.governance.boundary import GovernanceBoundary
from app.sandbox.service import get_order, get_task_scope, DuplicateIdempotencyError
from app.policy.models import TaskScope
from app.policy.storage import load_policy

def create_governed_mcp_server(
    conn: sqlite3.Connection,
    boundary: Optional[GovernanceBoundary] = None,
    authenticated_caller: Optional[str] = None
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
            action_id = f"act_{uuid.uuid4().hex}"
            audit_id = f"audit_{uuid.uuid4().hex[:12]}"

            # 1. FAIL-CLOSED: Policy configuration check
            policy = load_policy(conn)
            if not policy:
                try:
                    with conn:
                        conn.execute(
                            "INSERT INTO audit_events (id, action_id, tool, verdict, reason, fingerprint, details) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (audit_id, action_id, "lookup_order", "BLOCKED", "FAIL_CLOSED: Policy configuration unavailable or corrupt", "", json.dumps({"order_id": order_id}))
                        )
                except Exception:
                    pass
                return types.CallToolResult(is_error=True, content=[types.TextContent(type="text", text=json.dumps({"error": "POLICY_UNAVAILABLE"}))])

            # 2. FAIL-CLOSED: Tool inclusion in policy.allowed_tools
            if "lookup_order" not in policy.allowed_tools:
                try:
                    with conn:
                        conn.execute(
                            "INSERT INTO audit_events (id, action_id, tool, verdict, reason, fingerprint, details) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (audit_id, action_id, "lookup_order", "BLOCKED", "UNKNOWN_TOOL: Tool 'lookup_order' is not in policy allowlist", "", json.dumps({"order_id": order_id}))
                        )
                except Exception:
                    pass
                return types.CallToolResult(is_error=True, content=[types.TextContent(type="text", text=json.dumps({"error": "TOOL_NOT_ALLOWED"}))])

            # 3. FAIL-CLOSED: Task Scope Enforcement
            if policy.enforce_task_scope:
                if not scope_id:
                    try:
                        with conn:
                            conn.execute(
                                "INSERT INTO audit_events (id, action_id, tool, verdict, reason, fingerprint, details) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                (audit_id, action_id, "lookup_order", "BLOCKED", "OUTSIDE_TRUSTED_TASK_SCOPE: Scope ID required for lookup", "", json.dumps({"order_id": order_id}))
                            )
                    except Exception:
                        pass
                    return types.CallToolResult(is_error=True, content=[types.TextContent(type="text", text=json.dumps({"error": "SCOPE_ID_REQUIRED"}))])

                raw_scope = get_task_scope(conn, scope_id)
                if not raw_scope or TaskScope(**raw_scope).is_expired():
                    try:
                        with conn:
                            conn.execute(
                                "INSERT INTO audit_events (id, action_id, tool, verdict, reason, fingerprint, details) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                (audit_id, action_id, "lookup_order", "BLOCKED", "TASK_SCOPE_EXPIRED", "", json.dumps({"order_id": order_id, "scope_id": scope_id}))
                            )
                    except Exception:
                        pass
                    return types.CallToolResult(is_error=True, content=[types.TextContent(type="text", text=json.dumps({"error": "TASK_SCOPE_EXPIRED"}))])

                if raw_scope["order_id"] != order_id:
                    try:
                        with conn:
                            conn.execute(
                                "INSERT INTO audit_events (id, action_id, tool, verdict, reason, fingerprint, details) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                (audit_id, action_id, "lookup_order", "BLOCKED", f"OUTSIDE_TRUSTED_TASK_SCOPE: Scope authorized order '{raw_scope['order_id']}', attempted '{order_id}'", "", json.dumps({"order_id": order_id, "scope_id": scope_id}))
                            )
                    except Exception:
                        pass
                    return types.CallToolResult(is_error=True, content=[types.TextContent(type="text", text=json.dumps({"error": "OUTSIDE_TRUSTED_TASK_SCOPE"}))])

                # 4. Fail-Closed Caller Identity Binding
                # Untrusted client parameter 'caller_id' is NEVER accepted as authentication.
                # Only trusted server-verified principal 'trusted_principal' is authorized.
                expected_operator = raw_scope.get("operator_id")
                if expected_operator:
                    if not trusted_principal:
                        try:
                            with conn:
                                conn.execute(
                                    "INSERT INTO audit_events (id, action_id, tool, verdict, reason, fingerprint, details) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                    (audit_id, action_id, "lookup_order", "BLOCKED", f"OUTSIDE_TRUSTED_TASK_SCOPE: Anonymous/unauthenticated caller cannot access scope bound to operator '{expected_operator}'", "", json.dumps({"order_id": order_id, "scope_id": scope_id, "caller_id": caller_id}))
                                )
                        except Exception:
                            pass
                        return types.CallToolResult(is_error=True, content=[types.TextContent(type="text", text=json.dumps({"error": "CALLER_IDENTITY_MISMATCH"}))])

                    if trusted_principal != expected_operator:
                        try:
                            with conn:
                                conn.execute(
                                    "INSERT INTO audit_events (id, action_id, tool, verdict, reason, fingerprint, details) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                    (audit_id, action_id, "lookup_order", "BLOCKED", f"OUTSIDE_TRUSTED_TASK_SCOPE: Scope operator '{expected_operator}' does not match authenticated principal '{trusted_principal}'", "", json.dumps({"order_id": order_id, "scope_id": scope_id, "caller_id": caller_id, "authenticated_caller": trusted_principal}))
                                )
                        except Exception:
                            pass
                        return types.CallToolResult(is_error=True, content=[types.TextContent(type="text", text=json.dumps({"error": "CALLER_IDENTITY_MISMATCH"}))])

                    if caller_id and caller_id != trusted_principal:
                        try:
                            with conn:
                                conn.execute(
                                    "INSERT INTO audit_events (id, action_id, tool, verdict, reason, fingerprint, details) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                    (audit_id, action_id, "lookup_order", "BLOCKED", f"OUTSIDE_TRUSTED_TASK_SCOPE: Client parameter caller_id '{caller_id}' does not match authenticated principal '{trusted_principal}'", "", json.dumps({"order_id": order_id, "scope_id": scope_id, "caller_id": caller_id, "authenticated_caller": trusted_principal}))
                                )
                        except Exception:
                            pass
                        return types.CallToolResult(is_error=True, content=[types.TextContent(type="text", text=json.dumps({"error": "CALLER_IDENTITY_MISMATCH"}))])

            # 5. Authoritative Order Lookup
            order = get_order(conn, order_id)
            if not order:
                try:
                    with conn:
                        conn.execute(
                            "INSERT INTO audit_events (id, action_id, tool, verdict, reason, fingerprint, details) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (audit_id, action_id, "lookup_order", "BLOCKED", f"Order {order_id} not found in sandbox", "", json.dumps({"order_id": order_id}))
                        )
                except Exception:
                    pass
                return types.CallToolResult(
                    is_error=True,
                    content=[types.TextContent(type="text", text=json.dumps({"error": f"Order {order_id} not found in sandbox"}))]
                )

            # 6. FAIL-CLOSED: Audit Logging (Never return data if audit insert fails!)
            try:
                with conn:
                    conn.execute(
                        "INSERT INTO audit_events (id, action_id, tool, verdict, reason, fingerprint, details) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (audit_id, action_id, "lookup_order", "ALLOWED", "Order lookup succeeded", "", json.dumps({"order_id": order_id}))
                    )
            except Exception:
                return types.CallToolResult(
                    is_error=True,
                    content=[types.TextContent(type="text", text=json.dumps({"error": "AUDIT_LOGGING_FAILED"}))]
                )

            # 7. Minimized Data Delivery: Zero Customer PII & Masked Destination Only
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
            action_id = f"act_{uuid.uuid4().hex}"
            audit_id = f"audit_{uuid.uuid4().hex[:12]}"

            # 1. FAIL-CLOSED: Policy configuration check
            policy = load_policy(conn)
            if not policy:
                try:
                    with conn:
                        conn.execute(
                            "INSERT INTO audit_events (id, action_id, tool, verdict, reason, fingerprint, details) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (audit_id, action_id, "refund_order", "BLOCKED", "FAIL_CLOSED: Policy configuration unavailable or corrupt", "", json.dumps({"order_id": order_id}))
                        )
                except Exception:
                    pass
                return types.CallToolResult(is_error=True, content=[types.TextContent(type="text", text=json.dumps({"error": "POLICY_UNAVAILABLE"}))])

            # 2. FAIL-CLOSED: Tool inclusion in policy.allowed_tools
            if "refund_order" not in policy.allowed_tools:
                try:
                    with conn:
                        conn.execute(
                            "INSERT INTO audit_events (id, action_id, tool, verdict, reason, fingerprint, details) VALUES (?, ?, ?, ?, ?, ?, ?)",
                            (audit_id, action_id, "refund_order", "BLOCKED", "UNKNOWN_TOOL: Tool 'refund_order' is not in policy allowlist", "", json.dumps({"order_id": order_id}))
                        )
                except Exception:
                    pass
                return types.CallToolResult(is_error=True, content=[types.TextContent(type="text", text=json.dumps({"error": "TOOL_NOT_ALLOWED"}))])

            # 3. Idempotency Key validation
            if not idempotency_key or not idempotency_key.strip() or len(idempotency_key) > 128:
                return types.CallToolResult(
                    is_error=True,
                    content=[types.TextContent(type="text", text=json.dumps({"error": "IDEMPOTENCY_KEY_REQUIRED"}))]
                )

            # 4. FAIL-CLOSED: Task Scope & Caller Identity Enforcement
            task_scope = None
            if policy.enforce_task_scope:
                if not scope_id:
                    try:
                        with conn:
                            conn.execute(
                                "INSERT INTO audit_events (id, action_id, tool, verdict, reason, fingerprint, details) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                (audit_id, action_id, "refund_order", "BLOCKED", "OUTSIDE_TRUSTED_TASK_SCOPE: Scope ID required for refund", "", json.dumps({"order_id": order_id}))
                            )
                    except Exception:
                        pass
                    return types.CallToolResult(is_error=True, content=[types.TextContent(type="text", text=json.dumps({"error": "SCOPE_ID_REQUIRED"}))])

                raw_scope = get_task_scope(conn, scope_id)
                if not raw_scope or TaskScope(**raw_scope).is_expired():
                    try:
                        with conn:
                            conn.execute(
                                "INSERT INTO audit_events (id, action_id, tool, verdict, reason, fingerprint, details) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                (audit_id, action_id, "refund_order", "BLOCKED", "TASK_SCOPE_EXPIRED", "", json.dumps({"order_id": order_id, "scope_id": scope_id}))
                            )
                    except Exception:
                        pass
                    return types.CallToolResult(is_error=True, content=[types.TextContent(type="text", text=json.dumps({"error": "TASK_SCOPE_EXPIRED"}))])

                # Verify caller identity against scope owner: scope possession ALONE does not grant authority!
                expected_operator = raw_scope.get("operator_id")
                if expected_operator:
                    if not trusted_principal:
                        try:
                            with conn:
                                conn.execute(
                                    "INSERT INTO audit_events (id, action_id, tool, verdict, reason, fingerprint, details) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                    (audit_id, action_id, "refund_order", "BLOCKED", f"OUTSIDE_TRUSTED_TASK_SCOPE: Anonymous/unauthenticated caller cannot access scope bound to operator '{expected_operator}'", "", json.dumps({"order_id": order_id, "scope_id": scope_id}))
                                )
                        except Exception:
                            pass
                        return types.CallToolResult(is_error=True, content=[types.TextContent(type="text", text=json.dumps({"error": "CALLER_IDENTITY_MISMATCH"}))])

                    if trusted_principal != expected_operator:
                        try:
                            with conn:
                                conn.execute(
                                    "INSERT INTO audit_events (id, action_id, tool, verdict, reason, fingerprint, details) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                    (audit_id, action_id, "refund_order", "BLOCKED", f"OUTSIDE_TRUSTED_TASK_SCOPE: Scope operator '{expected_operator}' does not match authenticated principal '{trusted_principal}'", "", json.dumps({"order_id": order_id, "scope_id": scope_id, "authenticated_caller": trusted_principal}))
                                )
                        except Exception:
                            pass
                        return types.CallToolResult(is_error=True, content=[types.TextContent(type="text", text=json.dumps({"error": "CALLER_IDENTITY_MISMATCH"}))])

                    if caller_id and caller_id != trusted_principal:
                        try:
                            with conn:
                                conn.execute(
                                    "INSERT INTO audit_events (id, action_id, tool, verdict, reason, fingerprint, details) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                    (audit_id, action_id, "refund_order", "BLOCKED", f"OUTSIDE_TRUSTED_TASK_SCOPE: Client parameter caller_id '{caller_id}' does not match authenticated principal '{trusted_principal}'", "", json.dumps({"order_id": order_id, "scope_id": scope_id, "caller_id": caller_id, "authenticated_caller": trusted_principal}))
                                )
                        except Exception:
                            pass
                        return types.CallToolResult(is_error=True, content=[types.TextContent(type="text", text=json.dumps({"error": "CALLER_IDENTITY_MISMATCH"}))])

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

            # 5. Route through zero-trust governance boundary
            try:
                evaluation = gov_boundary.intercept_and_evaluate(action_payload, task_scope=task_scope)
            except DuplicateIdempotencyError:
                return types.CallToolResult(
                    is_error=True,
                    content=[types.TextContent(type="text", text=json.dumps({"error": "IDEMPOTENCY_KEY_REUSED"}))]
                )
            except Exception:
                return types.CallToolResult(
                    is_error=True,
                    content=[types.TextContent(type="text", text=json.dumps({"error": "AUDIT_LOGGING_FAILED"}))]
                )

            return types.CallToolResult(
                is_error=False,
                content=[types.TextContent(type="text", text=json.dumps(evaluation))]
            )

    return server
