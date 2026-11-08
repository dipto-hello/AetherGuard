# AetherGuard — Implementation plan

## লক্ষ্য ও constraints

২০ নভেম্বর team preliminary deadline-এর জন্য ১৭ নভেম্বরের মধ্যে পূর্ণ working submission package লক্ষ্য; ১৮–১৯ নভেম্বর improvement ও buffer। একজন প্রধান builder, আনুমানিক ৫–৬ ঘণ্টা/দিন; actual time, credentials ও costs এখনও যাচাই হয়নি। Deadline snapshot অনুযায়ী ২০ নভেম্বর ১১:৫৯ PM বাংলাদেশ সময়, current portal-এ পুনরায় যাচাই করতে হবে।

## Build order

1. **Foundation ও early MCP spike:** environment/model access, synthetic sandbox, real MCP client → governed boundary → tool; verify one allow and one deny against actual sandbox state।
2. **Trusted task scope, policy ও audit:** validate identity, tool/arguments and authoritative task scope; allow, deny, approval-required; persist decisions and actual outcome. Low amount or ticket text alone is not authorization।
3. **Human approval:** exact action binding, expiry, atomic single-use, concurrency/retry handling, reject ও fail-closed behavior।
4. **Real agent ও dashboard:** real model chooses tool, user can view inputs, results, audit, pending decisions; edit thresholds ও reset safely।
5. **MCP interoperability, usability ও evaluation:** harden the real MCP path started in the first slice; browser tests, bilingual handling, mixed legitimate/adversarial evaluation, deployment and access controls। MCP বাস্তবে না চললে সেটি দাবি নয়।
6. **Submission:** ১-page summary, AI/data disclosures, ৩-minute video, working demo link ও verified form/roster; test, review, deploy, backup/rehearsal।

দেখানোর মতো সবচেয়ে ছোট end-to-end flow আগে শেষ হবে; user-এর লক্ষ্য পূর্ণ working system, তাই গুরুত্বপূর্ণ integration, quality ও polish যতটা সময়ে সম্ভব শেষ করার পরিকল্পনা আছে। Unsupported infrastructure যোগ করে points ভরার চেষ্টা নয়।

## Schedule targets

| তারিখ | লক্ষ্য ও checkpoint |
|---|---|
| ৮–৯ নভেম্বর | Setup ও early real MCP client → governed boundary → sandbox spike; allow ও deny হলে actual state প্রত্যাশামতো। Check real model access as early as possible। |
| ১০–১১ নভেম্বর | Approval exact-action binding, persistent audit, failure ও replay tests। |
| ১২ নভেম্বর | পুরো core flow UI-তে ব্যবহারযোগ্য; incomplete থাকলে প্রথমে এটি শেষ। |
| ১৩–১৫ নভেম্বর | Editable policies, MCP interoperability hardening, bilingual handling ও mixed evaluation। |
| ১৬–১৭ নভেম্বর | Security hardening, deployment, browser/device verification, measured evaluation, documentation; ১৭ তারিখে submission-ready লক্ষ্য। |
| ১৮–১৯ নভেম্বর | ২–৩ দিনের buffer: missing work, demo, video, summary, roster ও portal check; সম্ভব হলে আগে submit। |
| ২০ নভেম্বর | Final safety buffer ও successful submitted/locked status যাচাই। |

## Mandatory verification

Policy allow/deny/approval, trusted task scope and unauthorized small refund, amounts/destination/order validation, unknown tool, missing policy, changed/expired/replayed approval, simultaneous duplicate attempts, backend timeout/uncertain result, bypass attempt, audit correctness, reset safety, and failure closed। Test actual sandbox state, not only UI/log output. Browser flow: normal → block → approve → result; keyboard and viewport checks; clean setup and demo accessibility।

## Risks and contingencies

- **Model nondeterminism or outage:** isolate agent proposal from policy; transparently labeled captured replay only as supplementary backup; never pretend replay is live AI.
- **Complex MCP integration:** test one real SDK-supported path in the first slice; document actual version/limits, preserve a functional submission if integration cannot be finished.
- **Time short:** secure end-to-end core and required submission artifacts first, then highest-value enhancements; omit only unfinished items and disclose them.
- **Direct credential bypass:** isolate sandbox write path and test; production-grade containment is a separate undertaking.
- **Scope drift / score chasing:** evaluate extra dependencies by their demonstrable benefit and cost. Use platform scoring fields truthfully; no guaranteed score.
- **Submission lock:** organizers' FAQ says improvements after deadline do not change locked judged version; leader may revert submitted entry to draft and resubmit before deadline. Preserve exact submitted version and verify finals rules later.

Task details and verification gates are in [todo.md](todo.md). No implementation is complete until verified.

## Design and test detail

- [Technical boundaries and conceptual contracts](../docs/TECHNICAL_DESIGN.md)
- [Verification cases](../docs/VERIFICATION.md)
- The stack and exact implementation paths remain open until environment and access are checked; do not treat this as a finished code-level implementation specification.

- [Six current planning documents](../docs/01_PRD.md); [06 Plan](../docs/06_Plan.md) links back to this authoritative schedule.
