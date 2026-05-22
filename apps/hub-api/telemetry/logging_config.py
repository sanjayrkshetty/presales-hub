import logging
import os

from telemetry.context import (
    get_correlation_id, get_request_id, get_actor_id, get_proposal_id,
)

SERVICE_NAME = os.getenv("SERVICE_NAME", "hub-api")


class ContextFilter(logging.Filter):
    """Injects request-scoped context vars into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = get_correlation_id()
        record.request_id = get_request_id()
        record.actor_id = get_actor_id()
        record.proposal_id = get_proposal_id()
        record.service = SERVICE_NAME
        return True


def setup_logging(level: str = "INFO") -> None:
    """
    Configure structured JSON logging for the entire process.

    Uses python-json-logger when available; falls back to a plain
    formatter that still injects the context fields.
    """
    context_filter = ContextFilter()

    try:
        from pythonjsonlogger import jsonlogger  # type: ignore[import]
        formatter: logging.Formatter = jsonlogger.JsonFormatter(
            fmt="%(asctime)s %(name)s %(levelname)s %(message)s "
                "%(correlation_id)s %(request_id)s %(actor_id)s "
                "%(proposal_id)s %(service)s",
            datefmt="%Y-%m-%dT%H:%M:%SZ",
            rename_fields={"asctime": "timestamp", "levelname": "level"},
        )
    except ImportError:
        # Graceful fallback: structured fields still injected; just not JSON
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s | cid=%(correlation_id)s "
                "pid=%(proposal_id)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%SZ",
        )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.addFilter(context_filter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
