"""Exponential backoff with jitter."""
from __future__ import annotations

import random
from integration_fabric.config import RETRY_BASE_DELAY_S, RETRY_MAX_DELAY_S, RETRY_BACKOFF_FACTOR


def exponential_delay(attempt: int, base: float = RETRY_BASE_DELAY_S,
                      factor: float = RETRY_BACKOFF_FACTOR,
                      max_delay: float = RETRY_MAX_DELAY_S,
                      jitter: bool = True) -> float:
    """Return delay in seconds for the given attempt (0-indexed)."""
    delay = min(base * (factor ** attempt), max_delay)
    if jitter:
        delay *= (0.5 + random.random() * 0.5)
    return round(delay, 3)


def should_retry(attempt: int, max_attempts: int, error: Exception | None = None) -> bool:
    if attempt >= max_attempts:
        return False
    non_retryable = (ValueError, TypeError, PermissionError)
    if error and isinstance(error, non_retryable):
        return False
    return True
