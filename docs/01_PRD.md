# 01 PRD — AetherGuard

**Status:** product requirements drafted 7 November 2026; implementation and verification are in progress. See [review status](REVIEW_STATUS.md) for current evidence.

## Problem and target user

AI agents reading external text can propose unintended tool actions. AetherGuard helps engineering teams govern consequential agent actions through an actual MCP path, clear decisions, human review and measurable evaluation. Synthetic support/refund is the first demonstration scenario, not a claim that every agent or business domain is supported.

## Core workflow

An authorized operator creates bounded trusted task scope. A real AI agent reads a synthetic English/Bangla ticket, looks up an order and proposes a tool action. The governed boundary checks trusted scope, authoritative order data and policy before allowing, blocking or requesting approval. A sandbox executes permitted actions, while the inspector shows the decision and actual outcome.

**Critical distinction:** A small refund may be policy-compliant but outside the user's actual task. Untrusted ticket text and the model cannot authorize themselves or widen task scope. Missing or conflicting scope means deny or seek explicit authenticated review of a bounded action; do not claim complete understanding of user intent.

## Acceptance

- A real MCP client/tool path demonstrates governed allow and deny; a real LLM proposes at least one action.
- An authorized reviewer approves the exact pending action; altered, expired or replayed approvals and concurrent duplicate execution are prevented.
- A dashboard exposes real actions, decisions, reasons, approval and sandbox outcome; authorized policy editing and safe reset work.
- A repeatable mixed legitimate/adversarial evaluation records expected and actual decisions and sandbox effects. A safe judge-accessible demo, 3-minute video and one-page summary are prepared.
- Sandbox data is synthetic; direct write credentials are not exposed to the agent. Meaningful tests and documented limitations support all claims.

No claim of universal prompt-injection protection, any-agent compatibility, SOC2 readiness, production security, exact latency, success rate or guaranteed prize without evidence. More detail: [TRD](04_TRD.md), [Schema](05_Schema.md), [verification](VERIFICATION.md).
