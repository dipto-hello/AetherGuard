# AetherGuard — Technical design and interface boundaries

> Supporting detail: [04 TRD](04_TRD.md) and [05 Schema](05_Schema.md) carry the current architecture and data contracts. If earlier examples conflict, those documents take precedence.

**Status: planning draft, 7 November 2026.** These are behavioral contracts, not evidence of implemented endpoints or a finalized framework. Final API paths, schema and SDK versions will be chosen and documented against actual code at implementation time. See `PRODUCT_SPEC.md` for scope.

## Components and trust

1. **Support agent:** receives a synthetic ticket, requests order data, proposes a tool call through the controlled boundary. It does not authorize its own actions or hold the backend's write credential.
2. **Policy/approval boundary:** validates caller and schema, reads authoritative order/payment state, evaluates allow/deny/approval, and owns the controlled upstream write capability. Never trust client-supplied policy outcome, destination flags, provenance or approval state.
3. **Sandbox backend:** synthetic orders and refund records. Only controlled path may write; database constraints protect duplicate refunds. Decide process/network isolation with deployment design; same-process functions alone do not prove network isolation.
4. **Operator dashboard:** shows decisions, pending approvals, history and actual backend outcomes. Policy change, approval and reset require server-side authorization; display server-reported facts, never a fabricated event.

## Conceptual contracts

- **Order lookup:** input validated order identifier; output minimum synthetic order details needed for decision. Missing order has explicit error; agent cannot infer a successful write from lookup alone.
- **Refund proposal:** identified action and canonical arguments: order id, currency, amount in integer minor units and permitted destination reference. Validate positive amounts, allowed currency and refundable balance against authoritative order state. Never trust `original_payment_method=true` supplied by the model.
- **Policy evaluation:** unknown tools, invalid inputs and unavailable policy deny; explicit deny wins; otherwise allow or require review according to the configured policy and supported action. Policy must not allow amounts above balance. Threshold examples are demo configuration, not real-world defaults.
- **Trusted task scope:** an authorized operator bounds order, action, currency, destination, amount and expiry; neither ticket text nor agent output may widen it. A low-value refund outside trusted scope must not silently execute. Review of a scope expansion is a separate authenticated action, not evidence that the system inferred intent.
- **Approval:** pending action holds immutable canonical arguments, policy/version and expiry. Authenticated reviewer sees those details; rejection, expiry, mismatch or replay cannot authorize execution. Re-evaluate current policy/order state before effect; use atomic state transitions and durable idempotency to prevent duplicate local execution. Explain competing-review and expiry outcomes in the UI.
- **Execution outcome:** represent pending, blocked, approval-required, executing, succeeded, failed, and **unknown** where upstream response is lost. Use a stable idempotency key for the same intent and backend support; reconcile unknown outcome before retry. A generic remote provider cannot be claimed exactly-once without its own compatible guarantees.
- **Policy administration / demo reset:** validated and authorized server-side; audit changes and keep reset restricted to synthetic data. UI errors show safe actionable messages, logs avoid credentials or unnecessary ticket content.

## Persistence model — conceptual

`Order` (id, currency, paid/refundable amount, original destination reference); `Policy` (id/version, rules, active status); `Action` (id, principal, immutable tool/args, policy version, decision, status, idempotency key); `Approval` (action reference, reviewer, status, expiry, consumed time); `AuditEvent` (timestamp, action id, sanitized reason/outcome). Actual fields and database constraints are implementation decisions; migrations and backup/reset behavior must be tested.

## External interfaces and deployment

MCP is a planned integration via a verified official SDK, not yet implemented. Test a real supported client/server and `tools/list`, `tools/call`; do not invent JSON-RPC extensions or claim generic compatibility. Human approval may initially be an application workflow; only call it a protocol-native MCP flow after verified integration. Public demos need authenticated writes/approval, restricted CORS/hosts as appropriate, protected service credentials and safe fixtures.

## Decisions pending

Frontend and backend frameworks/versions; model provider and cost; single-host vs remote demo; identity/access mechanism; storage and migration tools; MCP SDK/version; exact API routes and error formats. Select with environment evidence and official documentation; record decisions in the relevant doc, without presenting proposals as facts.
