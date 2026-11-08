# AetherGuard — Submission Draft

**Status: draft, not submitted.** Verify the organizer dashboard, eligibility, team roster, current form fields, demonstration, links and all claims before submission. Earlier unsupported draft claims are preserved in `../../archive_outdated/AetherGuard_Submission_Package_pre_review_2026-11-08.md` for reference, not submission.

## Project details

- **Event:** International AI Builders Congress 2026; **track:** Idea to Unicorn (team).
- **Team:** AetherOps AI; **challenge:** AgentOps, under InfraSphere AI.
- **Project:** AetherGuard — task-scoped governance for AI agent tool actions.
- **Roster, roles, repository, live demo and video:** Confirm actual details in the organizer portal; do not invent names, links, public access, or completed artifacts.
- A saved 6 November organizer snapshot lists a 20 November preliminary deadline; reconfirm the current date, time zone, eligibility, and team-size requirements in the official dashboard.
- Organizer [submission rules](https://cloudcampbd.com/events/ai-builders-congress/policies/submission) describe a one-page summary, a three-minute concept/prototype video, localization consideration and disclosure of tools/data/contributions. Their [AI usage policy](https://cloudcampbd.com/events/ai-builders-congress/policies/ai-usage) requires the team to validate and explain AI-generated work. Search-indexed copies were available on 8 November; the logged-in submission form and any newer notices were not verified.

## One-page summary — editable draft

**Problem.** AI assistants can propose actions based on external text, including requests that do not match the task the operator intended. For systems that can issue refunds or perform other consequential operations, relying on a model's instructions alone is insufficient. Excessive permissions and autonomy are recognized risks ([OWASP](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/)).

**Approach.** AetherGuard is a prototype for inspecting and governing a bounded agent tool action before it affects a synthetic refund sandbox. An operator specifies a task scope, and deterministic policy checks the requested order, amount, currency and destination. Depending on the action and configured policy, the system allows it, blocks it, or places it in a human approval queue. A dashboard displays the decision and sandbox outcome.

**Demonstration.** Use synthetic English and Bengali support tickets and synthetic orders. Show a permitted request, an out-of-scope request, and an approval-required request; compare the decision with actual sandbox balances and refund records. Clearly identify whether a run uses the live model, deterministic parser, or fallback. The dashboard uses an official MCP SDK client with in-memory transport; it shares a process with the governed server and does not establish process isolation. The local browser demo and MCP tests are described in [review status](REVIEW_STATUS.md).

**Users and impact hypothesis.** Small teams building tool-using agents may benefit from an understandable, task-bounded approval and audit workflow. This is a hypothesis: no user interviews, production deployment, customer outcomes, or market-size measurements have been established here. Existing products also support gateway policy controls; explain any differentiation as a hypothesis, not a verified novelty claim.

**Limits.** This is a synthetic prototype. It does not move real funds, prove broad prompt-injection prevention, establish production isolation or multi-user authorization, or certify compatibility with every MCP client. An ordinary database audit table is not immutable or tamper-evident. Report only results produced by the final tested version and include test scope and failures.

**AI and data disclosure.** Record the actual AI tools and model providers used, human contributions, synthetic fixtures, dependencies and external material. Do not claim a model was used live or an external system was integrated unless the relevant run is verified. Check the current organizer's disclosure requirements.

## Three-minute video outline

1. **Problem and user:** Explain unsafe tool actions and the intended engineering team.
2. **Approach:** Show the operator's bounded scope, deterministic decision and human review; describe the sandbox as synthetic.
3. **Actual demo:** Run supported allow, block and approval examples; display real sandbox state and honestly label model and MCP behavior.
4. **Evidence and limits:** Show measured results only, state the scope and known gaps, and explain the next validation step.

Rehearse against the actual product. The existence of this outline does not mean the video has been recorded or a demo has been deployed.

A timed draft and synthetic recording checklist are in [DEMO_VIDEO_SCRIPT.md](DEMO_VIDEO_SCRIPT.md).

## Before submission

- [ ] Confirm registered roster, track, deadline, fields, rules and eligibility from the current organizer dashboard.
- [ ] Verify the final build, access controls, synthetic demo scenarios, test results, browser behavior and relevant MCP path.
- [ ] Replace unverified claims with observed results and disclose limitations, AI usage, sources and human contributions.
- [ ] Prepare a valid accessible repository, one-page summary and video; verify links and submission status.
