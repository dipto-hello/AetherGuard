# AetherGuard — Product scope

> Supporting detail: [01 PRD](01_PRD.md) is the current product-level source. In particular, low amount alone never establishes authorization; trusted task scope is required.

**State:** agreed direction and draft implementation specification, ৭ নভেম্বর ২০২৬; no implemented features claimed. User-এর পরবর্তী সিদ্ধান্ত ও validated findings অনুযায়ী পরিবর্তনযোগ্য।

## Problem and target user

AI agent external text পড়ে refund-এর মতো business action ভুলভাবে বা অনুমতি ছাড়া প্রস্তাব করতে পারে। Target user হলো agent তৈরি করা ছোট engineering team, যারা tool execution-এর আগে control ও human review চায়। AetherGuard একটি নির্দিষ্ট controlled tool path-এ এই কাজ করার লক্ষ্যে নির্মিত হবে; সব prompt injection বা সব enterprise risk সমাধানের দাবি নয়।

## First complete workflow

Synthetic customer ticket → real AI agent → order lookup / proposed refund → server-side validation and policy → allow, deny, or approval-required → sandbox backend → persisted result and audit → dashboard.

1. English/Bangla ticket ও seeded synthetic order data নিয়ে agent কাজ করবে। Model তৈরি করবে tool proposal; authorization করবে আলাদা deterministic logic।
2. Policy tool, order, amount ও destination যাচাই করবে। Example only: $40 allow, $250 approval, $5,000 deny, new destination deny। বাস্তব policy configurable; সংখ্যাগুলো আইনি বা universal business rule নয়।
3. Approval screen-এ exact action/order/amount/destination দেখাবে। Reject, expiry, changed arguments, duplicate/replay ও concurrent request নিরাপদে সামলাতে হবে; business action একবারের বেশি execute না হওয়ার ব্যবস্থা ও test থাকতে হবে।
4. Approved action synthetic sandbox data-তে বাস্তব পরিবর্তন করবে; blocked action backend-এ পৌঁছাবে না। Agent-এর কাছে সরাসরি write credential থাকবে না।
5. Dashboard-এ ticket/run, proposed tool call, decision ও reason, pending approval, actual outcome এবং audit history থাকবে। Policy threshold change ও safe reset করার সুবিধা থাকবে।
6. Users-এর জন্য documented setup, clear errors, accessible responsive UI এবং secure demo access থাকবে।

## Design boundaries

- Unknown tool, malformed/invalid input, missing policy/identity বা approval, policy engine failure: unsafe action বন্ধ থাকবে; error ও reason লগ করা হবে।
- Use synthetic data and a sandbox; real payment, real customer data or third-party actions are outside this demo scope. Public access must protect policy changes, approvals and writes.
- Audit means stored decision history; tamper-proof, immutable or cryptographically verifiable বলে দাবি নয় যতক্ষণ না implement ও পরীক্ষা করা হয়। Untrusted agent-provided provenance নিজের থেকে সত্য নয়।
- Protect secrets and minimize data/log exposure. Controlled-path guarantee depends on preventing direct access to the sandbox write path; real enterprise isolation আলাদা কাজ।
- MCP integration একটি planned objective: official SDK and one real interoperable tool path; সফল implementation ও compatible client test-এর আগে MCP compatibility claim নয়।

## Done means

- Real AI workflow plus reproducible allowed, blocked and approved sandbox actions; a clearly labeled captured replay can supplement nondeterministic live AI, not masquerade as live inference.
- Policy editing changes real decisions; rejected or changed/replayed approvals do not execute, including concurrent requests.
- Dashboard decisions match persisted backend state, important failure paths fail closed, and meaningful tests plus manual browser checks pass.
- Another person can follow current instructions and access a safe demonstration; AI usage, synthetic data, limits and results are honestly documented.

## Planned expansion

MCP is an early planned integration; wider policy coverage, more connectors, meaningful evaluation, localization, improved UX, portability and deployment hardening are planned in order of value, time and verified quality. Graph/vector databases, advanced taint lineage, SQL analysis, cryptographic audit and multi-agent orchestration remain candidates—not completed capabilities or mandatory dependencies. Product improvements after preliminary are allowed, but the organizer says judges evaluate the submission locked at deadline; finals treatment of later improvements needs current organizer guidance.

## Choices to confirm during implementation

Python/FastAPI and SQLite are reasonable initial candidates, not locked decisions. Choose UI framework, model provider, deployment and authentication based on available skills, access, budget and current official docs. Do not expose live secrets; do not claim production-grade safety, performance or novelty without evidence.
