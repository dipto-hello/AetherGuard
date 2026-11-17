# AI claim judge with photo evidence

## Intent

Before a refund proposal reaches the policy engine, an AI judge reviews the customer's story and an optional evidence photo and decides whether the claim is still valid. The policy rules only check numbers (scope, balance, limits, destination); the judge adds a sense check on the claim itself. The rule is: the AI judges the story, the database and policy decide the money, a human handles unclear cases.

## Goals

- The operator can attach one evidence photo to a ticket on the **Test a refund** tab.
- A Gemini judge returns `valid`, `unsure`, or `invalid` with a short reason before the proposal step.
- Only `valid` claims continue to the existing proposal, policy, and approval flow, unchanged.
- `unsure` and `invalid` move no money. The trace shows "Needs human review" with the judge's reason; the operator can add evidence and resubmit.

## Non-goals

- Customer-facing claim page, customer login, automatic scopes (option B, rejected).
- Auto-rejecting customers, or creating a pending approval for unsure claims.
- Checking that the photo shows the purchased product (orders do not record products).
- Fake-photo detection, duplicate-photo hashing, storing photos.

## Anti-goals

- The judge must never unblock or approve anything. A `valid` judgment only lets the claim reach the unchanged policy.
- Any judge failure (error, timeout, bad output, text-only model with a photo) must not count as `valid`.
- No real customer photos in the demo; synthetic only.

## Approaches

1. **Separate judge call before the proposal (picked).** Its own focused prompt; existing proposal, policy, and approval code untouched. Costs a second Gemini call per claim.
2. One combined call adding judgment fields to the proposal. Cheaper, but the same call that proposes payment decides validity, so one tricky message fools both.
3. Judge after the policy as a brake only. Dropped: reverses the requested order (judge first, then policy).

## Revision 2026-11-17: unsure goes to Approvals

After manual testing, the user chose: **unsure → human approval, invalid → blocked**. An unsure claim runs the proposal and every rule; if the rules allow it, the existing `require_refund_approval` switch forces it into Approvals (`arguments.reason` = `AI judge unsure: <reason>`, shown on the approval card). Rules that block still block. Invalid claims skip the proposal and are blocked with `CLAIM_INVALID: <reason>`. This supersedes the non-goal about not creating pending approvals.

## Revision 2026-11-17: refund eligibility policy

The judge now also checks eligibility, not only believability. A fixed policy in `SupportAgent.REFUND_ELIGIBILITY_POLICY` (option A: in code, not operator-editable) refunds problems the company is responsible for (arrived damaged, wrong or missing item, never delivered, defective) and refuses customer-caused damage after delivery (including breaking it while opening) and change of mind. Unclear fault → `unsure`.

## Design

**API** (`backend/app/api/agent.py`): `ProcessTicketRequest` gains optional `evidence_image` (base64 string) and `evidence_mime_type` (`image/jpeg`, `image/png`, `image/webp`). The server rejects bad base64, a mime type outside that list, or bytes whose file signature does not match the mime type (HTTP 422). The existing 1 MB request cap stays.

**Frontend** (`AgentArena.tsx`, `api.ts`): one optional photo picker. The browser shrinks the photo (longest side 1280 px, JPEG) before sending so it fits under 1 MB, shows a small preview with a remove button, and displays the judge stage in the existing pipeline view.

**Judge** (`backend/app/agent/core.py`): new `_judge_claim_llm(ticket_text, image)` using the same Gemini client pattern as `_parse_ticket_llm`: one forced function call `judge_claim(verdict: valid|unsure|invalid, reason: string)`, automatic function calling disabled, ticket and image marked untrusted, text inside the image treated as evidence and never as instructions. It walks the model chain but skips text-only models when a photo is attached. Any failure returns `unsure` with a failure reason.

**Flow in `process_ticket`:** judge runs first. On `valid`, everything continues exactly as today. Otherwise the proposal call is skipped, the amount is forced to 0 (the same pattern as the existing mismatch checks), the governed tool still runs so the attempt is recorded as BLOCKED in the audit trail, and the reason becomes `CLAIM_NEEDS_REVIEW: <judge reason>`. With no Gemini key configured, behavior is unchanged (`model_not_configured`).

**Trace:** adds `claim_judgment: {verdict, reason}` and a new pipeline stage "AI Claim Judge" before the proposal stage.

**Tests:** `conftest.py` patches the judge offline to return `valid` so existing tests keep passing. New tests cover: unsure/invalid moves no money and records a BLOCKED action with the review reason; judge failure fails closed; image validation rejects bad base64, wrong mime, and mismatched file signatures; text-only models are skipped when a photo is present.

## Calls made by Claude (check these)

- The photo is **optional**. Without one, the judge rules on the message alone.
- No separate order ID or payment method fields: the existing **Refund permission** panel already sets the order and destination, and the ticket text names them.
- The judge does not see order data from the database; amount and balance checks stay with the policy.
- One photo per ticket.

## Left to the builder

The exact judge prompt wording, the stage styling, and the test file layout.
