"""AetherGuard Backend Application Entrypoint"""
import os
import time
from collections import defaultdict
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from app.auth import OperatorAuthMiddleware
from app.api.sandbox import router as sandbox_router
from app.api.governance import router as governance_router
from app.api.agent import router as agent_router
from app.api.evaluation import router as evaluation_router

app = FastAPI(
    title="AetherGuard AgentOps Control Plane",
    version="0.1.0",
    description="Zero-Trust MCP Governance Boundary & Execution Firewall"
)

app.add_middleware(OperatorAuthMiddleware)

_RATE_LIMITS = defaultdict(list)
MAX_REQUEST_SIZE = 1_048_576  # 1 MB maximum payload limit

@app.middleware('http')
async def rate_limit_and_size_guard(request: Request, call_next):
    # 1. Payload size check
    content_length = request.headers.get("content-length")
    transfer_encoding = request.headers.get("transfer-encoding", "").lower()

    if content_length is not None:
        try:
            cl = int(content_length)
            if cl < 0 or cl > MAX_REQUEST_SIZE:
                return JSONResponse(
                    status_code=413,
                    content={"detail": "Payload Too Large: Maximum allowed request size is 1MB"}
                )
        except (ValueError, TypeError):
            return JSONResponse(
                status_code=400,
                content={"detail": "Bad Request: Malformed Content-Length header"}
            )

    if "chunked" in transfer_encoding or request.method in ("POST", "PUT", "PATCH"):
        total_size = 0
        chunks = []
        async for chunk in request.stream():
            total_size += len(chunk)
            if total_size > MAX_REQUEST_SIZE:
                return JSONResponse(
                    status_code=413,
                    content={"detail": "Payload Too Large: Maximum allowed request size is 1MB"}
                )
            chunks.append(chunk)
        request._body = b"".join(chunks)

    # 2. Rate limiting for AI ticket processing (/api/agent/process-ticket)
    # Active by default in production; allows bypassing during test runs when explicitly set to "1"
    if request.url.path == "/api/agent/process-ticket" and os.environ.get("PYTEST_CURRENT_TEST_BYPASS_RATELIMIT", "0") != "1":
        client_ip = request.client.host if request.client else "unknown"
        trusted_proxies = {p.strip() for p in os.environ.get("AETHERGUARD_TRUSTED_PROXIES", "127.0.0.1,::1").split(",") if p.strip()}
        if client_ip in trusted_proxies and "x-forwarded-for" in request.headers:
            forwarded = request.headers["x-forwarded-for"].split(",")[0].strip()
            if forwarded:
                client_ip = forwarded
        now = time.time()
        window = 60.0
        max_rpm = int(os.environ.get("AETHERGUARD_RATE_LIMIT_PER_MINUTE", 20))
        
        _RATE_LIMITS[client_ip] = [t for t in _RATE_LIMITS[client_ip] if now - t < window]
        if not _RATE_LIMITS[client_ip]:
            del _RATE_LIMITS[client_ip]
        if len(_RATE_LIMITS[client_ip]) >= max_rpm:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too Many Requests: Rate limit exceeded. Please wait before retrying."},
                headers={"Retry-After": "60"}
            )
        _RATE_LIMITS[client_ip].append(now)

    return await call_next(request)

@app.middleware('http')
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'no-referrer'
    if request.url.path in ('/docs', '/redoc', '/openapi.json'):
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data: https://fastapi.tiangolo.com; "
            "object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
        )
    else:
        response.headers['Content-Security-Policy'] = "default-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    if request.url.path == '/api' or request.url.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store'
    return response

app.include_router(sandbox_router)
app.include_router(governance_router)
app.include_router(agent_router)
app.include_router(evaluation_router)

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "aetherguard-governance-engine",
        "version": "0.1.0"
    }

# Mount Frontend static files for unified single-port production delivery
default_frontend_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist"))
frontend_dist = os.environ.get("FRONTEND_DIST_PATH", default_frontend_dist)
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
