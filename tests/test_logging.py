import logging
import unittest

from app.api.middleware import RequestLoggingMiddleware
from app.core.logging import RequestFormatter, request_id


class LoggingTests(unittest.IsolatedAsyncioTestCase):
    async def test_request_correlation_and_status(self):
        seen = []
        sent = []

        async def endpoint(scope, receive, send):
            seen.append(request_id.get())
            await send({"type": "http.response.start", "status": 422, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        async def send(message):
            sent.append(message)

        with self.assertLogs("app.api.middleware", level="INFO") as logs:
            await RequestLoggingMiddleware(endpoint)(
                {"type": "http", "method": "POST", "path": "/private"}, None, send
            )
        self.assertEqual(dict(sent[0]["headers"])[b"x-request-id"].decode(), seen[0])
        self.assertEqual(request_id.get(), "-")
        self.assertIn("status=422", logs.output[0])
        self.assertNotIn("/private", logs.output[0])

    async def test_exception_resets_context_and_logs_failure(self):
        async def endpoint(scope, receive, send):
            raise RuntimeError("secret")

        with self.assertLogs("app.api.middleware", level="ERROR") as logs:
            with self.assertRaises(RuntimeError):
                await RequestLoggingMiddleware(endpoint)(
                    {"type": "http", "method": "GET"}, None, None
                )
        self.assertEqual(request_id.get(), "-")
        self.assertIn("status=500", logs.output[-1])
        self.assertNotIn("secret", " ".join(logs.output))

    async def test_formatter_uses_utc_and_request_context(self):
        formatter = RequestFormatter(
            "%(asctime)sZ | %(levelname)s | %(request_id)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
        record = logging.LogRecord("app", logging.INFO, "", 0, "hello", (), None)
        record.created = 0
        token = request_id.set("test-id")
        try:
            self.assertEqual(formatter.format(record), "1970-01-01T00:00:00Z | INFO | test-id | hello")
        finally:
            request_id.reset(token)
