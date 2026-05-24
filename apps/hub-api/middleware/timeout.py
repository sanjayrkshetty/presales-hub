"""Request timeout middleware.

Default: 30s for most routes.
Override via X-Timeout-Override header (internal use only) or route-specific config.
Long-running routes (copilot, proposal generation) should set higher limits.
"""
import asyncio
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger("middleware.timeout")

# Per-prefix overrides (seconds). Most specific prefix wins.
_TIMEOUT_OVERRIDES: dict[str, int] = {
    "/api/ai/generate":  120,
    "/copilot":          120,
    "/api/agents":       90,
    "/api/workflows":    60,
    "/ws/":              0,   # WebSocket — no timeout
}
_DEFAULT_TIMEOUT = 30


def _resolve_timeout(path: str) -> int:
    for prefix, t in _TIMEOUT_OVERRIDES.items():
        if path.startswith(prefix):
            return t
    return _DEFAULT_TIMEOUT


class RequestTimeoutMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        timeout = _resolve_timeout(request.url.path)
        if timeout == 0:
            return await call_next(request)

        try:
            return await asyncio.wait_for(call_next(request), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(
                "Request timed out after %ds: %s %s",
                timeout, request.method, request.url.path,
            )
            return JSONResponse(
                {"detail": f"Request timed out after {timeout}s", "path": request.url.path},
                status_code=504,
            )
