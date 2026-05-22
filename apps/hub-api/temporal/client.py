"""
Lazy singleton Temporal client.

Degrades gracefully when the Temporal server is unreachable — callers
receive None and must handle it (return 503, skip orchestration, etc.).

The client is process-scoped and thread-safe; reuse it for all operations.
"""
import logging
import os
from typing import Optional

logger = logging.getLogger("temporal.client")

TEMPORAL_HOST = os.getenv("TEMPORAL_HOST", "localhost:7233")
_client = None


async def get_temporal_client():
    """Connect once, reuse forever. Returns None if Temporal is unreachable."""
    global _client
    if _client is not None:
        return _client
    try:
        from temporalio.client import Client
        _client = await Client.connect(TEMPORAL_HOST)
        logger.info("Temporal client connected → %s", TEMPORAL_HOST)
        return _client
    except ImportError:
        logger.warning("temporalio not installed — Temporal orchestration disabled")
        return None
    except Exception as exc:
        logger.warning(
            "Temporal unreachable at %s: %s — workflow orchestration disabled",
            TEMPORAL_HOST, exc,
        )
        return None
