# AetherGuard — Free-Only Cloud Hosting & Deployment Evaluation

## 1. Executive Summary & Strict Constraints

This evaluation prepares AetherGuard for a future deployment session under strict **free-only, zero-subscription, zero-credit-card** requirements:
- **Zero Mandatory Fees**: Absolutely no paid subscriptions, upfront charges, or trial expiration traps.
- **No Credit Card Required**: Must be provisionable by a student without a credit or debit card on file.
- **Security & HTTPS**: Built-in TLS encryption and secure environment variable storage for secrets (`AETHERGUARD_OPERATOR_TOKEN`, `GEMINI_API_KEY`).
- **Single Unified Runtime**: Single-port HTTP delivery serving both FastAPI backend and React 19 SPA frontend from one process/container.
- **Storage Reality Check**: An honest technical appraisal of SQLite persistence under free-tier filesystem constraints.

---

## 2. Comparative Analysis of Free Hosting Providers

| Platform | Free Tier Eligibility | Credit Card Required? | HTTPS Included? | Sleep / Cold Start Behavior | Filesystem & SQLite Persistence | Verdict for AetherGuard |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Hugging Face Spaces (Docker SDK)** | Generous free CPU Basic (2 vCPU, 16GB RAM) | **NO** (Zero credit card) | **YES** (`*.hf.space`) | Sleeps after 48h idle; instant restart on HTTP visit | **Ephemeral by default**; resets on restart. Space secrets supported. | **TOP RECOMMENDED (Cloud Demo)**: Best free specs, zero credit card, instant Docker support. |
| **Cloudflare Tunnel (`cloudflared`)** | 100% Free Quick Tunnel or Zero Trust Account | **NO** (Zero credit card) | **YES** (`*.trycloudflare.com` or custom domain) | **Zero sleep** (runs on host machine) | **100% Durable**: Uses host machine's actual SQLite database directly on disk. | **TOP RECOMMENDED (Live Local-to-Web)**: Zero cloud setup, persistent data, zero cold start. |
| **Render.com (Free Web Service)** | 750 free instance hours / month | **NO** (Zero credit card) | **YES** (`*.onrender.com`) | Spins down after 15 min idle; ~50s cold start delay | **Ephemeral ONLY**: Free tier lacks persistent disks (Render Disks are paid). DB resets on spin-down. | **VIABLE WITH CAVEATS**: Good for temporary demo sessions; resets state on sleep. |
| **Koyeb (Free Tier)** | 1 free Nano instance (512MB RAM, 0.1 vCPU) | **NO** (In standard regions) | **YES** (`*.koyeb.app`) | Minimal cold start; keeps running | **Ephemeral ONLY**: No persistent volume on free tier. | **VIABLE ALTERNATIVE**: Low memory ceiling (512MB), requires careful Docker optimization. |
| **Fly.io** | Historically free compute allowance | **YES** (Credit card required for fraud verification) | **YES** | Suspends idle machines | Supports 3GB free persistent volume (when card verified). | **DISQUALIFIED**: Requires credit card on file. |
| **Oracle Cloud (OCI) Always Free** | 2 AMD VMs + 4 ARM cores (24GB RAM, 200GB disk) | **YES** (Strict credit card verification) | Requires manual Certbot | Never sleeps | 100% durable local block volume. | **DISQUALIFIED**: Requires credit card on file for account setup. |

---

## 3. The Free-Tier SQLite Persistence Dilemma & Architectural Reality

> [!WARNING]
> **Ephemeral Filesystem Disclosure**  
> Cloud platforms offering 100% free hosting without credit cards (Hugging Face Spaces, Render Free, Koyeb) use **ephemeral container filesystems**. Whenever the container restarts, updates, or recovers from sleep, the filesystem reverts to its built-in image state. Any orders updated or audit records written to `/data/sandbox.db` will be discarded, returning to the seeded baseline (`ORD-101` to `ORD-104`).

### Why this is acceptable for the Hackathon Demonstration:
1. **Self-Healing Baseline**: AetherGuard automatically initializes and seeds synthetic orders on a fresh database startup (`init_db()` in `db.py`), ensuring the demo is immediately functional without manual setup.
2. **Deterministic Reset**: For evaluation and hackathon judging, returning to a known baseline between sessions prevents state corruption from prior test runs.

### The Smallest Reasonable Future Alternatives for Long-Term Free Persistence:
If persistent state across restarts is strictly required in the future without paying for cloud storage:
1. **Cloudflare Tunnel (`cloudflared`)**: Run AetherGuard locally with its durable SQLite database on disk while exposing a secure, public HTTPS URL for judges.
2. **Free Serverless SQLite (Turso / LibSQL)**: Turso offers a completely free tier (9GB storage, 500 databases, no credit card required). In a future session, migrating the backend database driver from Python standard library `sqlite3` to `libsql-experimental` would allow durable cloud-hosted SQLite storage with zero container disk dependencies. *(Note: Intentionally deferred to avoid architectural changes in this freeze).*

---

## 4. Recommended Step-by-Step Future Deployment Recipes

### Option A: Hugging Face Spaces (100% Free Cloud Docker Container)
*Ideal for a hosted 24/7 web demonstration with zero credit card.*

1. **Prerequisites**: A free Hugging Face account at `https://huggingface.co`.
2. **Create Space**:
   - Go to `https://huggingface.co/new-space`.
   - Name: `aetherguard-control-plane`.
   - License: Choose intended license (e.g. Apache 2.0 or MIT).
   - Space SDK: Select **Docker** (Blank template).
   - Space Hardware: **CPU Basic · 2 vCPU · 16GB RAM · Free**.
3. **Configure Space Secrets**:
   - Navigate to **Settings** $\rightarrow$ **Variables and secrets**.
   - Add Secret: `AETHERGUARD_OPERATOR_TOKEN` = `<generate-secure-random-token>`.
   - Optional Secret: `GEMINI_API_KEY` = `<your-gemini-api-key>`.
4. **Deploy Repository**:
   - Connect the future GitHub repository or push directly to Hugging Face Git remote.
   - Hugging Face automatically detects `Dockerfile`, builds the React frontend, packages the FastAPI backend, and serves the container on port 7860/8000.
   - Note: In Dockerfile or Space settings, set `ENV PORT=7860` if using Hugging Face's default web port.

---

### Option B: Free Cloudflare Quick Tunnel (Local Durable Execution to Public Web)
*Ideal for live demonstration with 100% durable local SQLite persistence and zero cloud account requirements.*

1. **Prerequisites**: Download official free `cloudflared` binary from `https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/`.
2. **Start Local AetherGuard Server**:
   ```powershell
   cd backend
   $env:AETHERGUARD_OPERATOR_TOKEN = "your-secure-demo-token-min-32-chars"
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```
3. **Launch Free HTTPS Tunnel** (in a separate terminal):
   ```powershell
   cloudflared tunnel --url http://127.0.0.1:8000
   ```
4. **Access**:
   - Cloudflare prints an instant public HTTPS URL: `https://<random-slug>.trycloudflare.com`.
   - Open URL in browser, input your `AETHERGUARD_OPERATOR_TOKEN`, and demo full live bilingual governance.

---

### Option C: Render.com Free Web Service
*Alternative standard cloud container host.*

1. **Prerequisites**: Free account at `https://render.com` (sign in via GitHub).
2. **Create Web Service**:
   - Connect future GitHub repository.
   - Environment: **Docker**.
   - Region: Select nearest free region (e.g. Oregon, Frankfurt).
   - Instance Type: **Free**.
3. **Environment Variables**:
   - `AETHERGUARD_OPERATOR_TOKEN`: `<secure-random-token>`
   - `GEMINI_API_KEY`: `<optional-key>`
   - `PORT`: `8000`
4. **Limitations to Note**:
   - Will sleep after 15 minutes of inactivity; first request takes 45–60s to wake up.
   - Ephemeral database resets on spin-down.
