"""Agent Integration REST API Routes"""
import base64
import binascii
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, PrivateAttr, model_validator
from typing import Literal, Optional

from app.sandbox.db import get_connection
from app.sandbox.service import get_task_scope, get_order, save_task_scope, DuplicateIdempotencyError
from app.policy.models import TaskScope
from app.governance.boundary import GovernanceBoundary
from app.agent.core import SupportAgent
from app.agent.tickets import BENCHMARK_TICKETS

router = APIRouter(prefix="/api/agent", tags=["Agent"])

class ProcessTicketRequest(BaseModel):
    ticket_text: str = Field(..., min_length=1, max_length=10000, description="Customer support ticket text in English or Bengali")
    scope_id: Optional[str] = Field(None, description="Operator authorized task scope ID (admin only)")
    order_id: Optional[str] = Field(None, min_length=1, max_length=64, description="User role: the order this refund is for; the server derives the scope from its record")
    force_mode: Optional[Literal["live"]] = Field(None, description="Legacy client field; ticket processing always uses the live model")
    expected_amount: Optional[int] = Field(None, strict=True, gt=0, le=2**53 - 1, description="Exact amount in a generated example")
    idempotency_key: str = Field(..., min_length=1, max_length=128, pattern=r'.*\S.*', description="Stable key for this request")
    evidence_image: Optional[str] = Field(None, min_length=1, max_length=1_000_000, description="Optional evidence photo as raw base64")
    evidence_mime_type: Optional[Literal["image/jpeg", "image/png", "image/webp"]] = None
    _evidence: Optional[tuple] = PrivateAttr(None)

    @model_validator(mode="after")
    def check_evidence(self):
        if (self.evidence_image is None) != (self.evidence_mime_type is None):
            raise ValueError("evidence_image and evidence_mime_type must be sent together")
        if self.evidence_image is not None:
            try:
                data = base64.b64decode(self.evidence_image, validate=True)
            except (binascii.Error, ValueError):
                raise ValueError("evidence_image must be valid base64")
            signature_ok = {
                "image/jpeg": data.startswith(b"\xff\xd8\xff"),
                "image/png": data.startswith(b"\x89PNG\r\n\x1a\n"),
                "image/webp": data[:4] == b"RIFF" and data[8:12] == b"WEBP",
            }[self.evidence_mime_type]
            if not signature_ok:
                raise ValueError("evidence_image content does not match evidence_mime_type")
            self._evidence = (data, self.evidence_mime_type)
        return self

    @property
    def evidence(self):
        return self._evidence

@router.get("/tickets")
async def get_benchmark_tickets():
    """Retrieve pre-configured benchmark customer tickets (English, Bengali, and Adversarial Injections)."""
    return {"tickets": BENCHMARK_TICKETS}

def _scope_from_order_record(conn, req: ProcessTicketRequest) -> TaskScope:
    """A requester must not set their own limits: the scope comes only from the stored order."""
    if req.scope_id is not None:
        raise HTTPException(403, detail={"code": "SCOPE_NOT_ALLOWED", "message": "Refund permission is set from the order record."})
    if req.order_id is None:
        raise HTTPException(422, detail={"code": "ORDER_REQUIRED", "message": "Choose the order this refund is for."})
    order = get_order(conn, req.order_id)
    if order is None:
        raise HTTPException(404, detail={"code": "ORDER_NOT_FOUND", "message": "This order was not found."})
    if order["currency"] != "BDT":
        raise HTTPException(422, detail={"code": "CURRENCY_MISMATCH", "message": "This order cannot be refunded online."})
    if order["refundable_amount"] <= 0:
        raise HTTPException(422, detail={"code": "NOTHING_TO_REFUND", "message": "This order has already been fully refunded."})
    raw = save_task_scope(
        conn=conn,
        scope_id=f"scope_{uuid.uuid4().hex[:10]}",
        operator_id="demo_operator",  # the in-process MCP binds scopes to this principal
        order_id=order["id"],
        allowed_action="refund_order",
        max_amount=order["refundable_amount"],
        allowed_currency="BDT",
        allowed_destination=order["original_destination"],
        expires_at=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
    )
    return TaskScope(**raw)

@router.post("/process-ticket")
async def process_ticket_endpoint(req: ProcessTicketRequest, request: Request):
    """
    Simulate real support agent receiving a ticket, looking up order data,
    and proposing actions through the AetherGuard zero-trust boundary.
    """
    conn = get_connection()
    try:
        task_scope = None
        if getattr(request.state, "role", None) == "user":
            task_scope = _scope_from_order_record(conn, req)
        elif req.scope_id:
            raw_scope = get_task_scope(conn, req.scope_id)
            if raw_scope:
                task_scope = TaskScope(**raw_scope)

        boundary = GovernanceBoundary(conn)
        agent = SupportAgent(boundary)
        trace = await agent.process_ticket(
            ticket_text=req.ticket_text,
            task_scope=task_scope,
            idempotency_key=req.idempotency_key,
            expected_amount=req.expected_amount,
            evidence=req.evidence,
        )
        return {"trace": trace}
    except DuplicateIdempotencyError as exc:
        raise HTTPException(status_code=409, detail={"code": "IDEMPOTENCY_KEY_REUSED", "message": str(exc)})
    finally:
        conn.close()
