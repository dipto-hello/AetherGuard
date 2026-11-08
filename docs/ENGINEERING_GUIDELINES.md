# AetherGuard — Engineering guidelines

প্রাসঙ্গিক local skill instructions পড়ে এই project-specific নির্দেশগুলো বেছে নেওয়া হয়েছে। এগুলো task অনুযায়ী ব্যবহার করবে; skill availability বা সংস্করণ পরে বদলালে আবার যাচাই করবে। User-এর বর্তমান নির্দেশ ও বাস্তব project evidence সর্বাগ্রে।

## কাজের ধরণ

- আগে existing code, callers, tests, configuration ও affected paths পড়ো; প্রতিটি পরিবর্তনের উদ্দেশ্য ও side effect বোঝো। ছোট end-to-end slice তৈরি করো যাতে প্রতিটি ধাপের পরে application কাজ করে।
- নতুন non-trivial behavior ও security logic-এর জন্য আগে meaningful failing test, তারপর implementation ও verification। Bug এলে আগে reproduce, root cause ঠিক এবং regression test যোগ করো। ছোট documentation-only পরিবর্তনে অপ্রয়োজনীয় tests নয়।
- Context অনুযায়ী tests, build/type/lint, real browser behavior ও security review চালাও। Test fail করলে নতুন feature চালিয়ে না গিয়ে আগে কারণ সমাধান করো। Completed claim-এর সঙ্গে concrete result দাও।
- Git ব্যবহার শুরু করার আগে existing status ও user changes দেখো। ছোট reviewable changes রাখো; unrelated file rewrite, destructive commands ও secret commit এড়াও। কোনো অজানা কাজ মুছে ফেলো না।

## Trust boundary ও security

- LLM output, external ticket, incoming tool parameters ও model-provided labels untrusted। Validate schema, allowed tools, identity and authorization at the server boundary; default deny for unsupported or malformed actions।
- Decision upstream side effect-এর **আগে** নিতে হবে। Event logging বা asynchronous graph computation-কে authorization হিসেবে ব্যবহার নয়। Agent-এর direct write credentials/network bypass এড়াও; public environment-এ approvals, policy changes ও reset নিরাপদ authenticated access-এর পেছনে।
- Human approval exact action/arguments-এর সঙ্গে bind; expiring, single-use, replay-resistant এবং atomic consumption দরকার। Concurrent requests ও retry নিরাপদ করতে persistent idempotency ও actual backend state যাচাই করো; timeout মানেই action ঘটেনি ধরে নিও না।
- Log minimum necessary data; secrets ও sensitive information সংরক্ষণ/প্রদর্শন নয়। Test data synthetic। No fake login that grants real admin access, unsafe default credentials, destructive SQL বা direct production payments।
- Current official MCP/provider docs পড়ে real supported protocol/SDK ব্যবহার করো; claimed version, interoperability, latency ও security test না করে ঘোষণা নয়।

## UI, API ও demo

- APIs-এর inputs, outputs, errors ও ownership স্পষ্ট রাখো; changing the policy/approval flow যেন পুরোনো consumers না ভাঙে।
- UI-তে keyboard operation, accessible labels, readable contrast, mobile/desktop layout এবং loading, empty, error, success ও denied states যাচাই করো। Color alone দিয়ে decision বোঝাবে না।
- Live AI ও synthetic sandbox স্পষ্টভাবে চিহ্নিত করো। Replay থাকলে labeled থাকবে; upstream execution status actual state থেকে আসবে।
- No simulated result as real, fabricated benchmark, unsupported production/security claim or unused technology selected for points. Report known limitations and measured outcomes.

## Skill selection for future work

| কাজ | প্রাসঙ্গিক local skill |
|---|---|
| Scope ও implementation planning | `agent-skills:planning-and-task-breakdown`, `agent-skills:spec-driven-development` |
| ছোট working increments | `agent-skills:incremental-implementation` |
| API ও side-effect safety | `agent-skills:api-and-interface-design` |
| Security-sensitive engineering | `agent-skills:security-and-hardening`; substantial audit-এর সময় installed `security-audit` workflow ও isolation requirements বিবেচনা |
| Tests ও regression | `agent-skills:test-driven-development`, `agent-skills:debugging-and-error-recovery` |
| UI implementation | `agent-skills:frontend-ui-engineering`; browser testing-এর জন্য relevant available browser tool |
| Change review ও version control | `agent-skills:code-review-and-quality`, `agent-skills:git-workflow-and-versioning` |

Implementation-এর সময় প্রাসঙ্গিক skill-এর current `SKILL.md` আগে পড়বে; এই summary সম্পূর্ণ skill-এর বিকল্প নয়। একাধিক skill একসঙ্গে প্রয়োগ করলে বাস্তব value অনুযায়ী বাছাই করবে, অপ্রয়োজনীয় gates বা dependencies যোগ করবে না।
