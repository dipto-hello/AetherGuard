# Review status — 8 November 2026

The application is a synthetic-data prototype. The checks below are local evidence for specific behavior, not a certification, full security audit, market validation or production-readiness claim.

## Current evidence

- **Backend:** 81 pytest tests passed in a network-isolated WSL bubblewrap environment with a disposable copy, dummy credentials and temporary SQLite database. This included real FastAPI and MCP SDK dependencies installed into a separate Linux virtual environment. No real provider key or payment system was used.
- **MCP:** Automated tests exercise a real official MCP SDK client and server, including the in-process agent path and stdio path. The in-process path shares a process and database connection; it does not establish isolation between agent and write capability.
- **Frontend:** TypeScript project build and Vite production build passed in a network-isolated disposable copy with Linux dependencies installed separately. Browser smoke tests using a mock API checked widths 320, 768, 1024 and 1440 pixels and unknown-outcome persistence after reload.
- **Real local integration:** Chromium and the actual local backend ran together inside an isolated network namespace using a disposable database and dummy token. A synthetic allow, no-scope block and approval flow produced order balances of 25000 → 21000 → 21000 → 11000 minor units. This run used deterministic synthetic parsing, not a live model.
- **Accessibility:** Automated axe checks in the mock-backed UI returned no detected issues in the arena, evaluation, policy, audit and sandbox views checked. Approval view and complete keyboard/screen-reader behavior remain unverified.

## Changes reviewed

The direct HTTP refund endpoint was removed; a shared demo operator token protects API routes. Scope currency/destination, current policy before approval, and action idempotency are checked on the governed path. Shared policy and action request records are stored in SQLite, including migration handling for legacy pending actions and refund keys. A lookup by idempotency key helps inspect a previously submitted action. A 404 is only a point-in-time observation and does not prove an in-flight request cannot complete.

Synthetic amount parsing now handles selected decimal and currency formats and rejects tested malformed amounts. The main dashboard agent uses a real MCP SDK in-memory client. Actual Gemini behavior is unverified; the model currently extracts parameters, and code constructs the tool proposal. Synthetic fallback is labeled and must not be presented as live inference.

The older submission and README drafts included unsupported claims and are preserved outside the project under `../../archive_outdated/`; current submission text is a draft. The previous assistant's actual skill invocations cannot be proven from project documents alone.

## Outstanding and limitations

- Independently verify the final code with the complete security-audit workflow and check dependency advisories. The deep audit was recorded as incomplete at `C:/Users/sarke/security-audit-skill/AetherGuard/run-1/REPORT.md` after delegated agents reached a usage limit. The local demo token is a single shared credential; it does not implement role separation, rate limiting, TLS, or production deployment controls.
- The backend and its agent execute in the same process with access to the same SQLite connection. The project does not prove process isolation, cross-tenant security or zero write capability for arbitrary agents.
- Perform a real provider-backed model run with explicit authorization and synthetic inputs; no live model behavior, cost or availability has been verified in this review.
- Run broader browser, keyboard, screen-reader and device tests, including approval and failure/recovery paths. Browser storage may be unavailable, and a reset removes refund history.
- Verify current organizer dashboard, deadline, registered team roster and eligibility, and prepare a real video, accessible links and submission. No pilot, user interviews, customer outcomes or measured real-world impact are established.
- Project-owned security-sensitive paths received focused review, but a line-by-line review of every dependency, generated artifact and binary file has not been established. No claim that all possible defects or skill rules were exhaustively verified is warranted.

## Additional work — 8 November 2026

A separate source snapshot and preliminary reconnaissance are recorded in `C:/Users/sarke/security-audit-skill/AetherGuard/run-2/REPORT.md`. The audit remains incomplete: no structured coverage ledger, hunting waves, independent candidate verification or full sandbox/artifact-promotion verification was completed. A source-based hypothesis is that distinct actions could reuse one task scope and exceed its maximum in aggregate; intended semantics and runtime behavior need verification.

Dependency advisory checks found no known vulnerabilities reported by `npm audit --package-lock-only --ignore-scripts` for the snapshot lockfile, or `pip-audit --no-deps` for the packages installed in the Windows backend virtual environment on 8 November. These are point-in-time advisory results, not a security guarantee. Backend requirements use mostly open-ended minimum versions, so another installation can resolve differently.

The user identified public internet deployment as the intended environment. The existing single shared token and in-process agent/server do not establish suitable public access controls or isolation. No public deployment was performed or verified. No Gemini key was present in the current, user or machine environment when checked; the user said they would configure it. The current public event page loaded, but the dashboard, current deadline, roster and submission fields were not verified; the policy page did not load its content in the browser.

## Follow-up implementation — 8 November 2026

- The Windows user environment now contains `GEMINI_API_KEY`. A synthetic live parsing request succeeded. A separate in-memory synthetic run returned `live_gemini`, `ALLOWED`, executed a 4,000-minor-unit refund, and changed ORD-101 from 25,000 to 21,000 minor units. No real payment was involved. The supplied key was exposed in the chat and screenshot and needs rotation. Windows user environment variables are not an encrypted secrets vault.
- Treat `TaskScope.max_amount` as a cumulative limit for executed refunds linked to the scope via `action_requests`. The governed execution and approval paths check the amount inside their existing SQLite transactions. Two new tests were observed failing before the fix. A distinct-request concurrency test using separate database connections was also added; 86 backend tests passed in a disposable network-isolated WSL bubblewrap environment with a temporary database. Historical refunds without a matching action registry record cannot be attributed to a scope; a one-time migration expires existing scopes and pending actions while preserving refund history; recreation of a missing action registry also expires scopes. Shared-connection MCP concurrency remains unverified.
- The Agent Arena and navigation received a visual refresh; the production frontend build passed. The rendered dashboard, approval navigation, and a 390px viewport were inspected. A complete screen-reader, keyboard, device and accessibility audit has not been performed. Frontend lint completed with four existing warnings.
- The earlier full security audit remains incomplete. The `run-2` snapshot predates this change and is not an audit of the current code. Independent review and deployment-specific controls remain necessary before public exposure.



## Deployment-hardening follow-up — 8 November 2026

- A real stdio MCP concurrency regression reproduced two distinct refunds exceeding one scope budget. A per-server lock now serializes use of its shared SQLite connection. The new test observed one allowed and one blocked action and passed five repeated isolated runs; 90 backend tests passed overall. This does not establish safety for multiple server instances or direct callers sharing the same connection.
- Same-origin HTTP responses now include CSP, anti-framing, no-sniff and referrer headers; API responses use `no-store`. The unnecessary localhost CORS allowlist was removed; Vite's existing same-origin proxy remains. Automated tests cover headers and the disallowed cross-origin response, but real-browser compatibility with the new headers has not yet been checked. Ticket input is bounded to 1–10,000 characters; this is not a substitute for an upstream HTTP request-body size limit.
- The Dockerfile now points to the actual frontend build, runs as a non-root user and places SQLite in `/data`; `.dockerignore` excludes local environments, databases, dependencies and common key files. The README documents a private staging recipe and deployment prerequisites. Docker, Podman and Buildah were not available, so no container build or runtime check was performed. Hosting, TLS, identity-aware access, rate limiting, persistent storage, backup/restore and production behavior remain unverified.
- Full security-audit workflow is still incomplete. Run-3 reconnaissance used a snapshot taken before these latest fixes and is not an audit of the current source; no full coverage ledger, hunting or independent final verification was completed. An independent source reviewer checked the per-server lock and identified the limitations above.

- Follow-up source review found the strict CSP may block FastAPI `/docs` and `/redoc`, which load CDN assets and inline bootstrap code. Their browser behavior and a safe compatible solution remain unverified. Replaced the dashboard's inline balance-bar style with a native progress element; frontend build passed, but browser compatibility under the new CSP has not been verified.

## Implementation and verification follow-up — 8 November 2026

- The Gemini path now asks for a `refund_order` function proposal with SDK automatic function execution disabled. A supported single proposal is validated and passed through the governed MCP client. Unknown tools, malformed fields and absent proposals fail closed. The new function-call path has mock-provider regression coverage; the earlier successful live Gemini run used the previous parser and does not verify this new path. The model may abstain; a single available tool does not establish general autonomous tool choice.
- The previously observed approval idempotency-key collision was reproduced and fixed: approval now uses and checks the original registered action's key, fingerprint and scope; existing refund keys also bind action IDs. Sandbox reset and its audit event are now atomic, including rollback on audit-write failure. New actions use full UUIDs; historical shorter IDs and schema-level uniqueness limitations remain.
- Added bounded audit-log query limits and fixed policy-editor values being overwritten by unchanged polling responses. The login form now validates the operator token before entering the dashboard; failed credentials remain on the login screen with an error.
- In an isolated loopback namespace, Chromium and the actual backend with a disposable SQLite database and dummy token passed 320px/1440px dashboard, CSP, sandbox, allow and keyboard-triggered approval checks. The synthetic balances were 25000 → 21000 → 11000 minor units. Separate mock-backed browser smoke covered 320/768/1024/1440 widths, rejected/accepted token flow, and action interaction; axe checks on six mock-backed views reported no detected WCAG 2 A/AA or 2.1 A/AA violations. This is not a complete screen-reader or accessibility audit.
- The deterministic evaluation suite ran against isolated in-memory data: all 10 predefined cases matched expected verdicts and measured sandbox effects; this is not a measure of model safety, real-world impact or general security.
- Container build and runtime remain unverified; Docker-compatible tools are unavailable. The full security audit is in progress against its own snapshot, which may differ from the current source. Default FastAPI `/docs` and `/redoc` remain potentially incompatible with the strict CSP. Live hosting and its deployment-specific controls have not been tested.

## Security and verification follow-up — 8 November 2026

- Isolated full backend suite: **106 passed**; isolated frontend TypeScript/Vite build and three API tests passed. Oxlint reported two `react/set-state-in-effect` warnings, no errors.
- The MCP refund tool and the HTTP process-ticket/evaluate APIs now require a nonblank caller-supplied idempotency key of at most 128 characters. This is a compatibility change for callers that omitted keys. Retrying without the original key is not safe; the dashboard already supplies one.
- The deterministic fallback now blocks tested tickets without a refund keyword or with selected negative phrases. These are conservative English/Bengali heuristics, not proof of intent recognition; other phrasings can be misunderstood. The real-model path has not been retested against the provider since function-call changes.
- Isolated actual-backend browser flow passed at 320px and 1440px after the current API key requirement. A separate mock-backed failure test verified unknown outcome survives reload and prevents another action until the operator acknowledges reconciliation. Search-indexed organizer submission and AI provenance policies were checked; authenticated dashboard fields and notices remain unverified.
- A recording script exists at `docs/DEMO_VIDEO_SCRIPT.md`; no final video or submission exists. Full security audit continues in a separate run, with source drift after earlier snapshots; no completed-audit claim is made.
- Live provider follow-up: the previous `gemini-2.5-flash` request returned HTTP 404 for this project even though the model appeared in the model list. On 8 November a separate synthetic request using `gemini-3.5-flash-lite` returned one `refund_order` function call with the expected synthetic order, amount, currency and destination. The app now selects this model with a 30-second request timeout and one attempt. This standalone SDK check did not execute the current application path end-to-end with the provider; that combination remains to be verified. Google describes 2.5 model access as restricted for some users, not universally discontinued: https://ai.google.dev/gemini-api/docs/models
- Additional audit-sourced tests reproduced a withdrawn-refund synthetic ticket causing an allowed action. The known wording is now blocked along with other selected negative phrases; this remains a limited heuristic, and reliable intent recognition or review-only execution for ambiguous text is not established. See `backend/tests/test_agent_integration.py`.
- Latest isolated backend suite after these changes: **107 passed**. Required idempotency keys are a compatibility change for both HTTP action endpoints and the MCP refund tool; previous integrations omitting them must be updated.


## Priority Model Fallback Chain & Live Integration Follow-up — 9 November 2026

- Implemented an automatic 3-tier model priority fallback chain following the specified architectural priority order:
  1. `gemini-3.5-flash-lite` (Primary choice, multimodal, 500 requests/day, 15 RPM).
  2. `gemini-3.1-flash-lite` (Fallback 1, multimodal, 500 requests/day, 15 RPM).
  3. `gemma-4-31b-it` (Fallback 2, high-volume text filter, 14,400 requests/day, 30 RPM).
  4. `synthetic_fallback` (deterministic offline engine).
- Resolved destination mismatch gap in live model inference: natural-language refund phrases ("original payment card", "my card", "বিকাশ একাউন্ট", etc.) are safely resolved to the order's authoritative original payment destination, while explicit adversarial destination overrides (e.g. `0xAttacker...`) remain intact and are blocked by the policy engine.
- Physically verified live Gemini integration end-to-end:
  - English ticket (`TICKET-EN-01`): `model_used: gemini-3.5-flash-lite`, verdict `ALLOWED`, executed refund of $40.00 (`amount: 4000`), reducing ORD-101 balance from 25000 to 21000 minor units.
  - Bengali ticket (`TICKET-BN-01`): `model_used: gemini-3.5-flash-lite`, verdict `ALLOWED`, executed refund of ৳50.00 (`amount: 5000`), reducing ORD-103 balance from 500000 to 495000 minor units.
  - Simulated primary quota exhaustion: seamlessly triggered fallback to `gemini-3.1-flash-lite`, producing verdict `ALLOWED` and executing refund without error.
- Resolved FastAPI Swagger `/docs`, `/redoc` and `/openapi.json` CSP compatibility by permitting jsdelivr CDN assets on doc routes while strictly enforcing `default-src 'self'; object-src 'none'; frame-ancestors 'none'` on root and API routes.
- Full backend test suite: **109 passed** in 7.17s (including 20 RPM sliding-window rate limiting and 1MB payload size guard). Frontend production build passed in 927ms, and 3/3 frontend API tests passed in 25ms.
- Real browser end-to-end audit via Playwright MCP verified all views (Agent Arena 5-stage pipeline, balance defense, operator approval desk, 10/10 evaluation benchmark cases passed, 0 console errors).
