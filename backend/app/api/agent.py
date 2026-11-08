"""Agent Integration REST API Routes"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from app.sandbox.db import get_connection
from app.sandbox.service import get_task_scope, DuplicateIdempotencyError
from app.policy.models import TaskScope
from app.governance.boundary import GovernanceBoundary
from app.agent.core import SupportAgent
from app.agent.tickets import BENCHMARK_TICKETS
from datetime import datetime

router = APIRouter(prefix="/api/agent", tags=["Agent"])

class ProcessTicketRequest(BaseModel):
    ticket_text: str = Field(..., min_length=1, max_length=10000, description="Customer support ticket text in English or Bengali")
    scope_id: Optional[str] = Field(None, description="Operator authorized task scope ID")
    force_mode: Optional[str] = Field(None, description="Force synthetic parser for offline testing")
    idempotency_key: str = Field(..., min_length=1, max_length=128, pattern=r'.*\S.*', description="Stable key for this request")

@router.get("/tickets")
async def get_benchmark_tickets():
    """Retrieve pre-configured benchmark customer tickets (English, Bengali, and Adversarial Injections)."""
    return {"tickets": BENCHMARK_TICKETS}

@router.post("/process-ticket")
async def process_ticket_endpoint(req: ProcessTicketRequest):
    """
    Simulate real support agent receiving a ticket, looking up order data,
    and proposing actions through the AetherGuard zero-trust boundary.
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
        agent = SupportAgent(boundary)
        trace = await agent.process_ticket(
            ticket_text=req.ticket_text,
            task_scope=task_scope,
            force_mode=req.force_mode,
            idempotency_key=req.idempotency_key,
        )
        return {"trace": trace}
    except DuplicateIdempotencyError as exc:
        raise HTTPException(status_code=409, detail={"code": "IDEMPOTENCY_KEY_REUSED", "message": str(exc)})
    finally:
        conn.close()
