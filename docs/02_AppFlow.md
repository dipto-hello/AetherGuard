# 02 App Flow — AetherGuard

**Status:** proposed, not implemented; screen names and API paths are not locked.

1. Authenticated operator defines bounded trusted task scope: allowed action, order, currency, amount, destination reference and expiry. The ticket and agent cannot enlarge this scope.
2. Operator runs a real agent on a clearly labeled synthetic ticket. Agent reads allowed order data and proposes a tool call through the real MCP path.
3. Boundary validates identity, tool, arguments, trusted scope, authoritative order/balance and policy. Invalid or missing trust data cannot silently authorize a write.
4. Denied actions show a reason and no backend write. An approval-required action is stored with immutable parameters; only an authorized reviewer can approve or reject it. An allow applies only within the trusted scope and policy.
5. Before execution, check approval validity and current policy/order state. Reject changed, expired or replayed approvals; prevent simultaneous duplicate execution.
6. Execute the controlled sandbox action and show actual persisted outcome. If the response is lost, show **unknown** and reconcile before retrying.
7. Inspector displays real event sequence, rule, decision, approval and outcome. Evaluation runner labels synthetic cases and any captured replay.

Required UI states: idle, running, missing scope, denied, pending, rejected, expired, executing, succeeded, failed, unknown, model/network failure and access denied. Test a small refund outside trusted scope as well as allowed, blocked and approved flows. See [UI](03_UI_Spec.md) and [verification](VERIFICATION.md).
