"""Policy Models and Schemas"""
from enum import Enum
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
import hashlib
import json

class PolicyVerdict(str, Enum):
    ALLOWED = "ALLOWED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    BLOCKED = "BLOCKED"

class TaskScope(BaseModel):
    """
    Operator-Authorized Task Scope.
    Low value or ticket text alone is NOT authority; this scope bounds the agent.
    """
    scope_id: str = Field(..., description="Unique scope identifier")
    operator_id: str = Field(..., description="ID of the human operator who granted authority")
    order_id: str = Field(..., description="Specifically authorized order ID")
    allowed_action: str = Field("refund_order", description="Authorized tool name")
    max_amount: int = Field(..., gt=0, description="Maximum total refund amount for this scope, in integer minor units")
    allowed_currency: str = Field("USD", description="Authorized 3-letter currency")
    allowed_destination: str = Field(..., description="Authorized payment destination")
    expires_at: datetime = Field(..., description="Scope expiration timestamp in UTC")

    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at

class PolicyConfig(BaseModel):
    """Configurable Deterministic Policy Rules"""
    version: str = "1.0.0"
    allowed_tools: List[str] = Field(default_factory=lambda: ["refund_order", "lookup_order"])
    auto_allow_threshold: int = Field(5000, description="Max amount for auto-allow (e.g. $50.00)")
    hard_ceiling_threshold: int = Field(100000, description="Absolute ceiling before hard-block (e.g. $1,000.00)")
    enforce_task_scope: bool = True
    require_exact_destination_match: bool = True

class ActionIntent(BaseModel):
    """Canonical representation of an intercepted agent tool action"""
    action_id: str
    tool: str
    arguments: Dict[str, Any]
    idempotency_key: str
    task_scope_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def compute_fingerprint(self) -> str:
        """Deterministic SHA-256 fingerprint over canonical arguments and tool name"""
        canonical_str = json.dumps(
            {"tool": self.tool, "arguments": self.arguments},
            sort_keys=True
        )
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()
