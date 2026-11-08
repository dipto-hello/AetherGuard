"""Single-operator authentication for the synthetic demo API."""
import hmac
import os


class OperatorAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        protected = scope["type"] == "http" and (path == "/api" or path.startswith("/api/")) and path != "/api/health"
        if protected:
            token = os.environ.get("AETHERGUARD_OPERATOR_TOKEN")
            headers = [value for name, value in scope.get("headers", []) if name.lower() == b"authorization"]
            if not token:
                status, body = 503, b'{"detail":"Operator token is not configured"}'
            elif len(headers) != 1 or not hmac.compare_digest(headers[0], b"Bearer " + token.encode("utf-8")):
                status, body = 401, b'{"detail":"Invalid operator credentials"}'
            else:
                return await self.app(scope, receive, send)
            await send({"type": "http.response.start", "status": status, "headers": [(b"content-type", b"application/json")]})
            await send({"type": "http.response.body", "body": body})
            return
        return await self.app(scope, receive, send)
