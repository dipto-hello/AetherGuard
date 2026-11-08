# AetherGuard project instructions

AetherGuard is an agent tool-action governance system; its initial demonstration uses synthetic support tickets and a refund sandbox. An implementation exists, but review and verification are ongoing; consult `docs/REVIEW_STATUS.md` for evidence and outstanding work. Use `docs/01_PRD.md` for scope and `tasks/plan.md` for priorities. Update status based on actual evidence as work progresses.

Use the current six documents `docs/01_PRD.md` through `docs/06_Plan.md` according to the task; `docs/04_TRD.md` and `docs/05_Schema.md` own architecture and conceptual data contracts. Read `docs/VERIFICATION.md` for security and regression checks and `docs/ENGINEERING_GUIDELINES.md` for the wider workflow. Avoid loading every document for unrelated minor edits. Current user instructions and verified organizer updates take precedence over old planning notes.

For reusable cross-project lessons, consult `../../GOLDEN_PROJECT_WORKFLOW.md` when planning substantial work; project-specific facts do not carry over automatically.

## Work and skills
- Select relevant available skills from their descriptions for the task; inspect the matching `SKILL.md` before applying it. If a named skill is absent, use a suitable available alternative. Do not claim a skill ran when it did not.
- Planning: `agent-skills:planning-and-task-breakdown`; incremental feature work: `agent-skills:incremental-implementation`; material risk/assumptions: adversarial review, using `agent-skills:doubt-driven-development` when appropriate.
- Policy/approval/API: `agent-skills:security-and-hardening` and `agent-skills:api-and-interface-design`; non-trivial behavioral tests: `agent-skills:test-driven-development`; unexpected failure: `agent-skills:debugging-and-error-recovery`.
- UI changes: `agent-skills:frontend-ui-engineering`, then a suitable browser testing tool/skill for real behavior. MCP/framework integrations: verify version-specific official sources (`agent-skills:source-driven-development` when appropriate). Audit/log design: `agent-skills:observability-and-instrumentation` when relevant.
- Before reporting completion, verify actual behavior and applicable tests/build; for substantial changes consider `agent-skills:code-review-and-quality`. For deployment use applicable shipping guidance. For a substantial explicitly requested security audit, consider `security-audit` and obey its separate isolation requirements. Do not run every skill on every task or introduce unnecessary approval gates.

## Project invariants
- Validate identity, tool and arguments at the last trusted server-side boundary before consequential effects; deny unknown/invalid/unauthorized calls. Keep sandbox credentials out of the agent and browser; no live payments or real sensitive data in the demo.
- Scope comes from a trusted authorized operator, not from the ticket or agent; low amount and policy compliance alone do not establish user intent. Test the actual MCP governance path early.
- Approval must cover the exact pending action, be authorized, expiring and single-use; prevent changed payloads and duplicate/concurrent execution. Treat upstream timeouts as unknown, not automatically safe to retry. Verify actual backend state.
- Separate real model behavior, deterministic policy, synthetic data and replay in the UI and claims. No invented test results, scores, latency, completed features, interoperability or production security.
- Protect public write/policy/approval/reset endpoints, minimize logs, preserve user data, use accessible UI and maintain regression tests. Check relevant callers and tests before changing behavior. Avoid unrelated modifications.
