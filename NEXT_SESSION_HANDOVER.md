# AetherGuard — নতুন session handover

**শেষ কাজের অবস্থা: ৮ নভেম্বর ২০২৬।** নতুন session-এ এই file-এর সঙ্গে `AGENTS.md`, `docs/REVIEW_STATUS.md`, `tasks/todo.md` ও actual project files পড়ে বর্তমান অবস্থা যাচাই করে বাকি কাজ থেকে শুরু করো। এই handover বর্তমান code বা external rules-এর বিকল্প প্রমাণ নয়।

## বাকি কাজ

1. **Independent security audit ও dependency advisory review:** সম্পূর্ণ security-audit workflow এখনও শেষ হয়নি। আগের run-এ delegated agents usage limit-এ পৌঁছেছিল। অসম্পূর্ণ audit report: `C:/Users/sarke/security-audit-skill/AetherGuard/run-1/REPORT.md`। স্থিতিশীল source snapshot-এ বাকি audit, প্রাসঙ্গিক findings-এর independent verification এবং প্রয়োজনীয় নিরাপদ fixes ও tests সম্পন্ন করো। Project folder নিজে কোনো Git repository ছিল না—আগে বর্তমান অবস্থা পুনরায় দেখো।
2. **Live Gemini run:** আগের session-এর process-এ `GEMINI_API_KEY` পাওয়া যায়নি; real provider-backed model behavior, availability ও cost যাচাই হয়নি। কেবল synthetic input ব্যবহার করে এবং প্রয়োজনীয় credentials/access থাকলে প্রাসঙ্গিক নিরাপত্তা সীমা মেনে পরীক্ষা করো। Live inference, deterministic parsing ও fallback আলাদাভাবে দেখাও।
3. **Accessibility ও deployment:** পূর্ণ keyboard, screen-reader, device, approval ও failure/recovery checks বাকি। Intended deployment environment-এ নিরাপদ configuration, access ও behavior যাচাই করতে হবে। Local test public deployment-এর প্রমাণ নয়।
4. **Hackathon submission:** Current organizer dashboard-এ deadline, registered roster, eligibility, submission rules ও fields যাচাই করো। বাস্তব video, repository/demo links ও final submission তৈরি/যাচাই এখনো বাকি। বর্তমান draft: `docs/07_Submission_Package.md`।
5. **Product ও impact:** Target users-এর সঙ্গে problem, differentiation ও বাস্তব impact যাচাই করা হয়নি। Working synthetic demo বা test pass থেকে market fit, real-world impact বা prize placement দাবি করো না।

## গুরুত্বপূর্ণ ঝুঁকি ও সীমা

- Demo-তে একটি shared operator token আছে; এটি multi-user identity বা role separation নয়। Public deployment-এর আগে authentication, authorization, transport ও অন্য প্রাসঙ্গিক controls যাচাই/উন্নত করতে হবে।
- Agent ও governed MCP server একই process-এ এবং একই SQLite connection ব্যবহার করে। এটি independent process isolation বা arbitrary agent-এর zero write capability প্রমাণ করে না।
- Synthetic sandbox reset refund history মুছে দেয়। Lost-response lookup-এর 404 শুধু ওই মুহূর্তের অবস্থা; in-flight action ঘটবে না, এর নিশ্চয়তা নয়।
- পূর্ববর্তী review প্রতিটি third-party dependency, generated artifact ও binary file-এর প্রতিটি line audit করেছে বলে দাবি করা যায় না; সব সম্ভাব্য defect ধরা পড়েছে এমন নিশ্চয়তাও নেই।
- Previous implementation-এ অন্য AI কোন skills ব্যবহার করেছিল, তার invocation evidence পাওয়া যায়নি। নতুন session-এ কাজ অনুযায়ী available skills/tools বেছে নিজেরা প্রয়োগ ও যাচাই করো।

## আগের session-এর যাচাইকৃত সীমিত ফল

- Isolated WSL environment-এ **৮১টি backend pytest test pass**; এগুলো তখনকার source-এর ফল, নতুন পরিবর্তনের পর পুনরায় চালাতে হবে।
- Frontend TypeScript/Vite build pass। Local isolated Chromium ও actual backend দিয়ে synthetic allow → block → approval flow যাচাই করা হয়েছে; balance minor units-এ `25000 → 21000 → 21000 → 11000`।
- Mock-backed UI-তে কিছু viewport ও axe checks হয়েছে; এগুলো সম্পূর্ণ accessibility audit নয়। বিস্তারিত ও exact limitations `docs/REVIEW_STATUS.md`-এ আছে।
- User আগের session-এ প্রয়োজনীয় tools/dependencies install করার অনুমতি দিয়েছেন। Security-sensitive tests-এ উপযুক্ত isolation, dummy data ও credentials রক্ষা করে কাজ করো; install সংক্রান্ত এই অনুমতিকে user-এর বর্তমান নতুন নির্দেশের সঙ্গে মিলিয়ে প্রয়োগ করো।

## নতুন session-এ বলার জন্য

> AetherGuard project-এর `NEXT_SESSION_HANDOVER.md`, `AGENTS.md`, `docs/REVIEW_STATUS.md` ও প্রাসঙ্গিক project files পড়ে actual বর্তমান অবস্থা যাচাই করো। আগের session-এ যেসব কাজ বাকি ছিল সেখান থেকে শুরু করো: independent security audit ও dependency review, প্রয়োজনীয় fixes/tests, live Gemini যাচাই যেখানে credentials ও access আছে, accessibility/deployment checks এবং organizer dashboard-এ submission eligibility ও rules যাচাই। প্রয়োজনীয় tools/dependencies নিরাপদে install করো। প্রমাণ ছাড়া completion বা security claim করো না; গুরুত্বপূর্ণ blocker ও remaining risks জানাও।

## 8 November — additional review in progress

- Current public-internet deployment goal is not verified or ready for exposure; intended host and its access controls remain unspecified.
- Security-audit `run-2` snapshot and preliminary source review: `C:/Users/sarke/security-audit-skill/AetherGuard/run-2/REPORT.md`. Audit is incomplete; complete the ledger, sandbox and artifact safeguards, hunting, independent validation, and final verification. Investigate the documented possible cumulative task-scope limit issue before implementing or claiming a fix.
- Point-in-time npm lockfile and installed Windows backend environment advisory checks reported no known advisories; see `docs/REVIEW_STATUS.md` for limitations.
- User plans to configure `GEMINI_API_KEY`; verify availability without displaying the key before attempting an authorized synthetic live run. Public event page loaded but organizer dashboard and policy details remain unverified.

## Latest follow-up — 8 November

The Windows user environment contains a Gemini key supplied by the user; it was exposed in chat/screenshot and should be rotated. A synthetic live Gemini-to-MCP-to-policy-to-in-memory-sandbox run succeeded. A cumulative task-scope limit fix was added and 86 backend tests passed in an isolated WSL run. See `docs/REVIEW_STATUS.md` for limitations, including shared-connection MCP concurrency and one-time expiration of prior scopes. UI was refreshed; build, basic navigation and 390px rendering were checked. Full security audit, complete accessibility and public deployment verification are still outstanding. The old audit snapshot predates these changes.



## Latest deployment hardening — 8 November

Same-server MCP stdio concurrent scope-budget bypass was reproduced and fixed with a per-server connection lock; 90 backend tests passed in the isolated WSL test setup, with the concurrent test additionally passing five runs. Added same-origin response security headers and removed unused localhost CORS allowance. Container frontend path, non-root user, persistent database path and `.dockerignore` were added; see README for staging. Container build/run was not tested because no Docker-compatible runtime was available. Public hosting and identity/TLS/rate-limiting, full audit and full accessibility remain unfinished. Run-3 audit snapshot predates these changes. The running localhost server may need restart to load current backend changes.


## Current work — 8 November

Model-native refund proposal is implemented with SDK auto-execution disabled and mock-provider tests; a live provider test of this new path remains pending. Approval request-key collision and atomic reset audit have regression fixes; audit list is bounded. Isolated Chromium with actual backend/CSP and dummy data verified allow plus keyboard approval and balances 25000 → 21000 → 11000 at two viewports; mock-backed checks covered four widths and axe checks. The 10-case deterministic evaluation passed its recorded expectations. Full audit run-5 is in progress against its own snapshot; check its final report and source drift. Docker runtime/build and `/docs`/`/redoc` under CSP remain unverified or unresolved. See `docs/REVIEW_STATUS.md` for details.

## Latest verified state — 8 November

Isolated backend suite: 106 passed. Isolated frontend build and three API tests passed; two lint warnings remain. MCP and HTTP action endpoints now require stable idempotency keys; synthetic negative-intent handling is heuristic only. Actual backend/browser allow and approval flow was rerun after the contract change; unknown-outcome persistence was checked with a mock. A detailed recording script exists but no completed video. Audit run-6 continues separately against a snapshot and must be checked for source drift; live provider function-call test, Docker build, full audit, docs CSP and deployment-specific checks remain open.

A separate synthetic provider SDK request to `gemini-3.5-flash-lite` returned the expected refund function proposal; the previous 2.5 request returned 404 for this project. The app was updated to the working model with 30-second timeout and one attempt. Current app + live provider end-to-end is not yet verified.

Latest isolated backend suite: 107 passed. Audit also reproduced a withdrawn-refund synthetic ticket that would execute; a limited phrase guard now blocks the tested example, but arbitrary intent recognition is not established. Keep this open in the security review rather than declaring a general fix.


## 9 November — Priority Model Fallback Chain & Live Integration Verified

- Implemented automatic 3-tier model priority fallback chain:
  1. `gemini-3.5-flash-lite` (Primary choice, multimodal, 500 req/day).
  2. `gemini-3.1-flash-lite` (Fallback 1, multimodal, 500 req/day).
  3. `gemma-4-31b-it` (Fallback 2, high-volume text filter, 14,400 req/day).
  4. `synthetic_fallback` (deterministic offline engine).
- Fixed destination mismatch bug on live LLM extraction: natural language phrases ("original payment card", "বিকাশ একাউন্ট") resolve to order's authoritative original payment destination, while adversarial injections (`0xAttacker...`) remain intact and are blocked by the policy engine.
- Physically verified live Gemini integration:
  - English ticket (`TICKET-EN-01`): `model_used: gemini-3.5-flash-lite`, `verdict: ALLOWED`, deducted $40.00 (`amount: 4000`), ORD-101 balance reduced from 25000 to 21000 minor units.
  - Bengali ticket (`TICKET-BN-01`): `model_used: gemini-3.5-flash-lite`, `verdict: ALLOWED`, deducted ৳50.00 (`amount: 5000`), ORD-103 balance reduced from 500000 to 495000 minor units.
  - Fallback verification: When primary model was unavailable, system seamlessly fell back to `gemini-3.1-flash-lite`, passing `ALLOWED` and executing sandbox refund without downtime.
- Fixed FastAPI Swagger `/docs`, `/redoc` CSP conflict: allows required jsdelivr CDN on doc routes while strictly enforcing `default-src 'self'` on root and API endpoints.
- Verification status: 107/107 backend tests passing, frontend build passing (575ms), 3/3 frontend API tests passing.
