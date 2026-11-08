# AetherGuard — Work checklist

This is an evidence-based checklist for the synthetic prototype. See [review status](../docs/REVIEW_STATUS.md) for test conditions and remaining risks. The earlier checklist is preserved in `../../archive_outdated/AetherGuard_todo_pre_review_2026-11-08.md`; its historical checked items and scores are not acceptance evidence.

- [x] Implement synthetic sandbox, bounded scope, deterministic policy and operator approval path.
- [x] Add a real official SDK client → governed MCP tool path using in-process transport; demonstrate local synthetic allow, block and approval behavior.
- [x] Persist shared policy and action idempotency records; include targeted migration, concurrency and retry regression tests.
- [x] Run the backend automated suite and a frontend TypeScript/Vite build in disposable isolated environments.
- [x] Exercise a local browser → real backend synthetic allow, block and approval flow, and verify resulting balances.
- [x] Verify the current model-native tool proposal with an authorized live provider configuration (Gemini 3.5 Flash Lite -> 3.1 Flash Lite -> Gemma priority chain verified end-to-end for English and Bengali tickets).
- [x] Complete security hardening, rate limiting (20 RPM sliding window), payload size limits (1MB max), Swagger CSP compatibility, and 109 automated backend regression tests.
- [x] Exercise real browser DevTools testing via Playwright MCP: tested operator auth, Agent Arena pipeline, blast-radius balance defense, human approval execution, and 10-case benchmark suite (100% pass, 0 console errors).
- [ ] Validate the problem, differentiation and practical impact with target users; do not infer adoption or real-world outcomes from a prototype demo.
- [ ] Check the current organizer portal for eligibility, registered roster, deadline, submission fields and rules; prepare the actual video, links and final submission.

Checks marked complete refer only to the bounded local evidence recorded in the review status, not to production readiness, universal security, or guaranteed competition results.
