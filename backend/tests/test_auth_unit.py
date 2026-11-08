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
