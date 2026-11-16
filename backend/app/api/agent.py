"""Agent Integration REST API Routes"""
import base64
import binascii

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, PrivateAttr, model_validator
from typing import Literal, Optional

from app.sandbox.db import get_connection
from app.sandbox.service import get_task_scope, DuplicateIdempotencyError
from app.policy.models import TaskScope
from app.governance.boundary import GovernanceBoundary
from app.agent.core import SupportAgent
from app.agent.tickets import BENCHMARK_TICKETS

router = APIRouter(prefix="/api/agent", tags=["Agent"])

class ProcessTicketRequest(BaseModel):
    ticket_text: str = Field(..., min_length=1, max_length=10000, description="Customer support ticket text in English or Bengali")
    scope_id: Optional[str] = Field(None, description="Operator authorized task scope ID")
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
