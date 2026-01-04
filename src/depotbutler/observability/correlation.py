"""Correlation ID management for request tracing."""

import contextvars
from datetime import UTC, datetime

# Thread-local storage for correlation ID
_correlation_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id", default=None
)


def generate_correlation_id() -> str:
    """
    Generate a unique correlation ID for a workflow run.

    Format: run-YYYYMMDD-HHMMSS
    Example: run-20260104-183045
    """
    now = datetime.now(UTC)
    return f"run-{now.strftime('%Y%m%d-%H%M%S')}"


def set_correlation_id(correlation_id: str) -> None:
    """Set the correlation ID for the current context."""
    _correlation_id.set(correlation_id)


def get_correlation_id() -> str | None:
    """Get the correlation ID for the current context."""
    return _correlation_id.get()
