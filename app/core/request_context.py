"""Per-request context shared with logging, error responses and audit logs."""

from contextvars import ContextVar

CORRELATION_ID_HEADER = "X-Correlation-Id"

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def get_correlation_id() -> str | None:
    return _correlation_id.get()


def set_correlation_id(value: str | None):
    """Set the id for the current request. Returns a token for `reset_correlation_id`."""
    return _correlation_id.set(value)


def reset_correlation_id(token) -> None:
    _correlation_id.reset(token)
