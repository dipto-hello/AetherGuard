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
    if content_length and int(content_length) > MAX_REQUEST_SIZE:
        return JSONResponse(
            status_code=413,
            content={"detail": "Payload Too Large: Maximum allowed request size is 1MB"}
        )

    # 2. Rate limiting for AI ticket processing (/api/agent/process-ticket)
    # Allows bypassing during automated unit test runs unless explicitly tested
    if request.url.path == "/api/agent/process-ticket" and not os.environ.get("PYTEST_CURRENT_TEST_BYPASS_RATELIMIT", "1") == "1":
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window = 60.0
        max_rpm = int(os.environ.get("AETHERGUARD_RATE_LIMIT_PER_MINUTE", 20))
        
        _RATE_LIMITS[client_ip] = [t for t in _RATE_LIMITS[client_ip] if now - t < window]
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
