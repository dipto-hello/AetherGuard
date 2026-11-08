# AetherGuard

AetherGuard is an **experimental, synthetic-data prototype** for governing support-agent refund proposals. An operator grants a task scope; deterministic checks decide whether a proposed action is allowed, blocked or needs review; a SQLite sandbox and dashboard show the result. It is intended for the International AI Builders Congress AgentOps challenge.

**Status:** implementation and independent verification are ongoing. Read [review status](docs/REVIEW_STATUS.md) before using the app or making submission claims. This is not a production security boundary, a real payment service, or evidence of universal prompt-injection protection. The single shared operator token is for a local demo, not multi-user authorization. Audit records are ordinary SQLite records, not tamper-proof.

## Local setup

From this directory, with Python 3.12+, Node and npm installed. These Windows commands have not yet been verified on a clean machine:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
cd ..\frontend
npm ci --ignore-scripts
npm run build
cd ..\backend
```

Set a strong private demo token in the server process, and use the same value in the UI. Optional `GEMINI_API_KEY` must be configured on the server only. Never commit either value or enter real customer or payment information.

```powershell
$env:AETHERGUARD_OPERATOR_TOKEN = Read-Host 'Demo operator token'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Use a trusted local machine and a synthetic dataset; public deployment needs separate authentication, access, transport and security verification. A sandbox reset removes synthetic refund history.

## Container staging

The Dockerfile packages the frontend and backend together and uses `/data/sandbox.db` for persistent SQLite state. The container changes have **not been built or run here** because Docker was unavailable. The following is a local staging recipe, not a public deployment:

```sh
docker build -t aetherguard .
docker volume create aetherguard-data
docker run --name aetherguard --env-file /secure/path/aetherguard.env \
  --mount source=aetherguard-data,target=/data -p 127.0.0.1:8000:8000 aetherguard
```

Create the private env file outside the build context, containing a newly generated `AETHERGUARD_OPERATOR_TOKEN` and optionally `GEMINI_API_KEY`. Never use the previously disclosed local demo token or the exposed Gemini key for deployment. Do not commit or share this file. The runtime uses UID 10001; verify the chosen volume is writable by that UID and that the host backs it up. A replacement container must reuse the same volume. The first startup after the scope-budget migration expires existing task scopes and pending approvals while retaining refund history; back up the database before upgrading.

For an internet-accessible demonstration, place the application behind an HTTPS reverse proxy and an independently verified identity-aware access control with rate limiting. Keep the application port private, use one application instance with a durable volume, restrict access to intended operators, and verify backup/restore, secrets, logs, abuse limits, fail-closed behavior and all critical flows in the actual hosting environment. The shared operator token alone is not multi-user authentication. No hosting platform, identity provider, TLS configuration, public URL or deployment has been configured or verified in this project.

## Verification

Run tests only in a disposable environment: some tests manipulate SQLite state. From `backend` with dependencies installed:

```powershell
python -m pytest -q
```

The evaluation runs predefined synthetic cases; results describe only those cases. The current live-model, MCP, concurrency, browser, security and deployment evidence and limitations are recorded in [review status](docs/REVIEW_STATUS.md). Do not reuse historical fixed scores, certified-interoperability claims, or test counts without reproducing them on the version being presented.

The `refund_order` MCP tool and the HTTP `process-ticket` and `evaluate` endpoints require a caller-generated, nonblank idempotency key (maximum 128 characters). Generate a unique key per action and retain it when the outcome is unknown; inspect the recorded action rather than blindly issuing a new key. The synthetic parser uses limited English/Bengali heuristics and cannot establish intent in arbitrary text. A task scope authorizes only bounded synthetic actions; it does not prove the ticket's intent.

## Project documents

- [Product requirements](docs/01_PRD.md), [technical requirements](docs/04_TRD.md), and [data contracts](docs/05_Schema.md) describe intended behavior.
- [Verification plan](docs/VERIFICATION.md) lists acceptance checks.
- [Submission draft](docs/07_Submission_Package.md) separates demonstrated capabilities from impact and market hypotheses.

An older README is preserved in `../archive_outdated/AetherGuard_README_pre_review_2026-11-08.md` as historical context; it contains unsupported claims and must not be used as submission evidence.
