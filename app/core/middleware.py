"""Request middleware: correlation id, access logging and the last-resort 500 handler."""

import logging
import re
import time
import uuid

from starlette.datastructures import MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.errors import INTERNAL_ERROR_MESSAGE, error_body
from app.core.request_context import CORRELATION_ID_HEADER, reset_correlation_id, set_correlation_id

logger = logging.getLogger("app.request")

_HEADER_KEY = CORRELATION_ID_HEADER.lower().encode("latin-1")
_VALID_CORRELATION_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


class RequestContextMiddleware:
    """For every HTTP request:

    * uses the client's `X-Correlation-Id` (or generates a UUID) and echoes it on the response,
    * logs method, path, status and duration,
    * turns unhandled exceptions into the standard JSON 500 body, while the correlation id is still known.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        correlation_id = _read_correlation_id(scope)
        token = set_correlation_id(correlation_id)
        started_at = time.perf_counter()
        status_code = 500
        response_started = False

        async def send_with_correlation_id(message: Message) -> None:
            nonlocal status_code, response_started
            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
                MutableHeaders(scope=message).append(CORRELATION_ID_HEADER, correlation_id)
            await send(message)

        try:
            await self.app(scope, receive, send_with_correlation_id)
        except Exception:
            logger.exception("Unhandled error while processing %s %s", scope["method"], scope["path"])
            if response_started:
                raise
            response = JSONResponse(status_code=500, content=error_body(500, INTERNAL_ERROR_MESSAGE, scope["path"]))
            await response(scope, receive, send_with_correlation_id)
        finally:
            duration_ms = (time.perf_counter() - started_at) * 1000
            logger.info("%s %s -> %d (%.0f ms)", scope["method"], scope["path"], status_code, duration_ms)
            reset_correlation_id(token)


def _read_correlation_id(scope: Scope) -> str:
    for key, value in scope.get("headers", []):
        if key == _HEADER_KEY:
            candidate = value.decode("latin-1").strip()
            if _VALID_CORRELATION_ID.match(candidate):
                return candidate
            break
    return str(uuid.uuid4())
