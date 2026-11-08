# 05 Data, State and API Contracts — AetherGuard

**Status:** conceptual contract for an implemented prototype; this is not a complete description of the current database or a stable API. See [review status](REVIEW_STATUS.md) and source for verified behavior.

## Conceptual data

| Object | Required responsibility |
|---|---|
| Order | Synthetic ID, currency, paid/refundable balance and authoritative original destination. Amounts use integer minor units. |
| TaskScope | Trusted principal, order, allowed action, currency, cumulative maximum refund amount, destination and expiry; untrusted ticket/model cannot create or widen scope. |
| Policy | Versioned allow/deny/review rules; unknown action or unavailable policy denies. |
| Action | Immutable canonical tool/arguments, caller, scope, policy version, decision/reason, state, stable idempotency key and actual outcome. Same key with changed payload is rejected. |
| Approval | Action/fingerprint, authorized reviewer, status, expiry and consumption time; atomically single-use. |
| Refund | Synthetic order, amount/currency/destination, originating action and idempotency reference; constraints prevent duplicate effects and over-refunds. |
| AuditEvent | Timestamp, correlation/action, sanitized actor, rule, decision and observed outcome; no unnecessary secrets or personal data. |

## State and authorization

Proposal → denied, pending approval or allowed → executing → succeeded, failed or **unknown**. Pending approval may become approved, rejected or expired. Unknown means an upstream write may have happened: reconcile before retry. Concurrency must not duplicate sandbox effects. Human approval covers an exact bounded action and cannot bypass hard deny/business constraints; scope expansion requires a separate trusted operator action.

## Conceptual operations

- Authorized operator creates bounded task scope; a ticket alone is never authority.
- Agent reads an order and proposes a refund via the governed MCP path.
- Boundary returns actual decision and action identifier; allowed execution or exact-action review follows policy and trusted scope.
- Authorized reviewer approves/rejects; policy/order/expiry and immutable action are rechecked before the write.
- Authorized operator changes policy or resets synthetic data; each is validated and audited. Viewer inspects sanitized events and evaluation outcomes.

Specific HTTP endpoints, schemas, auth/error formats and MCP message versions are not yet fixed. Define them against the selected SDK, then keep implemented code and docs aligned. See [verification](VERIFICATION.md).
