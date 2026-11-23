"""Admin and user authentication for the synthetic demo API."""
import hmac
import json
import os

# Exact (method, path) pairs the user role may call: the "Test a refund" flow only.
USER_ROUTES = {
    ("GET", "/api/me"),
    ("GET", "/api/sandbox/orders"),
    ("GET", "/api/governance/policy"),
    ("POST", "/api/governance/scopes"),
    ("POST", "/api/agent/process-ticket"),
    ("GET", "/api/governance/actions/lookup"),
}


def _matches(header: bytes, token: str | None) -> bool:
    return bool(token) and hmac.compare_digest(header, b"Bearer " + token.encode("utf-8"))


class OperatorAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        protected = scope["type"] == "http" and (path == "/api" or path.startswith("/api/")) and path != "/api/health"
        if not protected:
            return await self.app(scope, receive, send)

        admin_token = os.environ.get("AETHERGUARD_OPERATOR_TOKEN")
        user_token = os.environ.get("AETHERGUARD_USER_TOKEN")
        headers = [value for name, value in scope.get("headers", []) if name.lower() == b"authorization"]
        role = None
        if len(headers) == 1:
            # Admin checked first so a token configured for both roles stays admin.
            role = "admin" if _matches(headers[0], admin_token) else "user" if _matches(headers[0], user_token) else None

        if not admin_token:
            status, body = 503, b'{"detail":"Operator token is not configured"}'
        elif role is None:
            status, body = 401, b'{"detail":"Invalid operator credentials"}'
        elif path == "/api/me" and scope.get("method") == "GET":
            status, body = 200, json.dumps({"role": role}).encode()
        elif role == "user" and (scope.get("method"), path) not in USER_ROUTES:
            status, body = 403, b'{"detail":"Admin access required"}'
        else:
            return await self.app(scope, receive, send)
        await send({"type": "http.response.start", "status": status, "headers": [(b"content-type", b"application/json")]})
        await send({"type": "http.response.body", "body": body})
