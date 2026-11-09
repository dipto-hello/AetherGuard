# AetherGuard — Verified Hackathon Submission Package
**Event:** International AI Builders Congress 2026  
**Track:** Idea to Unicorn (Team)  
**Challenge:** AgentOps, under InfraSphere AI  
**Team:** AetherOps AI  
**Status:** **VERIFIED & FINALIZED (Local Pre-GitHub Freeze)**  
**Verification Evidence:** [`TEST_EXECUTION_EVIDENCE.md`](TEST_EXECUTION_EVIDENCE.md) · [`architecture/SYSTEM_ARCHITECTURE.md`](architecture/SYSTEM_ARCHITECTURE.md)  

---

## 1. Project Details
- **Project Name:** AetherGuard — Zero-Trust MCP Execution Firewall & Observability Mesh for Autonomous AI Agents
- **Git State:** Local pre-release freeze on branch `main` (0 remote repositories, 0 pushed commits)
- **Compliance Rules Verified:**
  - Official [Submission Rules](https://cloudcampbd.com/events/ai-builders-congress/policies/submission): 1-page summary, 3-minute prototype demo video script, localization handling, and full disclosures.
  - Official [AI Usage Policy](https://cloudcampbd.com/events/ai-builders-congress/policies/ai-usage): Full transparency on generative models, automated coding agents, synthetic datasets, and human architectural validation.
  - Official [Terms & Conditions](https://cloudcampbd.com/events/ai-builders-congress/policies/terms): Intellectual property ownership, ethical AI adherence, and zero malicious behavior.

---

## 2. One-Page Structured Project Summary

### The Problem: Excessive Agency & The "Autopsy" Trap
Enterprises are aggressively deploying autonomous AI agents powered by LLMs with tool-use capabilities (Model Context Protocol, function calling). However, granting agents write access to enterprise APIs introduces the catastrophic risk of **OWASP LLM06: Excessive Agency**. Existing AgentOps tools (LangSmith, AgentOps.ai, Arize Phoenix) act as passive post-mortem loggers — they record that an agent siphoned $10,000 or deleted customer records *after* the disaster has occurred ("The Autopsy Problem"). Furthermore, text guardrails (Bedrock, NeMo) have zero awareness of database balances, transaction states, or cumulative spending budgets.

### The Solution: In-Line Zero-Trust Execution Firewall
AetherGuard is an inline, pre-execution governance firewall that sits between AI agent runtimes and tool execution backends. It treats the LLM as an **untrusted parameter extractor**, strictly subjecting all proposed tool actions to deterministic Python/SQL policy gates before execution can occur. If a tool call exceeds policy ceilings or order balances, it is either blocked instantly or quarantined in a Human-in-the-Loop Approval Desk requiring operator SHA-256 parameter integrity verification.

### Technical Architecture & Tech Stack
- **Execution Firewall**: FastAPI, Python 3.12, official MCP Python SDK (`mcp 2.3.0`), deterministic policy state-machine.
- **Authoritative Ledger**: Embedded SQLite with Write-Ahead Logging (WAL mode), immediate row locks (`BEGIN IMMEDIATE`), and 5000ms busy timeouts.
- **Inference Chain**: Google Gemini 3.5 Flash Lite $\rightarrow$ Gemini 3.1 Flash Lite $\rightarrow$ Gemma 4 31B IT $\rightarrow$ Deterministic Fail-Closed Boundary.
- **Operator Interface**: React 19 / Vite 8 SPA, Tailwind CSS 3.4, accessible WCAG 2.1 AA architecture, responsive 320px–1440px.
- **Edge Security Guidance**: Single-instance containerization, Cloudflare Authenticated Origin Pulls (AOP), Full (Strict) TLS, and dual-path Turnstile bot mitigation with machine API bypass.

### Empirical Key Metrics & Verification Evidence
- **272 / 272 Backend Pytest Tests Passing** (100% pass rate in ~17.5s, plus 6 standalone unittests and 9 frontend tests, clean TypeScript/Vite build in ~590ms).
- **12 / 12 Security Invariants (INV-01 to INV-12) Empirically Verified**: 0 counterexamples under heavy concurrency (20 parallel threads, $0 over-allocation, 0 duplicate idempotent replays).
- **100% Policy Decision Accuracy**: 10/10 adversarial benchmark cases passed with 0 unauthorized backend writes and 0% False Positive Rate.
- **7 / 7 Real-Browser User Journeys Verified**: 17 authentic Playwright PNG screenshots located in [`docs/screenshots/`](screenshots/) verifying bilingual English/Bengali execution, blast-radius defense ($250 blocked against $130), Approval Desk single-use locking, and 320px–1440px responsive layouts.

### Real-World Impact & Ethical Compliance
AetherGuard provides the missing safety rail necessary for enterprises to deploy autonomous agents in regulated financial, customer service, and e-commerce domains. By establishing verifiable audit trails and preventing runaway actions, AetherGuard enables safe, scalable AI autonomy while maintaining human oversight.

---

## 3. Three-Minute Timed Prototype Video Pitch Script
See complete shot-by-shot script in [`DEMO_VIDEO_SCRIPT.md`](DEMO_VIDEO_SCRIPT.md).
- **Runtime:** 0:00 to 2:45 (Buffer: 15s)
- **Live Sequence:**
  1. 0:00–0:20: Problem statement (Excessive agency, autopsy problem).
  2. 0:20–0:50: Dual-boundary architecture & operator policy setup.
  3. 0:50–1:20: English ticket auto-allow execution ($40 on ORD-101) & ledger verification.
  4. 1:20–1:55: Blast-radius defense ($250 refund blocked against $130 balance, $0 deducted).
  5. 1:55–2:25: Bengali ticket processing, Unicode normalization, Human Approval Desk workflow with SHA-256 fingerprinting.
  6. 2:25–2:45: 10-Case Evaluation Matrix execution (100% accuracy, 0 unauthorized writes).

---

## 4. AI Usage & Provenance Disclosures
- **Generative Models:** Gemini 3.5 Flash Lite, Gemini 3.1 Flash Lite, Gemma 4 31B IT, deterministic synthetic fallback.
- **Fail-Closed Rule:** All model timeouts and quota exhaustions strictly return amount 0 and `BLOCKED` verdict (INV-06).
- **Synthetic Fixtures:** 100% synthetic sandbox data (`ORD-101` to `ORD-104`, synthetic customer names, synthetic test cards).
- **Human Contribution & Architectural Validation:** All core architecture, trust boundaries, state machines, and concurrency invariants were engineered, audited, and verified by human software engineers.

---

## 5. Truthful Release Gates (G1 to G16) Summary
All 16 gates evaluated strictly on physical evidence:
- **G1 (Git Checkpoint):** PASS (Clean local tree, 0 remotes)
- **G2 (Database Backup):** PASS (Bit-for-bit verified local storage)
- **G3 (Backend Tests):** PASS (272/272 passed)
- **G4 (Frontend Build):** PASS (9/9 tests passed, 0 oxlint warnings, clean React 19 build)
- **G5 (INV-01 Bounds):** PASS
- **G6 (INV-02 Atomic Scope Budget):** PASS
- **G7 (INV-03 Exactly-Once):** PASS
- **G8 (INV-04 Deterministic Auth):** PASS
- **G9 (INV-05 Trusted Approval Binding):** PASS
- **G10 (INV-06 Fail-Closed):** PASS
- **G11 (INV-07 & INV-08 Unified Bounds):** PASS
- **G12 (INV-09 & INV-11 Isolation):** PASS
- **G13 (INV-10 & INV-12 Audit & Crash Safety):** PASS
- **G14 (Browser E2E Journeys A-G):** PASS (17 screenshots in `docs/screenshots/`)
- **G15 (Single-Instance Container):** PASS WITH ADVISORIES (SQLite single-writer verified)
- **G16 (Cloudflare Edge & Submission Package):** PASS
