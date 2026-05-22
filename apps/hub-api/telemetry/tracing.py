"""
Manual tracing helpers.

trace_span() is a sync context manager that:
  - creates an OTel child span under the current trace context
  - automatically enriches every span with request-scoped IDs
  - records exceptions and sets ERROR status on failure (then re-raises)
  - is a no-op when opentelemetry-sdk is not installed

All helpers degrade gracefully: if the SDK is absent, spans are skipped
but business logic continues unaffected.
"""
import logging
from contextlib import contextmanager
from typing import Any

logger = logging.getLogger("telemetry.tracing")


def _get_tracer():
    try:
        from opentelemetry import trace
        return trace.get_tracer("hub-api")
    except ImportError:
        return None


@contextmanager
def trace_span(name: str, **attrs: Any):
    """
    Sync context manager that wraps a block in an OTel span.

    Usage:
        with trace_span("workflow.transition", proposal_id=pid, from_stage=s):
            ...

    The span inherits the current trace context (set by FastAPI
    auto-instrumentation for HTTP requests, or starts a new root span
    for background workers).
    """
    from telemetry.context import (
        get_correlation_id, get_request_id, get_actor_id,
        get_proposal_id, get_workflow_id,
    )

    tracer = _get_tracer()
    if tracer is None:
        yield None
        return

    try:
        from opentelemetry.trace import Status, StatusCode
    except ImportError:
        yield None
        return

    with tracer.start_as_current_span(name) as span:
        # Always enrich with request context
        span.set_attribute("correlation_id", get_correlation_id())
        span.set_attribute("request_id", get_request_id())
        span.set_attribute("actor_id", get_actor_id())
        span.set_attribute("proposal_id", get_proposal_id())
        span.set_attribute("workflow_id", get_workflow_id())
        # Caller attrs
        for k, v in attrs.items():
            span.set_attribute(k, str(v) if v is not None else "")
        try:
            yield span
        except Exception as exc:
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            span.record_exception(exc)
            raise


def record_workflow_transition(span, from_stage: str, to_stage: str, proposal_id: str) -> None:
    """Attach workflow-specific attributes to an existing span."""
    if span is None:
        return
    try:
        span.set_attribute("workflow.from_stage", from_stage)
        span.set_attribute("workflow.to_stage", to_stage)
        span.set_attribute("workflow.proposal_id", proposal_id)
        span.set_attribute("event.type", "workflow_transition")
    except Exception:
        pass


def record_error(exc: Exception, context: dict[str, Any] | None = None) -> None:
    """Structured error log with classification — call from exception handlers."""
    from telemetry.context import get_correlation_id, get_proposal_id
    logger.error(
        "Unhandled error: %s",
        exc,
        exc_info=exc,
        extra={
            "error_type": type(exc).__name__,
            "correlation_id": get_correlation_id(),
            "proposal_id": get_proposal_id(),
            **(context or {}),
        },
    )
