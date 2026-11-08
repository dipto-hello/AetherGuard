# 06 Implementation Plan — AetherGuard

**Status:** original implementation plan; the prototype exists and verification continues. The schedule is [tasks/plan.md](../tasks/plan.md), work status is [tasks/todo.md](../tasks/todo.md), and current evidence is in [review status](REVIEW_STATUS.md).

## Order

1. Verify environment, current competition portal, roster, provider access and budget.
2. Early MCP spike: real client → governed boundary → synthetic sandbox tool, including discovery, allowed and blocked calls. Verify the boundary, not merely the server.
3. Implement trusted task scope, deterministic policy and observable decision/outcome; low amount alone is not authorization.
4. Implement exact-action approval, expiry, concurrent single-use and durable idempotent sandbox execution; reconcile unknown outcomes.
5. Connect real LLM agent and operator UI: inspector, approval, policy configuration, audit and safe reset. Test synthetic English/Bangla workflows.
6. Add reproducible mixed legitimate/adversarial evaluation and report actual expected/observed outcomes and backend effects. Include no-scope small refund and concurrency/replay cases.
7. Complete browser/accessibility, security, deployment and clean setup checks; prepare actual demo, 3-minute video, one-page summary and form disclosures by 17 November, preserving 18–19 November buffer before the reported 20 November team deadline.

## Gates and contingency

Each thin slice requires meaningful behavior tests and actual sandbox state verification. If an enhancement proves infeasible, preserve working secure core and submit truthful results; do not advertise universal compatibility, exact metrics or production security without evidence. Current organizer dashboard, registered team size, credentials, budget and deployment requirements remain to be checked. Post-deadline product improvement does not change the preliminary version locked for judging under the event FAQ.
