# 03 UI Specification — AetherGuard

**Status:** design requirements, not implemented. Prefer a clear AgentOps control surface over decorative effects. Refund is the first synthetic scenario.

## Main views

1. **Run and inspect:** trusted task scope, synthetic ticket input, real agent activity, tool/arguments, policy decision, reason and actual sandbox outcome. Distinguish live AI from replay.
2. **Approval desk:** exact order, amount, currency, destination, scope, reason and expiry; authorized approve/reject actions; clear stale and error states.
3. **Policy and audit:** authorized policy editing, actual event history and sandbox records. Minimize displayed data and protect write operations server-side.
4. **Evaluation:** run supported mixed cases and display expected/actual outcomes, backend effects, case counts and failures. No preset or simulated success score.

## Quality and demo

Use semantic controls, keyboard navigation, visible focus, readable contrast, responsive layouts and text in addition to color. Handle loading, empty, network failure, denied access, stale approval and unknown execution states. UI animation and delivery (polling or SSE) are implementation choices and must reflect real events. Use synthetic data only. Verify real browser behavior and compare displayed outcomes with backend state.
