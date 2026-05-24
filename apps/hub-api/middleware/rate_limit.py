"""Rate limiting.

slowapi is kept for app state wiring (exception handler registration).
Per-route rate limiting uses LoginRateLimiter (FastAPI Depends) to avoid
a slowapi 0.1.9 / FastAPI 0.115.5 signature-introspection incompatibility
where @limiter.limit() wrappers cause FastAPI to misclassify body/db params
as missing query parameters (422).
"""
from collections import defaultdict
from datetime import datetime, timedelta

from fastapi import HTTPException, Request, status
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
rate_limit_exceeded_handler = _rate_limit_exceeded_handler


class LoginRateLimiter:
    """In-process sliding-window rate limiter, safe to use as FastAPI Depends."""

    def __init__(self, times: int = 20, seconds: int = 60) -> None:
        self.times = times
        self.seconds = seconds
        self._calls: dict[str, list[datetime]] = defaultdict(list)

    async def __call__(self, request: Request) -> None:
        key = (
            request.headers.get("x-forwarded-for", "").split(",")[0].strip()
            or (request.client.host if request.client else "unknown")
        )
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=self.seconds)
        self._calls[key] = [t for t in self._calls[key] if t > window_start]
        if len(self._calls[key]) >= self.times:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests — try again later.",
            )
        self._calls[key].append(now)


login_rate_limiter = LoginRateLimiter(times=20, seconds=60)

__all__ = [
    "limiter",
    "rate_limit_exceeded_handler",
    "RateLimitExceeded",
    "login_rate_limiter",
    "LoginRateLimiter",
]
