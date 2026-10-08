"""API errors and the JSON error format shared by every endpoint.

Raise one of the `ApiError` subclasses from services; the handlers registered here turn
them into:

    {"timestamp", "status", "error", "message", "path", "correlationId", "details"}
"""

import logging
from datetime import datetime, timezone
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.request_context import get_correlation_id

logger = logging.getLogger(__name__)

INTERNAL_ERROR_MESSAGE = "Something went wrong. Please try again."


class ApiError(Exception):
    status_code = HTTPStatus.BAD_REQUEST

    def __init__(self, message: str, details: list[str] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or []


class BadRequestError(ApiError):
    status_code = HTTPStatus.BAD_REQUEST


class UnauthorizedError(ApiError):
    status_code = HTTPStatus.UNAUTHORIZED


class ForbiddenError(ApiError):
    status_code = HTTPStatus.FORBIDDEN


class NotFoundError(ApiError):
    status_code = HTTPStatus.NOT_FOUND


class ConflictError(ApiError):
    status_code = HTTPStatus.CONFLICT


def error_body(status_code: int, message: str, path: str, details: list[str] | None = None) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "timestamp": now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z",
        "status": status_code,
        "error": HTTPStatus(status_code).phrase,
        "message": message,
        "path": path,
        "correlationId": get_correlation_id(),
        "details": details or [],
    }


def error_response(request: Request, status_code: int, message: str, details: list[str] | None = None) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=error_body(status_code, message, request.url.path, details))


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        logger.info("%s %s -> %d %s: %s", request.method, request.url.path, exc.status_code, type(exc).__name__, exc.message)
        return error_response(request, exc.status_code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [_describe_validation_error(error) for error in exc.errors()]
        logger.info("%s %s -> 400 validation failed: %s", request.method, request.url.path, details)
        return error_response(request, HTTPStatus.BAD_REQUEST, "Validation failed", details)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        # Framework errors such as unknown routes (404) or wrong methods (405).
        response = error_response(request, exc.status_code, str(exc.detail))
        if exc.headers:
            response.headers.update(exc.headers)
        return response

    @app.exception_handler(IntegrityError)
    async def handle_integrity_error(request: Request, exc: IntegrityError) -> JSONResponse:
        # Usually a race on a unique value (e.g. two users registered with the same email at once).
        logger.warning("%s %s -> 409 integrity error: %s", request.method, request.url.path, exc.orig)
        return error_response(request, HTTPStatus.CONFLICT, "This change conflicts with existing data. Please refresh and try again.")


def _describe_validation_error(error: dict) -> str:
    if error.get("type") == "json_invalid":
        return "body: the request body is not valid JSON"
    location = [str(part) for part in error.get("loc", ()) if part not in ("body", "query", "path", "header", "form", "cookie")]
    field = ".".join(location) or "request"
    return f"{field}: {error.get('msg', 'is invalid')}"
