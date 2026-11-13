"""Human Approval Desk Service with Parameter Binding & Anti-Replay Safety"""
import sqlite3
import json
import uuid
from typing import Dict, Any, Optional
from app.sandbox.service import get_order, execute_sandbox_refund, get_task_scope, scope_refunded_amount
from app.policy.engine import evaluate_policy
from app.policy.models import PolicyVerdict, TaskScope, action_fingerprint
from app.policy.storage import load_policy
from app.sandbox.exchange_rate import get_policy_rate_micros

_DEFAULT_POLICY = object()

class ApprovalError(Exception):
    pass

class ApprovalNotFoundError(ApprovalError):
    pass

class ApprovalAlreadyProcessedError(ApprovalError):
    pass

class FingerprintMismatchError(ApprovalError):
    pass

class ScopeExpiredError(ApprovalError):
    pass

def get_pending_action(conn: sqlite3.Connection, action_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve details of a pending action by its ID."""
    cur = conn.execute("SELECT * FROM pending_actions WHERE action_id = ?", (action_id,))
    row = cur.fetchone()
    if not row:
        return None
    data = dict(row)
    try:
        data["arguments"] = json.loads(data["arguments"])
    except Exception:
        pass
    return data

def verify_fingerprint(tool: str, arguments: Dict[str, Any], expected_fingerprint: str) -> bool:
    """Verifies that the canonical JSON payload matches the stored SHA-256 fingerprint."""
    return action_fingerprint(tool, arguments) == expected_fingerprint

def decide_approval(
    conn: sqlite3.Connection,
    action_id: str,
    decision: str,
    reviewer_id: str,
    reason: Optional[str] = None,
    policy_config=_DEFAULT_POLICY,
) -> Dict[str, Any]:
    """
    Atomically processes a human operator's decision for a pending action.
    Strictly enforces:
    - Exists & pending status
    - Parameter fingerprint integrity (tamper detection)
    - Anti-replay protection (cannot execute or approve twice)
    - Concurrency safety (atomic state transition)
    - Re-verification of order balance before state mutation
    """
    decision = decision.lower()
    if decision not in ["approve", "reject"]:
        raise ApprovalError(f"Decision must be 'approve' or 'reject', got '{decision}'")

    # Prefetch FX before taking the write lock; the action is re-read and verified below.
    preview = get_pending_action(conn, action_id) if decision == "approve" else None
    preview_args = preview.get("arguments") if preview and preview["status"] == "pending" else None
    bdt_rate = get_policy_rate_micros() if isinstance(preview_args, dict) and preview_args.get("currency") == "BDT" else None

    with conn:
        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")
        if policy_config is _DEFAULT_POLICY:
            policy_config = load_policy(conn)
        cur = conn.execute("SELECT * FROM pending_actions WHERE action_id = ?", (action_id,))
        row = cur.fetchone()
        if not row:
            raise ApprovalNotFoundError(f"Pending action {action_id} not found")

        action = dict(row)
        if action["status"] != "pending":
            raise ApprovalAlreadyProcessedError(
                f"Action {action_id} has already been processed with status '{action['status']}'"
            )

        raw_args = action["arguments"]
        try:
            arguments = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
        except Exception:
            raise FingerprintMismatchError("Arguments cannot be parsed as JSON")

        # Verify parameter fingerprint integrity
        if not verify_fingerprint(action["tool"], arguments, action["fingerprint"]):
            raise FingerprintMismatchError(
                f"Security Violation: Arguments for action {action_id} do not match its cryptographic fingerprint"
            )

        if decision == "approve":
            if action["tool"] != "refund_order":
                raise ApprovalError("Unsupported pending action")
            scope = get_task_scope(conn, action["task_scope_id"]) if action.get("task_scope_id") else None
            if not scope:
                raise ApprovalError("Bound task scope is missing")
            try:
                task_scope = TaskScope(**scope)
                if task_scope.is_expired():
                    raise ScopeExpiredError(f"Bound task scope {action['task_scope_id']} has expired")
                order = get_order(conn, arguments.get("order_id")) if action["tool"] == "refund_order" else None
                verdict, policy_reason = evaluate_policy(
                    action["tool"], arguments, order, task_scope, policy_config, bdt_rate_micros=bdt_rate)
            except ApprovalError:
                raise
            except Exception as exc:
                raise ApprovalError("Current scope or policy could not be validated") from exc
            if verdict == PolicyVerdict.BLOCKED:
                raise ApprovalError(f"Current policy blocks approval: {policy_reason}")
            if scope_refunded_amount(conn, task_scope.scope_id) + arguments['amount'] > task_scope.max_amount:
                raise ApprovalError("Current scope maximum would be exceeded by total refunds")

        audit_id = f"audit_{uuid.uuid4().hex[:12]}"

        if decision == "reject":
            # Atomic update to rejected
            conn.execute(
                """
                UPDATE pending_actions
                SET status = 'rejected', reason = ?
                WHERE action_id = ? AND status = 'pending'
                """,
                (reason or "Rejected by human reviewer", action_id)
            )

            conn.execute(
                """
                INSERT INTO audit_events (id, action_id, tool, verdict, reason, fingerprint, details)
                VALUES (?, ?, ?, 'REJECTED', ?, ?, ?);
                """,
                (
                    audit_id,
                    action_id,
                    action["tool"],
                    reason or "Rejected by human reviewer",
                    action["fingerprint"],
                    json.dumps({"reviewer_id": reviewer_id, "arguments": arguments})
                )
            )

            return {
                "action_id": action_id,
                "status": "rejected",
                "refund": None,
                "reviewer_id": reviewer_id
            }

        elif decision == "approve":
            # Atomic state transition to prevent race conditions & concurrent duplicates
            cursor = conn.execute(
                """
                UPDATE pending_actions
                SET status = 'executing'
                WHERE action_id = ? AND status = 'pending'
                """,
                (action_id,)
            )
            if cursor.rowcount == 0:
                raise ApprovalAlreadyProcessedError(
                    f"Action {action_id} was already claimed by another concurrent process"
                )

            refund = None
            if action["tool"] == "refund_order":
                requests = conn.execute(
                    'SELECT idempotency_key, fingerprint, scope_id FROM action_requests WHERE action_id = ?',
                    (action_id,),
                ).fetchall()
                if (len(requests) != 1 or requests[0]['fingerprint'] != action['fingerprint']
                        or requests[0]['scope_id'] != action['task_scope_id']):
                    raise ApprovalError('Original action request is missing or does not match approval')
                idempotency_key = requests[0]['idempotency_key']
                refund = execute_sandbox_refund(
                    conn=conn,
                    order_id=arguments["order_id"],
                    amount=int(arguments["amount"]),
                    currency=arguments["currency"],
                    destination=arguments["destination"],
                    idempotency_key=idempotency_key,
                    action_id=action_id
                )

            conn.execute(
                """
                UPDATE pending_actions
                SET status = 'executed', reason = ?
                WHERE action_id = ?
                """,
                (f"Approved and executed by reviewer {reviewer_id}", action_id)
            )

            conn.execute(
                """
                INSERT INTO audit_events (id, action_id, tool, verdict, reason, fingerprint, details)
                VALUES (?, ?, ?, 'APPROVED', ?, ?, ?);
                """,
                (
                    audit_id,
                    action_id,
                    action["tool"],
                    f"Approved by reviewer {reviewer_id}",
                    action["fingerprint"],
                    json.dumps({"reviewer_id": reviewer_id, "refund": refund,
                                **({"bdt_rate_micros": bdt_rate} if bdt_rate is not None else {})})
                )
            )

            return {
                "action_id": action_id,
                "status": "executed",
                "refund": refund,
                "reviewer_id": reviewer_id
            }
