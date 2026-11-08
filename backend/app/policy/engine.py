"""Deterministic Policy Evaluation Engine"""
from typing import Dict, Any, Optional, Tuple
from .models import PolicyConfig, PolicyVerdict, TaskScope

def evaluate_policy(
    tool: str,
    arguments: Dict[str, Any],
    order: Optional[Dict[str, Any]],
    task_scope: Optional[TaskScope],
    policy_config: Optional[PolicyConfig]
) -> Tuple[PolicyVerdict, str]:
    """
    Deterministically evaluates an agent tool proposal.
    Returns: (PolicyVerdict, reason_string)
    
    Invariants enforced:
    - Missing policy config fails closed (BLOCKED)
    - Unknown tools are BLOCKED
    - Actions outside task scope are BLOCKED
    - Expired task scope is BLOCKED
    - Destination mismatch is BLOCKED
    - Requests exceeding refundable balance are BLOCKED
    - Requests above hard ceiling are BLOCKED
    - Requests above auto-allow threshold require APPROVAL_REQUIRED
    - Requests meeting all invariants under auto-allow are ALLOWED
    """
    # Invariant: Fail Closed
    if policy_config is None:
        return PolicyVerdict.BLOCKED, "FAIL_CLOSED: Policy configuration unavailable or corrupt"

    # Invariant: Allowed tools only
    if tool not in policy_config.allowed_tools:
        return PolicyVerdict.BLOCKED, f"UNKNOWN_TOOL: Tool '{tool}' is not in policy allowlist"

    # Specific checks for refund_order
    if tool == "refund_order":
        order_id = arguments.get("order_id")
        amount = arguments.get("amount")
        currency = arguments.get("currency")
        destination = arguments.get("destination")

        if not order_id or amount is None or not currency or not destination:
            return PolicyVerdict.BLOCKED, "VALIDATION_ERROR: Missing required refund parameters"

        if type(amount) is not int:
            return PolicyVerdict.BLOCKED, "VALIDATION_ERROR: Amount must be an integer"

        if amount <= 0:
            return PolicyVerdict.BLOCKED, "VALIDATION_ERROR: Amount must be greater than zero"

        # Invariant: Trusted Task Scope Enforcement
        if policy_config.enforce_task_scope:
            if task_scope is None:
                return PolicyVerdict.BLOCKED, "OUTSIDE_TRUSTED_TASK_SCOPE: No trusted task scope provided"
            
            if task_scope.is_expired():
                return PolicyVerdict.BLOCKED, "TASK_SCOPE_EXPIRED: Trusted task scope has expired"

            if task_scope.order_id != order_id:
                return PolicyVerdict.BLOCKED, (
                    f"OUTSIDE_TRUSTED_TASK_SCOPE: Scope authorized order '{task_scope.order_id}', "
                    f"attempted '{order_id}'"
                )

            if task_scope.allowed_action != tool:
                return PolicyVerdict.BLOCKED, (
                    f"OUTSIDE_TRUSTED_TASK_SCOPE: Scope authorized action '{task_scope.allowed_action}', "
                    f"attempted '{tool}'"
                )

            if amount > task_scope.max_amount:
                return PolicyVerdict.BLOCKED, (
                    f"OUTSIDE_TRUSTED_TASK_SCOPE: Requested amount {amount} exceeds scope maximum {task_scope.max_amount}"
                )

            if currency != task_scope.allowed_currency:
                return PolicyVerdict.BLOCKED, "OUTSIDE_TRUSTED_TASK_SCOPE: Currency is not authorized"

            if destination != task_scope.allowed_destination:
                return PolicyVerdict.BLOCKED, "DESTINATION_MISMATCH: Destination is not authorized by scope"

        # Invariant: Authoritative Order Verification
        if order is None:
            return PolicyVerdict.BLOCKED, f"ORDER_NOT_FOUND: Order '{order_id}' not found in authoritative state"

        if order["currency"] != currency:
            return PolicyVerdict.BLOCKED, f"CURRENCY_MISMATCH: Order is in {order['currency']}, requested {currency}"

        if policy_config.require_exact_destination_match:
            if destination != order["original_destination"]:
                return PolicyVerdict.BLOCKED, (
                    f"DESTINATION_MISMATCH: Destination '{destination}' does not match "
                    f"original '{order['original_destination']}'"
                )

        if amount > order["refundable_amount"]:
            return PolicyVerdict.BLOCKED, (
                f"EXCEEDS_ORDER_BALANCE: Requested amount {amount} exceeds "
                f"refundable balance {order['refundable_amount']}"
            )

        # Threshold checks
        if amount > policy_config.hard_ceiling_threshold:
            return PolicyVerdict.BLOCKED, (
                f"POLICY_HARD_CEILING: Amount {amount} exceeds maximum allowed hard ceiling "
                f"{policy_config.hard_ceiling_threshold}"
            )

        if amount > policy_config.auto_allow_threshold:
            return PolicyVerdict.APPROVAL_REQUIRED, (
                f"APPROVAL_REQUIRED: Amount {amount} exceeds auto-allow threshold "
                f"{policy_config.auto_allow_threshold}; human operator authorization required"
            )

        return PolicyVerdict.ALLOWED, "POLICY_PERMITTED: Action fully conforms to trusted scope and policy thresholds"

    return PolicyVerdict.BLOCKED, "UNKNOWN_TOOL: No governed execution handler exists for this tool"
