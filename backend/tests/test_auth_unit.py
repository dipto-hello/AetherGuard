import asyncio
import importlib.util
import os
import unittest
from unittest.mock import patch


class AuthMiddlewareTests(unittest.TestCase):
    def test_api_requires_configured_matching_bearer(self):
        spec = importlib.util.find_spec("app.auth")
        self.assertIsNotNone(spec, "operator authentication middleware must exist")
        from app.auth import OperatorAuthMiddleware

        async def endpoint(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        async def request(path, authorization=None):
            messages = []
            async def send(message):
                messages.append(message)
            async def receive():
                return {"type": "http.request", "body": b"", "more_body": False}
            headers = [] if authorization is None else [(b"authorization", authorization.encode())]
            await OperatorAuthMiddleware(endpoint)(
                {"type": "http", "path": path, "headers": headers}, receive, send,
            )
            return messages[0]["status"]

        with patch.dict(os.environ, {"AETHERGUARD_OPERATOR_TOKEN": "dummy-test-token"}, clear=True):
            self.assertEqual(asyncio.run(request("/api/health")), 200)
            self.assertEqual(asyncio.run(request("/api/governance/policy")), 401)
            self.assertEqual(asyncio.run(request("/api/governance/policy", "Bearer wrong")), 401)
            self.assertEqual(asyncio.run(request("/api/governance/policy", "Bearer dummy-test-token")), 200)
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(asyncio.run(request("/api/governance/policy", "Bearer dummy-test-token")), 503)

    def test_user_token_limited_to_refund_testing_routes(self):
        from app.auth import OperatorAuthMiddleware

        async def endpoint(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        async def request(method, path, token):
            messages = []
            async def send(message):
                messages.append(message)
            async def receive():
                return {"type": "http.request", "body": b"", "more_body": False}
            scope = {"type": "http", "method": method, "path": path, "headers": [(b"authorization", f"Bearer {token}".encode())]}
            await OperatorAuthMiddleware(endpoint)(scope, receive, send)
            return messages[0]["status"], messages[-1]["body"]

        env = {"AETHERGUARD_OPERATOR_TOKEN": "admin-t", "AETHERGUARD_USER_TOKEN": "user-t"}
        with patch.dict(os.environ, env, clear=True):
            self.assertEqual(asyncio.run(request("GET", "/api/me", "user-t")), (200, b'{"role": "user"}'))
            self.assertEqual(asyncio.run(request("GET", "/api/me", "admin-t")), (200, b'{"role": "admin"}'))
            self.assertEqual(asyncio.run(request("POST", "/api/agent/process-ticket", "user-t"))[0], 200)
            self.assertEqual(asyncio.run(request("GET", "/api/governance/policy", "user-t"))[0], 200)
            for method, path in [("PUT", "/api/governance/policy"), ("GET", "/api/governance/pending-approvals"),
                                 ("POST", "/api/governance/approvals/x/decide"), ("POST", "/api/sandbox/reset"),
                                 ("GET", "/api/governance/audit-logs"), ("PATCH", "/api/sandbox/orders/o1"),
                                 ("GET", "/api/sandbox/orders/o1")]:
                self.assertEqual(asyncio.run(request(method, path, "user-t"))[0], 403, path)
                self.assertEqual(asyncio.run(request(method, path, "admin-t"))[0], 200, path)
        # Unset user token never matches an empty bearer.
        with patch.dict(os.environ, {"AETHERGUARD_OPERATOR_TOKEN": "admin-t"}, clear=True):
            self.assertEqual(asyncio.run(request("GET", "/api/me", ""))[0], 401)
