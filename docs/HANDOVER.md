# Developer handover

AetherGuard demonstrates policy enforcement and human review for agent-proposed actions in a synthetic refund sandbox. Start with [Local setup](SETUP.md), then follow [Architecture](ARCHITECTURE.md) alongside the code.

| Start here | Responsibility |
| --- | --- |
| `frontend/src/App.tsx`, `api.ts` | Console, in-memory bearer token, HTTP requests |
| `frontend/src/components/` | Ticket workflow, approvals, policy, audit, evaluation, and order balance UI |
| `backend/app/main.py`, `auth.py` | HTTP routing, size limits, ticket rate limit, and operator authentication |
| `backend/app/agent/core.py`, `tickets.py` | Gemini proposal chain and sample tickets |
| `backend/app/governance/mcp_server.py`, `boundary.py` | MCP tools, caller scope checks, verdicts, and governed execution |
| `backend/app/approval/service.py`, `policy/engine.py` | Exact-action review and deterministic policy |
| `backend/app/sandbox/db.py`, `service.py`, `exchange_rate.py` | SQLite schema, synthetic orders and refunds, compatibility migrations, and USD/BDT quotes |

## First working session

1. Accept repository access, clone the private repository, and create a branch from `main`.
2. Follow the setup guide with your own local operator token and development database. Obtain a Gemini key separately if you need live ticket proposals.
3. Open the console, review the seeded orders, and run the evaluation matrix. For a live ticket, create its authorized scope, submit the ticket, inspect the pending action, approve or reject it, and compare the audit entry and refund ledger.
4. Run backend and frontend checks before opening a pull request. Use the existing tests to locate the appropriate regression coverage.

## Maintenance

- Preserve native currency amounts. When modifying policy, check the BDT conversion and cumulative scope budget at both proposal and approval.
- Reuse a stable idempotency key for retries. After an uncertain response, inspect the existing action via `GET /api/governance/actions/lookup` before making another request.
- Keep SQLite state outside Git. Back up using SQLite-aware tooling before migrations. Legacy authority may expire during initialization while recorded refunds are preserved.
- Keep API, MCP wrapper, and approval checks aligned while accounting for their different entry points. The ticket path requires review even when direct policy permits an immediate refund.

## Current limits and next work

The console, deterministic evaluation, scope enforcement, and approval workflows have automated local coverage. Live Gemini behavior depends on account quota, model availability, and proposal quality. No production payment provider, per-user identity system, or tamper-resistant audit service is configured. A stale exchange rate can affect the BDT policy threshold. The deployment design still needs persistent storage and recovery, independently authenticated operators and reviewers, proxy configuration, and an isolated execution identity. See [Security](../SECURITY.md).

## Verification for this handover

A fresh Windows install with Python 3.12 and Node.js 24 completed the frontend tests (14), lint, and production build, then the backend suite (294) and standalone approval tests (6). The backend suite includes SQLite migration and MCP stdio coverage. A loopback smoke test used a disposable database and checked UI serving, health, authentication, and four seeded orders. Live Gemini calls and the container runtime were outside this verification.
