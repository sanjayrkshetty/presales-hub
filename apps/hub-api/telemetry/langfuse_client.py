"""
Optional Langfuse integration for LLM call observability.

Activated only when LANGFUSE_PUBLIC_KEY + LANGFUSE_SECRET_KEY are set.
All helpers degrade gracefully when langfuse is not installed or
credentials are missing — callers get a no-op context.
"""
import logging
import os
from contextlib import contextmanager
from typing import Any

logger = logging.getLogger("telemetry.langfuse")

_client = None
_client_attempted = False


def get_langfuse():
    global _client, _client_attempted
    if _client_attempted:
        return _client
    _client_attempted = True
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    if not public_key or not secret_key:
        return None
    try:
        from langfuse import Langfuse  # type: ignore[import]
        host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
        _client = Langfuse(public_key=public_key, secret_key=secret_key, host=host)
        logger.info("Langfuse client initialised (host=%s)", host)
    except ImportError:
        logger.warning("langfuse package not installed — AI telemetry disabled")
    return _client


@contextmanager
def langfuse_trace(name: str, metadata: dict[str, Any] | None = None):
    """
    Context manager wrapping an LLM generation with a Langfuse trace.

    Yields the Langfuse trace object (or None if unavailable).
    Callers should log generations inside:

        with langfuse_trace("proposal_generation", metadata={...}) as lf:
            if lf:
                generation = lf.generation(name="claude", model="claude-opus-4-7")
            result = call_llm(...)
            if lf:
                generation.end(output=result)
    """
    from telemetry.context import get_correlation_id, get_proposal_id
    client = get_langfuse()
    if client is None:
        yield None
        return

    trace = client.trace(
        name=name,
        metadata={
            "correlation_id": get_correlation_id(),
            "proposal_id": get_proposal_id(),
            **(metadata or {}),
        },
    )
    try:
        yield trace
    except Exception as exc:
        try:
            trace.update(status_message=f"error: {exc}")
        except Exception:
            pass
        raise
    finally:
        try:
            client.flush()
        except Exception:
            pass
