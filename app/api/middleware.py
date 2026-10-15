"""Log each HTTP request without recording payloads or query parameters."""

import logging
from time import perf_counter
from uuid import uuid4

from app.core.logging import request_id

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        correlation_id = uuid4().hex
        token = request_id.set(correlation_id)
        started = perf_counter()
        status = 500

        async def send_with_id(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message = dict(message)
                message["headers"] = [
                    (key, value) for key, value in message.get("headers", [])
                    if key.lower() != b"x-request-id"
                ] + [(b"x-request-id", correlation_id.encode("ascii"))]
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        except Exception as exc:
            # Exception strings may contain provider URLs, tokens or payloads.
            logger.error("Unhandled request error | error_type=%s", type(exc).__name__)
            raise
        finally:
            level = logging.ERROR if status >= 500 else logging.WARNING if status >= 400 else logging.INFO
            route = scope.get("route")
            logger.log(
                level,
                "HTTP request completed | method=%s route=%s status=%s duration_ms=%.1f",
                scope["method"], getattr(route, "path", "<unmatched>"), status,
                (perf_counter() - started) * 1000,
            )
            request_id.reset(token)
