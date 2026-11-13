# Local setup

Install Python 3.12, Node.js 24 with npm, and Git. Run the following from the repository root in PowerShell.

```powershell
Set-Location backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Set `AETHERGUARD_OPERATOR_TOKEN` in `backend/.env` to a strong, unique local value. Add a Gemini API key only if you want live ticket processing. The instructions below explicitly load the environment file through Uvicorn.

```powershell
.\.venv\Scripts\python.exe -c "from dotenv import load_dotenv; from app.sandbox.db import init_db; load_dotenv('.env'); init_db().close()"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --env-file .env --host 127.0.0.1 --port 8000
```

In a separate terminal, start the console from the repository root.

```powershell
Set-Location frontend
npm ci
npm run dev
```

Open `http://localhost:5173` and enter the operator token. Vite proxies `/api` to `127.0.0.1:8000`. FastAPI exposes `/api/health` and Swagger UI at `/docs`. Use a separate development database for experiments. The sandbox reset changes synthetic state.

## Configuration

| Setting | Behavior |
| --- | --- |
| `AETHERGUARD_OPERATOR_TOKEN` | Required for protected HTTP routes. Requests fail closed if unset. |
| `GEMINI_API_KEY` | Enables live ticket proposals. Missing credentials or failed proposals produce no refund. |
| `AETHERGUARD_DB_PATH` | Optional SQLite path. Defaults to `backend/data/sandbox.db`. An absolute path outside the clone is suitable for persistent local state. |
| `AETHERGUARD_RATE_LIMIT_PER_MINUTE` | Ticket-processing request limit. Default 20 per process per client key. |
| `AETHERGUARD_TRUSTED_PROXIES` | Comma-separated addresses whose forwarded IP header may be used. Set for the actual proxy topology. |
| `FRONTEND_DIST_PATH` | Optional static frontend directory override. |
| `AETHERGUARD_AUTHENTICATED_OPERATOR` | Trusted principal injected by the launcher of a stdio MCP session. It must match the persisted scope owner. |

Use Uvicorn flags to choose the bind address and port. With `npm run build` completed, FastAPI can serve `frontend/dist` at startup. The checked-in Dockerfile builds the frontend and runs FastAPI as a non-root user. Initialize the database and configure persistent storage before using a container beyond a disposable smoke test. The container path is `/data/sandbox.db`.

To start a local stdio MCP session, configure a trusted launcher to invoke `python -m app.mcp_entrypoint` from `backend/` with the Python environment, absolute database path, and trusted principal in its process environment. This path initializes the database itself. See [Architecture](ARCHITECTURE.md).

## Verification

From `frontend/`, run `npm test`, `npm run lint`, and `npm run build`. Build before the backend suite because it checks static serving from `frontend/dist`. From `backend/`, run `python -m pytest -q` and `python -m tests.approval_check` with the virtual environment interpreter. The automated tests exercise local or mocked behavior without a live Gemini key.
