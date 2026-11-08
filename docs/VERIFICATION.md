# AetherGuard — Verification and quality plan

**Status: verification plan.** Some checks have run; see [review status](REVIEW_STATUS.md) for actual evidence and outstanding work. Use isolated synthetic fixtures and avoid live payment systems or untrusted code without the required isolation.

## Before accepting core behavior

| Scenario | Evidence required |
|---|---|
| Allowed refund | Correct sandbox order and refund state changes exactly once; decision and result visible. |
| Unknown tool, invalid amount/currency/order, missing policy | Denied; no backend effect; meaningful reason. |
| Small refund with missing or mismatched trusted task scope | No silent execution; test explicit deny or authenticated bounded scope authorization and verify backend state. |
| Excess refund, remaining balance exceeded, or changed destination | Denied even if client/model supplies a false “original destination” flag. |
| Approval required | No execution before authorized reviewer approves the exact displayed action. |
| Changed, expired, rejected or replayed approval | Cannot execute; current policy/order state checked before execution. |
| Concurrent approvals / duplicate calls | Atomic consumption plus idempotency: no duplicate sandbox effects. |
| Timeout or lost response after submission | Outcome marked unknown and reconciled; no blind unsafe retry. |
| Policy engine/backend failure | Fail closed for consequential actions; errors reported accurately. |
| Credential bypass and public writes | Verify intended isolation and server-side access checks with low-privilege test principals. |
| Audit and privacy | Events agree with real states, redact secrets, no unnecessary personal information. |
| Reset | Only synthetic data reset; unauthorized request rejected. |

## Agent, UI and release

- Exercise a real model/tool flow and both English and Bangla sample tickets. Model may not obey a poisoned ticket; do not claim repeatable exploitation without measured evidence. A replay, if used, is visibly labeled and still invokes real policy/backend logic.
- Run integration tests of boundary + database and focused unit tests for rule logic; test important browser flows, keyboard, responsive layout, and loading/error states. Compare dashboard to actual records.
- Verify one real MCP path and supported version if integrated; measure latency only with an identified setup and report observed results, not targets.
- Start the real client → governed boundary → sandbox test early; evaluate a reproducible mixed set of legitimate and adversarial supported cases. Record expected/actual decisions, actual effects, counts, failures and limitations; never present a fixed invented score.
- On fresh setup verify all documented commands, safe demo access and data resets. Before submission verify links, roles, source/AI disclosure, pitch/video, and that locked submission reflects actual build.
- For each implementation slice record test commands, pass/fail, manual observations and open limitations in `tasks/todo.md` or the relevant task record. Do not invent pass status; investigate regressions before adding features.
