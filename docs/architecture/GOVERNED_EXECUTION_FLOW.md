# AetherGuard — Governed Refund Execution Flow

## 1. Overview

This document specifies the exact lifecycle of a support-ticket refund request as it progresses from unstructured user input through the probabilistic agent boundary, into the deterministic governance firewall, and finally to atomic execution and audit trail recording.

---

## 2. Governed Refund Execution Flow Diagram

```mermaid
sequenceDiagram
    autonumber
    actor Customer as Customer / Ticket Issuer
    participant Frontend as React 19 Client
    participant API as FastAPI Ingress
    participant Agent as Support Agent (core.py)
    participant LLM as Gemini / Gemma Model
    participant MCP as Governed MCP Server
    participant Policy as Policy Engine
    participant Desk as Approval Desk
    participant DB as SQLite Sandbox (WAL)

    Note over Customer,API: Stage 1: Ingress & Token Authentication
    Customer->>Frontend: Submit ticket ("Refund $40 on ORD-101")
    Frontend->>API: POST /api/agent/process-ticket (Bearer Token + Idempotency Key)
    API->>API: OperatorAuthMiddleware validates HMAC Bearer token
    API->>API: Enforce 1MB payload ceiling & sliding-window rate limit

    Note over API,LLM: Stage 2: Agent Proposal & Sensitive Data Minimization
    API->>Agent: process_ticket(ticket_text, task_scope_id)
    Agent->>Agent: Pre-Scope Minimization: Zero DB reads on unauthenticated input
    Agent->>Agent: Bilingual detection & numeral normalization (০-৯ -> 0-9)
    Agent->>LLM: Structured tool proposal prompt (auto_execute=False)
    LLM-->>Agent: Proposed tool: refund_order(order_id, amount, currency, destination)

    Note over Agent,Policy: Stage 3: MCP Governance & Scope Verification
    Agent->>MCP: Client call: refund_order(proposal + idempotency_key)
    MCP->>MCP: Authenticate caller principal (reject spoofed caller_id)
    MCP->>DB: Check idempotency key in action registry
    alt Idempotency Hit (Replay)
        DB-->>MCP: Existing action record found
        MCP-->>Frontend: Return cached execution result (Zero duplicate write)
    else New Request
        MCP->>DB: Fetch TaskScope by ID (Verify active & unexpired)
        MCP->>DB: Lookup order state (refundable balance & original destination)
        MCP->>Policy: evaluate_policy(proposal, task_scope, order_balance)
        
        alt Policy Verdict: BLOCKED
            Note over Policy,DB: Case A: Policy Ceiling, Overdraw, or Diversion Violation
            Policy-->>MCP: BLOCKED (e.g. EXCEEDS_BALANCE, DESTINATION_MISMATCH)
            MCP->>DB: Write Audit Event (BLOCKED, reason, 0 balance change)
            MCP-->>Frontend: Return {verdict: "BLOCKED", reason: "..."}
        
        else Policy Verdict: ALLOWED
            Note over Policy,DB: Case B: Low-Risk Auto-Allow (<= $50.00 threshold)
            Policy-->>MCP: ALLOWED (Within auto-allow ceiling & order balance)
            MCP->>DB: BEGIN IMMEDIATE transaction
            MCP->>DB: UPDATE orders SET refundable_amount = refundable_amount - amount
            MCP->>DB: UPDATE task_scopes SET remaining_budget = remaining_budget - amount
            MCP->>DB: INSERT INTO audit_events (ALLOWED, amount, order_id, duration)
            MCP->>DB: COMMIT transaction (Atomic rollback if audit write fails)
            MCP-->>Frontend: Return {verdict: "ALLOWED", executed_amount: 4000}
        
        else Policy Verdict: APPROVAL_REQUIRED
            Note over Policy,Desk: Case C: High-Value Quarantine (> $50.00 & <= $1,000.00)
            Policy-->>MCP: APPROVAL_REQUIRED (Exceeds auto-allow threshold)
            MCP->>DB: Compute SHA-256 fingerprint of exact proposal parameters
            MCP->>DB: Register pending action in quarantine queue
            MCP->>DB: INSERT INTO audit_events (APPROVAL_REQUIRED, fingerprint)
            MCP-->>Frontend: Return {verdict: "APPROVAL_REQUIRED", action_id: "...", fingerprint: "..."}
            
            Note over Frontend,DB: Human-in-the-Loop Operator Resolution
            Frontend->>Desk: View quarantined action on Approval Desk
            actor Operator as Human Operator
            Operator->>Desk: Inspect parameters, order diff, and SHA-256 fingerprint
            Operator->>Desk: Click "Approve & Execute"
            Desk->>Desk: Synchronous in-flight lock engages (prevents rapid double-click)
            Desk->>API: POST /api/governance/approve-action (action_id, fingerprint)
            API->>DB: Verify original SHA-256 fingerprint match & scope budget
            API->>DB: BEGIN IMMEDIATE transaction
            API->>DB: UPDATE orders SET refundable_amount = refundable_amount - amount
            API->>DB: UPDATE task_scopes SET remaining_budget = remaining_budget - amount
            API->>DB: UPDATE action_requests SET status = 'EXECUTED'
            API->>DB: INSERT INTO audit_events (APPROVED_BY_OPERATOR, amount)
            API->>DB: COMMIT transaction
            API-->>Frontend: Return {status: "EXECUTED", new_balance: 2000}
        end
    end
```

---

## 3. Decision Branch Matrix & Reason Codes

The deterministic policy engine branches across three distinct outcomes based on mathematical and cryptographic invariants:

| Outcome | Trigger Condition | System Action | Sandbox Effect |
| :--- | :--- | :--- | :--- |
| **ALLOWED** | $\text{Amount} \le \text{Auto-Allow Threshold}$ ($50.00)<br>$\land \text{Amount} \le \text{Order Balance}$<br>$\land \text{Destination} == \text{Original Payment}$<br>$\land \text{Currency} == \text{Order Currency}$<br>$\land \text{Scope Active \& Budget Sufficient}$ | Instantly executed via MCP tool. | `refundable_amount` atomically reduced; audit event committed. |
| **APPROVAL_REQUIRED** | $\text{Amount} > \text{Auto-Allow Threshold}$ ($50.00)<br>$\land \text{Amount} \le \text{Hard Ceiling}$ ($1,000.00)<br>$\land \text{Amount} \le \text{Order Balance}$<br>$\land \text{Destination Valid}$<br>$\land \text{Scope Active \& Budget Sufficient}$ | Action suspended and quarantined. Action registered in SQLite with SHA-256 fingerprint. | `$0` deducted until human operator reviews and explicitly approves. |
| **BLOCKED** | Any of the following:<br>• $\text{Amount} > \text{Order Balance}$ (`EXCEEDS_ORDER_BALANCE`)<br>• $\text{Amount} > \text{Hard Ceiling}$ (`EXCEEDS_HARD_CEILING`)<br>• $\text{Destination} \ne \text{Original Destination}$ (`DESTINATION_MISMATCH`)<br>• $\text{Currency} \ne \text{Order Currency}$ (`CURRENCY_MISMATCH`)<br>• Remaining Scope Budget insufficient (`SCOPE_BUDGET_EXCEEDED`)<br>• Scope expired or inactive (`SCOPE_EXPIRED`)<br>• Malformed / negative amount (`INVALID_AMOUNT`) | Action halted immediately. | `$0` deducted. Immutable `BLOCKED` audit log event written. |

---

## 4. Concurrency, Race Condition, & Fail-Closed Guards

### 4.1 In-Flight UI Double-Click Lock
In `frontend/src/components/ApprovalDesk.tsx`, when an operator clicks **"Approve & Execute"** or **"Reject"**, a synchronous in-flight reference lock (`isSubmittingRef`) is acquired immediately before any async dispatch. Any rapid subsequent clicks within the same microtask or rendering cycle are silently dropped, preventing multi-click race conditions from dispatching duplicate approval requests.

### 4.2 Database Concurrency (`BEGIN IMMEDIATE`)
SQLite default transactions (`BEGIN DEFERRED`) allow multiple writers to acquire read locks simultaneously, upgrading to write locks only when an `UPDATE` executes. Under high concurrency, this produces `SQLITE_BUSY` or phantom overdraws. AetherGuard enforces `BEGIN IMMEDIATE` at transaction start, reserving an exclusive write lock upfront and serializing concurrent refunds against the same order or scope budget.

### 4.3 Fail-Closed Audit Trail (INV-10)
In `backend/app/governance/mcp_server.py`, the order deduction and audit event creation occur inside the same atomic database transaction. If the audit logging write raises an exception (e.g. disk full, schema failure, or constraint violation), the transaction is immediately rolled back:
```python
try:
    cursor.execute("UPDATE orders SET refundable_amount = refundable_amount - ?", (amount,))
    cursor.execute("INSERT INTO audit_events (...) VALUES (...)")
    conn.commit()
except Exception as exc:
    conn.rollback()
    raise AuditWriteFailureError("Transaction rolled back to prevent untracked balance change") from exc
```
This guarantees that **no financial balance change can ever exist without a corresponding immutable audit trail record**.
