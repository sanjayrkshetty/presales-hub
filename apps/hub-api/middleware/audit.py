"""Structured audit log middleware.

Logs every non-health API request with method, path, status, duration, IP,
and correlation ID. Registered after CorrelationIdMiddleware so the correlation
ID is already available in the context.

Health/metrics endpoints are excluded to avoid log noise from polling.
"""
import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("hub-api.audit")

_SKIP_PATHS = frozenset({"/api/health", "/api/ready", "/metrics", "/api/ready"})


class AuditLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in _SKIP_PATHS:
            return await call_next(request)

        start = time.monotonic()
        response = await call_next(request)
        duration_ms = round((time.monotonic() - start) * 1000, 1)

        client_ip = (
            request.headers.get("x-forwarded-for", "").split(",")[0].strip()
            or (request.client.host if request.client else "unknown")
        )

        logger.info(
            "%s %s %s",
            request.method,
            request.url.path,
            response.status_code,
            extra={
                "method": request.method,
                "path": request.url.path,
                "query": str(request.url.query)[:200] if request.url.query else "",
                "status": response.status_code,
                "duration_ms": duration_ms,
                "ip": client_ip,
                "user_agent": request.headers.get("user-agent", "")[:120],
            },
        )
        return response
