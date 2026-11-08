"""Governance Boundary REST API Routes"""
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone
import uuid
import json

from app.sandbox.db import get_connection
from app.sandbox.service import save_task_scope, get_task_scope, DuplicateIdempotencyError
from app.policy.storage import load_policy, save_policy
from app.policy.models import TaskScope, PolicyConfig, PolicyVerdict
from app.governance.boundary import GovernanceBoundary
from app.approval.service import (
    decide_approval,
    get_pending_action,
    ApprovalNotFoundError,
    ApprovalAlreadyProcessedError,
    FingerprintMismatchError,
    ScopeExpiredError,
    ApprovalError
)

router = APIRouter(prefix="/api/governance", tags=["Governance"])

class CreateScopeRequest(BaseModel):
    operator_id: str = Field(..., description="ID of the human operator authorizing the task")
    order_id: str = Field(..., description="Specifically authorized order ID")
    allowed_action: str = Field("refund_order", description="Authorized tool name")
    max_amount: int = Field(..., gt=0, description="Max amount in minor units authorized for this task")
    allowed_currency: str = Field("USD", description="Authorized currency")
    allowed_destination: str = Field(..., description="Authorized payment destination")
    expires_in_hours: int = Field(2, gt=0, description="Scope validity window in hours")

class InterceptActionRequest(BaseModel):
    tool: str = Field(..., description="Target tool name")
    arguments: Dict[str, Any] = Field(..., description="Raw tool invocation arguments")
    scope_id: Optional[str] = Field(None, description="Optional operator task scope ID")
    idempotency_key: str = Field(..., min_length=1, max_length=128, pattern=r'.*\S.*', description="Stable key for this request")

class UpdatePolicyRequest(BaseModel):
    auto_allow_threshold: Optional[int] = Field(None, gt=0, description="Auto-allow threshold in minor units")
    hard_ceiling_threshold: Optional[int] = Field(None, gt=0, description="Hard ceiling threshold in minor units")
    allowed_tools: Optional[List[str]] = Field(None, description="List of allowed tool names")

class DecideApprovalRequest(BaseModel):
    decision: str = Field(..., description="'approve' or 'reject'")
    reviewer_id: str = Field(..., description="ID of the human reviewer making the decision")
    reason: Optional[str] = Field(None, description="Optional explanation for decision")

@router.post("/scopes", status_code=201)
async def create_task_scope_endpoint(req: CreateScopeRequest):
    """Create an immutable, operator-bounded trusted task scope."""
    conn = get_connection()
    try:
        scope_id = f"scope_{uuid.uuid4().hex[:10]}"
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=req.expires_in_hours)).isoformat()
        scope = save_task_scope(
            conn=conn,
            scope_id=scope_id,
            operator_id="demo_operator",
            order_id=req.order_id,
            allowed_action=req.allowed_action,
            max_amount=req.max_amount,
            allowed_currency=req.allowed_currency,
            allowed_destination=req.allowed_destination,
            expires_at=expires_at
        )
        return {"scope": scope}
    finally:
        conn.close()

@router.get("/scopes/{scope_id}")
async def get_task_scope_endpoint(scope_id: str):
    """Retrieve an operator task scope."""
    conn = get_connection()
    try:
        scope = get_task_scope(conn, scope_id)
        if not scope:
            raise HTTPException(status_code=404, detail={"code": "SCOPE_NOT_FOUND", "message": f"Scope {scope_id} not found"})
        return {"scope": scope}
    finally:
        conn.close()

@router.post("/evaluate")
async def intercept_and_evaluate_endpoint(req: InterceptActionRequest):
    """
    Core Execution Firewall Interceptor:
    Takes an incoming agent tool request, verifies trusted scope, checks policy,
    and returns ALLOWED, BLOCKED, or APPROVAL_REQUIRED.
    """
    conn = get_connection()
    try:
        task_scope = None
        if req.scope_id:
            raw_scope = get_task_scope(conn, req.scope_id)
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

        boundary = GovernanceBoundary(conn)
        action_payload = {
            "tool": req.tool,
            "arguments": req.arguments,
            "idempotency_key": req.idempotency_key
        }
        result = boundary.intercept_and_evaluate(action_payload, task_scope=task_scope)
        return {"result": result}
    except DuplicateIdempotencyError as e:
        raise HTTPException(status_code=409, detail={"code": "IDEMPOTENCY_KEY_REUSED", "message": str(e)})
    finally:
        conn.close()

@router.get("/audit-logs")
async def get_audit_logs(limit: int = Query(50, ge=1, le=200)):
    """Retrieve stored audit events."""
    conn = get_connection()
    try:
        cur = conn.execute("SELECT * FROM audit_events ORDER BY created_at DESC, rowid DESC LIMIT ?", (limit,))
        logs = [dict(row) for row in cur.fetchall()]
        return {"logs": logs}
    finally:
        conn.close()

@router.get("/actions/lookup")
async def lookup_action(idempotency_key: str):
    """Read a consistent action snapshot; 404 does not exclude an in-flight request."""
    conn = get_connection()
    try:
        conn.execute('BEGIN')
        row = conn.execute('SELECT action_id FROM action_requests WHERE idempotency_key = ?', (idempotency_key,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Action not found")
        action_id = row['action_id']
        pending = conn.execute('SELECT status FROM pending_actions WHERE action_id = ?', (action_id,)).fetchone()
        refund = conn.execute('SELECT * FROM refunds WHERE action_id = ?', (action_id,)).fetchone()
        audit = conn.execute('SELECT verdict FROM audit_events WHERE action_id = ? ORDER BY rowid LIMIT 1', (action_id,)).fetchone()
        if pending:
            status = pending['status']
        elif refund:
            status = 'executed'
        elif audit and audit['verdict'] == 'BLOCKED':
            status = 'blocked'
        else:
            status = 'unknown'
        return {"action": {"action_id": action_id, "status": status, "refund": dict(refund) if refund else None}}
    finally:
        conn.close()

@router.get("/pending-approvals")
async def get_pending_approvals():
    """Retrieve actions currently suspended awaiting human approval."""
    conn = get_connection()
    try:
        cur = conn.execute("SELECT * FROM pending_actions WHERE status = 'pending' ORDER BY created_at DESC")
        actions = []
        for row in cur.fetchall():
            item = dict(row)
            try:
                item["arguments"] = json.loads(item["arguments"])
            except Exception:
                pass
            actions.append(item)
        return {"pending_actions": actions}
    finally:
        conn.close()

@router.post("/approvals/{action_id}/decide")
async def decide_approval_endpoint(action_id: str, req: DecideApprovalRequest):
    """
    Authorized human review of a pending action.
    Single-use, parameter-bound, anti-replay, and concurrent execution protected.
    """
    conn = get_connection()
    try:
        result = decide_approval(
            conn=conn,
            action_id=action_id,
            decision=req.decision,
            reviewer_id="demo_operator",
            reason=req.reason,
        )
        return {"result": result}
    except ApprovalNotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "APPROVAL_NOT_FOUND", "message": str(e)})
    except ApprovalAlreadyProcessedError as e:
        raise HTTPException(status_code=409, detail={"code": "ALREADY_PROCESSED", "message": str(e)})
    except FingerprintMismatchError as e:
        raise HTTPException(status_code=400, detail={"code": "FINGERPRINT_MISMATCH", "message": str(e)})
    except ScopeExpiredError as e:
        raise HTTPException(status_code=400, detail={"code": "SCOPE_EXPIRED", "message": str(e)})
    except ApprovalError as e:
        raise HTTPException(status_code=400, detail={"code": "APPROVAL_ERROR", "message": str(e)})
    finally:
        conn.close()

@router.get("/policy")
async def get_active_policy():
    """Get active deterministic policy parameters."""
    conn = get_connection()
    try:
        policy = load_policy(conn)
        if policy is None:
            raise HTTPException(status_code=503, detail="Policy configuration unavailable")
        return {"policy": policy.model_dump()}
    finally:
        conn.close()

@router.put("/policy")
async def update_policy(req: UpdatePolicyRequest):
    """Safely update policy thresholds."""
    conn = get_connection()
    try:
        conn.execute('BEGIN IMMEDIATE')
        policy = load_policy(conn)
        if policy is None:
            raise HTTPException(status_code=503, detail="Policy configuration unavailable")
        policy = policy.model_copy(update=req.model_dump(exclude_none=True))
        try:
            save_policy(conn, policy)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        conn.execute("INSERT INTO audit_events (id, tool, verdict, reason, details) VALUES (?, 'policy', 'POLICY_UPDATED', ?, ?)",
                     (f'audit_{uuid.uuid4().hex[:12]}', 'Policy updated by demo operator', policy.model_dump_json()))
        conn.commit()
        return {"policy": policy.model_dump(), "message": "Policy successfully updated"}
    finally:
        conn.close()
