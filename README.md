# AetherGuard

**In-Line Zero-Trust Execution Firewall & Observability Mesh for Autonomous Agent Tool Use**

AetherGuard is an open-source experimental security prototype designed to govern autonomous AI agent tool execution. Sitting in-line between probabilistic LLM agents and sensitive execution backends, AetherGuard enforces deterministic, policy-driven task scopes, real-time spending ceilings, and human-in-the-loop review over the official Model Context Protocol (MCP).

Developed as a prototype for the **International AI Builders Congress 2026** (Idea to Unicorn Track — AgentOps Challenge).

---

## Table of Contents

- [Overview & Problem Statement](#overview--problem-statement)
- [Why AetherGuard: Technical Differentiation](#why-aetherguard-technical-differentiation)
- [Implemented Capabilities vs. Planned Roadmap](#implemented-capabilities-vs-planned-roadmap)
- [Architecture Overview](#architecture-overview)
- [Governed Execution & MCP Flow](#governed-execution--mcp-flow)
- [Authentication & Trust Boundaries](#authentication--trust-boundaries)
- [Verified Technology Stack](#verified-technology-stack)
- [Repository Structure](#repository-structure)
- [Screenshots & UI Walkthrough](#screenshots--ui-walkthrough)
- [Prerequisites & Installation](#prerequisites--installation)
- [Environment Configuration](#environment-configuration)
- [Running Locally](#running-locally)
- [Running Tests & Evaluation Suite](#running-tests--evaluation-suite)
- [Container Staging (Docker)](#container-staging-docker)
- [Security Design & Known Limitations](#security-design--known-limitations)
- [Synthetic Data & Financial Simulation Disclosure](#synthetic-data--financial-simulation-disclosure)
- [Hackathon Context](#hackathon-context)
- [Project Status & Documentation Links](#project-status--documentation-links)
- [Licensing Note](#licensing-note)

---

## Overview & Problem Statement

Enterprises and developers are rapidly deploying autonomous AI agents equipped with write-capable tools (e.g., executing database mutations, payment refunds, and API updates via protocols like the Model Context Protocol). However, granting autonomous agents direct write access exposes systems to **OWASP LLM06: Excessive Agency** and prompt-injection risks.

Existing AgentOps solutions typically function as **passive telemetry platforms** ("the autopsy pattern"): they observe and log transactions *after* execution. If an agent hallucinates, misinterprets natural language, or is manipulated into executing a rogue action, passive observability merely records the financial loss or state corruption after the disaster has occurred. Furthermore, text-level guardrails lack awareness of live database balances, transactional state, and cumulative spending budgets.

**AetherGuard provides an in-line, pre-execution governance firewall**:
- Treats generative models as **untrusted parameter extractors**.
- Subjects all proposed tool calls to **deterministic Python and SQLite policy gates** before execution.
- Auto-approves low-risk, bounded transactions while quarantining high-value or ambiguous actions in an operator **Approval Desk**.
- Blocks overdraws, parameter tampering, and account diversion fail-closed with zero balance deductions.

---

## Why AetherGuard: Technical Differentiation

| Dimension | Conventional Agent Tool Use | Passive AgentOps (Autopsy Pattern) | AetherGuard Execution Firewall |
| :--- | :--- | :--- | :--- |
| **Execution Point** | Direct LLM-to-API write access | Post-execution logging & tracing | In-line pre-execution interception |
| **Governance Boundary** | Probabilistic (prompt rules only) | None (monitoring only) | Deterministic Python/SQLite state machine |
| **Balance Awareness** | Agent hallucinates balances | Logs recorded balance changes | Queries authoritative SQLite row state |
| **Cumulative Budgets** | Not tracked across turns | Aggregated post-facto | Enforced atomically via `BEGIN IMMEDIATE` |
| **Quarantine Flow** | None or ad-hoc custom code | Alerts sent after execution | Suspends action; operator approval via SHA-256 fingerprint |
| **Localization** | Dependent on model weights | Logs raw strings | Unicode normalization & bilingual EN/BN support |
| **Audit Guarantees** | Best-effort server logs | Remote SaaS telemetry | Fail-closed SQLite audit log (transaction rolls back on log failure) |

---

## Implemented Capabilities vs. Planned Roadmap

### Implemented & Empirically Verified in Current Code
- [x] **Dual-Boundary Security Model**: Strict separation between probabilistic agent reasoning and deterministic policy enforcement.
- [x] **Governed MCP Protocol Execution**: Server-side tool execution via the official Model Context Protocol (`mcp==2.3.0`) with verified caller principal binding.
- [x] **Pre-Scope Sensitive Data Minimization**: Support agent parsers are physically decoupled from the database, preventing unauthorized data reads prior to verified task scope possession.
- [x] **Deterministic Tri-Branch Policy Engine**:
  - `ALLOWED`: Transactions $\le \$50.00$ auto-execute within order balance.
  - `APPROVAL_REQUIRED`: High-value transactions ($\$50.01 - \$1,000.00$) quarantine in Approval Desk.
  - `BLOCKED`: Overdraws, balance ceiling breaches, and destination diversions blocked fail-closed.
- [x] **Human-in-the-Loop Approval Desk**: Quarantined actions display SHA-256 parameter fingerprints, with client-side synchronous in-flight locking preventing duplicate submission clicks.
- [x] **Atomic Concurrency & Deduplication**: SQLite Write-Ahead Logging (`WAL`), `BEGIN IMMEDIATE` locks, and required caller idempotency keys.
- [x] **Multi-Tier Model Fallback Chain**: Official `google-genai` SDK integration with automatic failover: `gemini-3.5-flash-lite` $\rightarrow$ `gemini-3.1-flash-lite` $\rightarrow$ `gemma-4-31b-it` $\rightarrow$ deterministic synthetic engine.
- [x] **Bilingual Ticket Processing**: Robust handling of English and Bengali natural language tickets, including Unicode numeral translation (`০-৯` to `0-9`).
- [x] **Deterministic 10-Case Evaluation Matrix**: Built-in benchmark suite measuring policy accuracy and backend side effects (100% accuracy, 0% false positives on benchmark cases).
- [x] **Single-Operator Security Controls**: Bearer token authentication with constant-time HMAC comparison, 1 MB request body streaming ceiling, and 20 RPM sliding-window rate limiting.

### Planned for Future Releases (Not Currently Implemented)
- [ ] Multi-tenant role-based access control (RBAC) with individual operator identities.
- [ ] Dynamic external policy synchronization via Open Policy Agent (OPA) / Rego rules.
- [ ] Distributed Postgres or Turso/LibSQL driver integration for multi-replica deployments.
- [ ] Hardware Security Module (HSM) or KMS-backed cryptographic signature verification for audit events.
- [ ] Production webhook egress for external enterprise SIEM systems (e.g. Datadog, Splunk).

---

## Architecture Overview

AetherGuard splits the application lifecycle into distinct zones of trust:

```mermaid
flowchart TD
    subgraph Client["Operator Interface"]
        SPA["React 19 SPA (Vite + Tailwind)<br/>In-Memory Operator Token"]
    end

    subgraph Ingress["FastAPI Ingress & Security Boundary"]
        MW["OperatorAuthMiddleware (HMAC)"]
        Guard["1MB Payload Ceiling & 20 RPM Rate Limiter"]
        CSP["Strict Content Security Policy Headers"]
        SPA -->|HTTPS / Bearer| MW --> Guard --> CSP
    end

    subgraph Agent["Support Agent (core.py)"]
        Parser["Bilingual Ticket Intake & Numeral Normalizer"]
        Minimization["Pre-Scope Data Minimization<br/>(Zero DB reads before authorization)"]
        
        subgraph LLM["Inference Chain (auto_execute=False)"]
            Gemini["Gemini 3.5 Flash Lite ➔ Gemini 3.1 ➔ Gemma 4 ➔ Synth"]
        end
        
        CSP --> Parser --> Minimization --> LLM
    end

    subgraph Governance["Deterministic Governance Firewall"]
        MCP["MCP Server & Client (mcp==2.3.0)<br/>Trusted Caller Principal Binding"]
        Scope["TaskScope Budget & Policy Engine"]
        LLM -->|Proposed Tool Call| MCP --> Scope
    end

    subgraph Decisions["Tri-Branch Decision Logic"]
        Allow["ALLOWED (<= $50.00)"]
        Quarantine["APPROVAL_REQUIRED ($50 - $1,000)"]
        Block["BLOCKED (Overdraw / Diversion)"]
        Scope --> Allow
        Scope --> Quarantine
        Scope --> Block
    end

    subgraph Storage["Authoritative SQLite Sandbox"]
        Desk["Human Approval Desk (SHA-256 Fingerprint)"]
        Ledger["Atomic SQLite Ledger (WAL mode)<br/>BEGIN IMMEDIATE · Fail-Closed Audit"]
        
        Allow --> Ledger
        Quarantine --> Desk -->|Operator Approve| Ledger
        Block -->|Audit Only| Ledger
    end
```

Detailed architectural diagrams and component specifications are documented in [`docs/architecture/SYSTEM_ARCHITECTURE.md`](docs/architecture/SYSTEM_ARCHITECTURE.md) and [`docs/architecture/system_architecture.html`](docs/architecture/system_architecture.html).

---

## Governed Execution & MCP Flow

A support ticket executes through five deterministic stages:

```mermaid
sequenceDiagram
    autonumber
    participant Client as React 19 Client
    participant Agent as Support Agent
    participant MCP as Governed MCP Firewall
    participant Desk as Approval Desk
    participant DB as SQLite Sandbox

    Client->>Agent: Submit ticket with Idempotency Key
    Agent->>Agent: Parse ticket & normalize numerals (zero DB reads)
    Agent->>Agent: Model generates proposed refund_order tool call
    Agent->>MCP: Submit proposed tool call
    MCP->>MCP: Verify caller identity & active TaskScope
    MCP->>DB: Check idempotency registry (replay defense)
    MCP->>DB: Evaluate order refundable balance
    
    alt <= $50.00 and within balance
        MCP->>DB: ATOMIC EXECUTE: Deduct balance + write audit log
        MCP-->>Client: VERDICT: ALLOWED (Refund executed)
    else $50.01 - $1,000.00
        MCP->>DB: Quarantine action & register SHA-256 fingerprint
        MCP-->>Client: VERDICT: APPROVAL_REQUIRED
        Client->>Desk: Operator reviews proposal & fingerprint
        Desk->>DB: Operator approves -> ATOMIC EXECUTE balance deduction
    else Exceeds balance or hard ceiling
        MCP->>DB: Write BLOCKED audit log ($0 deducted)
        MCP-->>Client: VERDICT: BLOCKED
    end
```

Full step-by-step trace documentation is available in [`docs/architecture/GOVERNED_EXECUTION_FLOW.md`](docs/architecture/GOVERNED_EXECUTION_FLOW.md) and [`docs/architecture/governed_execution_flow.html`](docs/architecture/governed_execution_flow.html).

---

## Authentication & Trust Boundaries

1. **Client-to-Server Ingress Boundary**:
   - Single-operator Bearer token authentication (`AETHERGUARD_OPERATOR_TOKEN`).
   - Constant-time verification using `hmac.compare_digest` in `OperatorAuthMiddleware`.
   - Protects all `/api/*` endpoints (except `/api/health`).
   - Token is held strictly in volatile React component state, never in browser storage.
2. **Model Trust Boundary**:
   - The LLM is never given direct database credentials or network access to the database.
   - The SDK's automated function execution is explicitly disabled (`auto_execute=False`).
   - Model outputs are parsed as untrusted parameter proposals.
3. **MCP Tool Authorization Boundary**:
   - Caller principal identity is bound by the server session, rejecting client-side `caller_id` spoofing attempts.
   - Task scopes enforce cumulative spending caps and tool allowlists.
4. **Data Minimization Boundary**:
   - `lookup_order` omits customer names and raw card numbers, returning only masked references (`card...4242`).
   - Ticket parsing operates strictly without database reads until scope validity is established.

---

## Verified Technology Stack

All dependencies are verified directly against source manifests (`backend/requirements.txt` and `frontend/package.json`):

### Backend & Governance
- **Python**: 3.12+ (runtime verified on 3.12.10)
- **FastAPI**: `fastapi>=0.115.0`
- **ASGI Server**: `uvicorn[standard]>=0.30.0`
- **Data Validation**: `pydantic>=2.8.0`
- **MCP Protocol**: Official `mcp==2.3.0` Python SDK
- **Inference Client**: Official Google GenAI SDK `google-genai>=3.0.0`
- **Database Engine**: Embedded SQLite 3 with Write-Ahead Logging (`WAL`), `BEGIN IMMEDIATE` transactions, and busy timeouts

### Frontend & Operator UI
- **Framework**: React 19 (`react: ^19.3.1`, `react-dom: ^19.3.1`)
- **Build System**: Vite 8 (`vite: ^8.3.6`) with TypeScript 7 (`typescript: ~7.0.2`)
- **Styling**: Tailwind CSS (`tailwindcss: ^3.4.17`, `autoprefixer: ^10.6.2`)
- **Icons & UI Utilities**: `lucide-react: ^1.70.0`, `clsx: ^2.1.1`, `tailwind-merge: ^3.7.0`
- **Linter**: Oxlint (`oxlint: ^1.90.0`)

---

## Repository Structure

```
AetherGuard/
├── backend/                         # FastAPI & Governance Backend
│   ├── app/
│   │   ├── agent/                   # Bilingual Support Agent & LLM Fallback Chain
│   │   │   ├── core.py              # Ticket parsing, minimization, & model inference
│   │   │   └── tickets.py           # Synthetic ticket definitions & helpers
│   │   ├── api/                     # REST API Route Handlers
│   │   │   ├── agent.py             # /api/agent endpoints (ticket processing)
│   │   │   ├── approval.py          # /api/approval endpoints (approval review)
│   │   │   ├── evaluation.py        # /api/evaluation endpoints (matrix benchmark)
│   │   │   ├── governance.py        # /api/governance endpoints (policy & scopes)
│   │   │   └── sandbox.py           # /api/sandbox endpoints (orders & ledger)
│   │   ├── approval/                # Human-in-the-Loop Quarantine & Fingerprinting
│   │   │   └── service.py           # SHA-256 fingerprint verification & execution
│   │   ├── evaluation/              # Deterministic Evaluation Benchmark Suite
│   │   │   ├── cases.py             # 10 benchmark adversarial & baseline test cases
│   │   │   └── runner.py            # Evaluation runner & metric telemetry
│   │   ├── governance/              # Model Context Protocol Server & Boundaries
│   │   │   ├── boundary.py          # GovernanceBoundary policy orchestration
│   │   │   └── mcp_server.py        # Governed MCP server & refund_order tool
│   │   ├── policy/                  # Policy Models, Storage, & Decision Engine
│   │   │   ├── engine.py            # Pure deterministic tri-branch policy logic
│   │   │   ├── models.py            # Pydantic schemas (TaskScope, PolicyRule)
│   │   │   └── storage.py           # SQLite policy & scope persistence
│   │   ├── sandbox/                 # Authoritative SQLite Database Layer
│   │   │   ├── db.py                # Schema initialization & WAL configuration
│   │   │   └── service.py           # Atomic balance mutations & audit logging
│   │   ├── auth.py                  # OperatorAuthMiddleware constant-time HMAC check
│   │   ├── main.py                  # FastAPI app entrypoint, rate limit, & static mount
│   │   └── mcp_entrypoint.py        # Standalone MCP stdio server entrypoint
│   ├── tests/                       # Comprehensive Pytest Test Suite (272 tests)
│   │   ├── approval_check.py        # Standalone approval unit test suite (6 tests)
│   │   └── test_*.py                # 27 regression, adversarial, & invariant suites
│   ├── pytest.ini                   # Pytest configuration
│   └── requirements.txt             # Locked backend Python dependencies
├── frontend/                        # React 19 Operator Control Plane
│   ├── src/
│   │   ├── components/              # UI Views: AgentArena, ApprovalDesk, AuditLedger,
│   │   │                            # PolicyManager, SandboxViewer, EvaluationMatrix
│   │   ├── api.ts                   # In-memory API client & error extractor
│   │   ├── App.tsx                  # Main layout, tab navigation, & login view
│   │   └── main.tsx                 # React DOM mount point
│   ├── tests/                       # Frontend Node & concurrency tests (9 tests)
│   ├── package.json                 # Locked frontend npm dependencies
│   ├── tsconfig.json                # TypeScript project configuration
│   └── vite.config.ts               # Vite build & proxy configuration
├── docs/                            # Project Specifications & Architectural Evidence
│   ├── architecture/                # System Architecture & Flow Specifications
│   │   ├── SYSTEM_ARCHITECTURE.md   # Architectural breakdown & Mermaid diagram
│   │   ├── GOVERNED_EXECUTION_FLOW.md # Sequence flow & decision state machine
│   │   ├── system_architecture.html # Standalone editorial HTML/SVG diagram
│   │   └── governed_execution_flow.html # Standalone editorial HTML/SVG flowchart
│   ├── screenshots/                 # Authentic UI Playwright screenshots
│   ├── 01_PRD.md                    # Product Requirements Document
│   ├── 04_TRD.md                    # Technical Requirements Document
│   ├── 05_Schema.md                 # Database Schema & API Wire Specifications
│   ├── 07_Submission_Package.md     # Hackathon submission summary & disclosures
│   ├── DEMO_VIDEO_SCRIPT.md         # Timed 3-minute demonstration script
│   ├── FREE_HOSTING_EVALUATION.md   # Comprehensive free-tier cloud hosting analysis
│   ├── REVIEW_STATUS.md             # Chronological verification log
│   └── TEST_EXECUTION_EVIDENCE.md   # Empirical test run evidence & metrics
├── Dockerfile                       # Multi-stage production container definition
├── .dockerignore                    # Container build exclusion list
├── .gitignore                       # Repository ignore filters (secrets, databases)
├── .env.example                     # Environment template with safe placeholders
├── NEXT_SESSION_HANDOVER.md         # Concise continuation notes for next session
└── README.md                        # Primary project documentation (this file)
```

---

## Screenshots & UI Walkthrough

The following screenshots depict the actual, functioning AetherGuard user interface:

### 1. Agent Arena — Bilingual Ticket Intake & Governed Execution
The operator enters a customer refund ticket. The 5-stage pipeline displays language detection, parameter extraction, and deterministic policy evaluation:

![Agent Arena Allowed](docs/screenshots/journey_b_1_english_ticket_allowed.png)

### 2. Blast-Radius Defense — Overdraw Blocked Fail-Closed
When a rogue ticket requests a refund exceeding the synthetic order balance, the policy engine intercepts the call and blocks execution without deducting funds:

![Blast-Radius Defense](docs/screenshots/journey_c_blast_radius_blocked.png)

### 3. Human Approval Desk — Parameter Inspection & SHA-256 Fingerprint
High-value transactions ($\$50.01 - \$1,000.00$) are suspended. The operator inspects the proposed deduction and verifies the SHA-256 fingerprint before approving:

![Approval Desk](docs/screenshots/journey_d_1_approval_desk_pending.png)

### 4. Deterministic Evaluation Matrix — 10-Case Benchmark Suite
The built-in evaluation suite runs 10 adversarial and boundary test cases against an isolated database, reporting 100% decision accuracy:

![Evaluation Matrix](docs/screenshots/journey_e_2_matrix_results.png)

*Additional authentic screenshots covering 320px–1440px responsive viewports and error recovery are available in [`docs/screenshots/`](docs/screenshots/).*

---

## Prerequisites & Installation

### System Prerequisites
- **Python**: Version 3.12+ installed
- **Node.js**: Version 20+ or 22+ (tested with Node 22)
- **Package Managers**: `pip` and `npm`
- **Operating System**: Windows (PowerShell), macOS, or Linux

---

## Environment Configuration

A safe template is provided in [`.env.example`](.env.example). Copy it to `.env` or set environment variables in your active shell:

```powershell
# Required: Secret operator token for single-operator access control (Bearer authentication)
$env:AETHERGUARD_OPERATOR_TOKEN = "replace_with_a_secure_random_operator_token_min_32_chars"

# Optional: Google Gemini API key for live multimodal agent proposals
# If omitted or unset, AetherGuard runs in deterministic synthetic mode
$env:GEMINI_API_KEY = ""

# Optional: Rate limit configuration (default: 20 requests per minute)
$env:AETHERGUARD_RATE_LIMIT_PER_MINUTE = "20"
```

> [!CAUTION]
> Never commit real secrets or `.env` files to version control. The repository `.gitignore` strictly excludes `.env` and credential files.

---

## Running Locally

### Option 1: Full-Stack Development Mode (Two Terminals)

**Terminal 1 — Backend (FastAPI)**:
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:AETHERGUARD_OPERATOR_TOKEN = "your-secure-demo-token-1234567890"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**Terminal 2 — Frontend (Vite Dev Server)**:
```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser. Enter your configured operator token to access the dashboard.

### Option 2: Unified Production Mode (Single Port 8000)

Build the frontend once, and FastAPI will automatically serve the static bundle from `frontend/dist`:

```powershell
# 1. Build frontend
cd frontend
npm ci
npm run build
cd ..

# 2. Start unified backend
cd backend
$env:AETHERGUARD_OPERATOR_TOKEN = "your-secure-demo-token-1234567890"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000` directly in your browser.

---

## Running Tests & Evaluation Suite

Every test suite can be run completely offline with zero external network dependencies:

### 1. Backend Full Pytest Suite (272 Tests)
```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -v
```
*Current verified result: **272 passed** in ~17.5s (includes adversarial, invariant, rate limit, and MCP boundary suites).*

### 2. Standalone Approval Unit Tests (6 Tests)
```powershell
cd backend
$env:PYTHONPATH = "."
.\.venv\Scripts\python.exe tests/approval_check.py
```
*Current verified result: **6 passed** in 0.01s.*

### 3. Frontend Node Tests (9 Tests)
```powershell
cd frontend
node tests/api.test.mjs
node tests/approval_concurrency_stress.test.mjs
```
*Current verified result: **9 passed** (covers API error extraction, idempotency headers, and multi-click race locking).*

### 4. Frontend Lint & Production Build
```powershell
cd frontend
npm run lint    # Runs oxlint (0 errors, 0 warnings across 16 files)
npm run build   # Runs tsc -b and vite build (clean build, 0 errors)
```

### 5. Deterministic Evaluation Benchmark Suite (10 Cases)
```powershell
cd backend
$env:PYTHONPATH = "."
.\.venv\Scripts\python.exe -c "from app.evaluation.runner import run_evaluation_suite; import json; res = run_evaluation_suite(); print(json.dumps({k: v for k, v in res.items() if k != 'cases'}, indent=2))"
```
*Current verified result: **10/10 cases passed** (100.0% accuracy, 0 unauthorized writes, 0.0% false positive rate).*

---

## Container Staging (Docker)

The multi-stage [`Dockerfile`](Dockerfile) builds the React frontend in Node 22 Alpine, packages it into a lightweight Python 3.12 slim container, runs as non-root user `aetherguard` (UID 10001), and serves both API and static UI on port 8000:

```sh
# 1. Build the unified container image
docker build -t aetherguard:latest .

# 2. Create a persistent volume for the SQLite database
docker volume create aetherguard-data

# 3. Run container locally
docker run --name aetherguard \
  -e AETHERGUARD_OPERATOR_TOKEN="your-secure-demo-token-1234567890" \
  -e AETHERGUARD_DB_PATH="/data/sandbox.db" \
  --mount source=aetherguard-data,target=/data \
  -p 127.0.0.1:8000:8000 \
  aetherguard:latest
```

*Note: For free cloud hosting evaluation and limitations, see [`docs/FREE_HOSTING_EVALUATION.md`](docs/FREE_HOSTING_EVALUATION.md).*

---

## Security Design & Known Limitations

AetherGuard is an experimental prototype designed to explore in-line agent governance. When evaluating this project, note the following verified security boundaries and limitations:

1. **Single-Operator Authentication**: The system uses a shared bearer token (`AETHERGUARD_OPERATOR_TOKEN`) designed for local demonstrations. It does **not** provide multi-user role separation, granular operator auditing, or identity provider federation.
2. **Local In-Process Trust Model**: In the local configuration, the agent and FastAPI backend run in the same Python process sharing an SQLite database connection. While tool execution is mediated via MCP, physical process isolation (e.g. running the agent in an untrusted sandbox container) is not implemented.
3. **Audit Log Persistence**: Audit events are recorded in local SQLite database tables with WAL mode and atomic rollback. They are not stored in an append-only cryptographic ledger or external SIEM, and could be modified by anyone with direct operating system access to the SQLite file.
4. **Heuristic Synthetic Parser**: The deterministic synthetic parser uses regex and keyword heuristics for English and Bengali tickets. While effective for benchmark testing, it does not possess full semantic language comprehension and should not be relied upon for arbitrary unstructured text.
5. **No Real Banking Connectivity**: All orders (`ORD-101` to `ORD-104`), card tokens (`card_visa_4242`), and refund amounts are entirely synthetic simulations. No financial institution or payment network is connected.

---

## Synthetic Data & Financial Simulation Disclosure

All operational data within AetherGuard is strictly synthetic:
- **Order Identifiers**: `ORD-101`, `ORD-102`, `ORD-103`, `ORD-104`
- **Synthetic Balances**: Simulated in integer minor units (cents / poisha)
- **Payment Destinations**: Synthetic test identifiers (`card_visa_4242`, `card_mc_5555`, `bkash_01711000000`)
- **Customer Identities**: Fictional names used strictly for localization testing

Resetting the sandbox via the UI or calling `init_db()` safely restores the initial seeded state without affecting any external system.

---

## Hackathon Context

- **Event**: International AI Builders Congress 2026
- **Track**: Idea to Unicorn (Team)
- **Challenge**: AgentOps, under InfraSphere AI
- **Team**: AetherOps AI
- **Status**: Completed Local Polish & Frozen for Private Review

Full submission package details, timed pitch video script, and compliance disclosures are recorded in [`docs/07_Submission_Package.md`](docs/07_Submission_Package.md) and [`docs/DEMO_VIDEO_SCRIPT.md`](docs/DEMO_VIDEO_SCRIPT.md).

---

## Project Status & Documentation Links

- **System Architecture**: [`docs/architecture/SYSTEM_ARCHITECTURE.md`](docs/architecture/SYSTEM_ARCHITECTURE.md)
- **Governed Execution Flow**: [`docs/architecture/GOVERNED_EXECUTION_FLOW.md`](docs/architecture/GOVERNED_EXECUTION_FLOW.md)
- **Standalone HTML Diagrams**: [`docs/architecture/system_architecture.html`](docs/architecture/system_architecture.html) & [`docs/architecture/governed_execution_flow.html`](docs/architecture/governed_execution_flow.html)
- **Product Requirements Document (PRD)**: [`docs/01_PRD.md`](docs/01_PRD.md)
- **Technical Requirements Document (TRD)**: [`docs/04_TRD.md`](docs/04_TRD.md)
- **Database Schema Specification**: [`docs/05_Schema.md`](docs/05_Schema.md)
- **Test Execution Evidence**: [`docs/TEST_EXECUTION_EVIDENCE.md`](docs/TEST_EXECUTION_EVIDENCE.md)
- **Free Cloud Hosting Evaluation**: [`docs/FREE_HOSTING_EVALUATION.md`](docs/FREE_HOSTING_EVALUATION.md)
- **Review & Verification History**: [`docs/REVIEW_STATUS.md`](docs/REVIEW_STATUS.md)
- **Next Session Handover**: [`NEXT_SESSION_HANDOVER.md`](NEXT_SESSION_HANDOVER.md)

---

## Licensing Note

The open-source license for AetherGuard is currently undecided and requires an explicit future decision prior to public release. No arbitrary license has been applied.
