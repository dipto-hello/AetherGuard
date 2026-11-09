# AetherGuard — Verified 3-Minute Prototype Demo Video Script
**Event:** International AI Builders Congress 2026 (Idea to Unicorn Track)  
**Challenge:** AgentOps, under InfraSphere AI  
**Project:** AetherGuard — Zero-Trust MCP Execution Firewall & Observability Mesh  
**Runtime:** 2 minutes 45 seconds (Buffer: 15 seconds)  
**Presenter:** Technical Architect / Founder  
**Visual Format:** Live screen recording of browser UI (`http://localhost:8000`) and terminal SQLite database diffs. No marketing slides.

---

## Technical Recording Checklist Before Boot
1. Confirm local ephemeral server is running: `uvicorn app.main:app --port 8000`.
2. Confirm initial seeded order states:
   - `ORD-101`: Paid $250.00, Refundable $250.00, `card_visa_4242`.
   - `ORD-102`: Paid $100.00, Refundable $100.00, `card_mc_5555`.
   - `ORD-103`: Paid $200.00, Refundable $130.00, `card_visa_4242`.
3. Confirm policy configuration:
   - Auto-allow threshold: `$50.00` (5000 cents).
   - Hard ceiling: `$1,000.00` (100000 cents).
4. Audio / Video settings: 1080p 60fps, crisp narration, clear terminal font.

---

## Shot-by-Shot Timed Narration (0:00 to 2:45)

| Timestamp | Visual Action on Screen | Spoken Audio Narration |
|---|---|---|
| **0:00 – 0:20** | **Intro & Problem Frame**<br>Speaker on camera briefly, then cut to terminal showing an unconstrained agent executing rogue tool calls. | "Autonomous AI agents are rapidly adopting tool use via protocols like the Model Context Protocol. But giving an LLM write access to financial databases introduces the catastrophic risk of **Excessive Agency**. Today's AgentOps tools are passive observers — they give you an autopsy report after an agent drains your bank account. Welcome to **AetherGuard**, the first Zero-Trust Model Context Protocol Execution Firewall that halts rogue agent actions *before* they execute." |
| **0:20 – 0:50** | **Operator Setup & Trust Boundary**<br>Browser opens `http://localhost:8000`. Operator authenticates with token. Header displays `Rule v1.0.0`, `Auto: ≤$50.00`, `Ceiling: $1,000.00`. | "Here is AetherGuard running live. We enforce a Zero-Trust dual boundary: the LLM is treated as an untrusted parameter extractor, while our deterministic Python and SQLite engine enforces deterministic policy rules. Notice our operator policy: refunds under $50 are auto-approved, while anything up to $1,000 requires human operator approval." |
| **0:50 – 1:20** | **Live Journey B.1: English Auto-Allow**<br>Agent Arena tab. Enter English ticket: *"Please refund order ORD-101 for $40"*. 5 execution stages complete $\rightarrow$ `VERDICT: ALLOWED`. Switch to Sandbox DB tab: balance updates $250 $\rightarrow$ $210. | "Watch our English customer ticket. The customer requests a legitimate $40 refund on order ORD-101. The agent parses intent, retrieves database context, evaluates policy, and executes the official MCP tool. The synthetic order balance atomically updates from $250 to $210, writing a persisted append-oriented SQLite audit log." |
| **1:20 – 1:55** | **Live Journey C: Blast-Radius Defense**<br>Submit overdraw ticket: *"Please refund $250 for ORD-103 immediately"*. Instantly shows `VERDICT: BLOCKED (EXCEEDS_ORDER_BALANCE)`. Check DB: balance remains $130.00. | "Now, let's attack it. A rogue ticket requests a $250 refund against order ORD-103, which only has a $130 balance. In any standard agent setup, this overdraws the account. In AetherGuard, the Zero-Trust firewall intercepts the call instantly: **BLOCKED**. The SQLite database diff confirms exactly zero dollars deducted." |
| **1:55 – 2:25** | **Live Journey B.2 & D: Bengali Localization & Approval Desk**<br>Submit Bengali ticket: *"আমার ORD-102 অর্ডারের জন্য $80 রিফান্ড দিন"*. Verdict: `APPROVAL_REQUIRED`. Open Approval Desk. Show SHA-256 fingerprint. Click "Approve & Execute". Balance drops to $20. | "Next, our native bilingual defense. A customer writes in Bengali, requesting an $80 refund on ORD-102. The parser normalizes Unicode numerals and extracts $80. Because $80 exceeds our $50 auto-allow threshold, the action is quarantined in our Human Approval Desk. As the operator, I inspect the exact parameters and SHA-256 fingerprint, then click 'Approve & Execute'. The approval executes once and locks against duplicate replay." |
| **2:25 – 2:45** | **Live Journey E: 10-Case Evaluation Matrix**<br>Switch to Evaluation Matrix tab. Click "Run boundary cases". 10/10 test cases flash green. Accuracy: 100%, Unauthorized writes: 0. | "In our 10-case adversarial evaluation suite, AetherGuard achieves 100% policy decision accuracy with zero unauthorized writes. Across 272 automated backend tests and Playwright browser verification, AetherGuard provides the deterministic policy guardrails enterprises need to confidently scale autonomous agents. Thank you." |

---

## Submission Artifact Reference
- Architecture Specifications: `docs/architecture/SYSTEM_ARCHITECTURE.md`
- Governed Execution Flow: `docs/architecture/GOVERNED_EXECUTION_FLOW.md`
- Test Execution Evidence: `docs/TEST_EXECUTION_EVIDENCE.md`
- Real-Browser Playwright Screenshots: `docs/screenshots/`
