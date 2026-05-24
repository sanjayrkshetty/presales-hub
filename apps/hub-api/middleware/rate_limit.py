"""Rate limiting via slowapi. Import limiter and apply @limiter.limit() on routes."""
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
rate_limit_exceeded_handler = _rate_limit_exceeded_handler

__all__ = ["limiter", "rate_limit_exceeded_handler", "RateLimitExceeded"]
