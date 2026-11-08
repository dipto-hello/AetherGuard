# AetherGuard — synthetic demo recording script

**Status:** recording script only; no video has been recorded or submitted. Verify current organizer requirements and replace placeholders only with real details. Use a disposable synthetic database. Never show tokens, API keys or real customer information.

## Setup

- Start a disposable local instance and sign in before recording. Confirm the UI labels the selected processing mode; this script uses the deterministic synthetic mode, not a live Gemini claim.
- Start with the seeded ORD-101 balance of USD 250.00. Confirm the policy auto-allow threshold is USD 50.00 and that the displayed order and destination are synthetic.
- Keep the browser and sandbox visible. Do not edit the footage to imply a different result. If any operation behaves differently, stop and correct the script or show the actual result.

## Shot list and narration — target under three minutes

| Time | Show | Narration |
|---|---|---|
| 0:00–0:15 | A support ticket and operator task scope in Agent Arena. | “An AI assistant can read a customer ticket and propose a consequential action. How do we check that action against what an operator actually authorized?” |
| 0:15–0:35 | Explain order ORD-101, the USD 50 scope limit, currency and original destination. | “AetherGuard is a synthetic prototype for task-scoped tool governance. An operator sets the order, cumulative refund limit and permitted destination before the action reaches the sandbox.” |
| 0:35–1:00 | Run the USD 40 example; show the actual verdict and Sandbox DB. | “Here the request fits the scope and policy. The governed MCP path returns an allow decision. The synthetic refundable balance changes from 250 to 210 dollars.” |
| 1:00–1:20 | Disable the scope and run a small refund request; show the blocked result and unchanged balance. | “A small amount alone is not authority. With no task scope, this request is blocked, and the sandbox balance stays at 210 dollars.” |
| 1:20–1:55 | Select the ORD-101 USD 300 scope; enter an explicit USD 100 refund to `card_visa_4242`. Run it, open Approval Desk, inspect the order, amount, destination and fingerprint, approve, then open Sandbox DB. | “A higher-value action is held for review. The operator can inspect the exact action. After approval, the synthetic balance changes from 210 to 110 dollars.” |
| 1:55–2:15 | Show the audit and evaluation views. | “The dashboard records decisions and outcomes. The evaluation contains predefined synthetic cases; it is a reproducible check, not a measure of real-world impact or universal protection.” |
| 2:15–2:30 | Return to the overview. | “This demonstration uses synthetic data and a deterministic parser. The agent and MCP server share a process, and the current operator credential is a demo control. Production isolation and public access controls require separate verification.” |

## Before using the recording

- Rehearse against the exact build and verify every displayed decision and balance.
- Add real team names, contributions, AI/tool disclosure and links only after checking them against the organizer portal.
- Confirm current video duration, visibility, language and submission rules. Do not represent this script as a completed video or submission.
