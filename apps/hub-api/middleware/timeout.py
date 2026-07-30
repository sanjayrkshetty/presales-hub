"""Request timeout middleware.

Default: 30s for most routes.
Override via X-Timeout-Override header (internal use only) or route-specific config.
Long-running routes (copilot, proposal generation) should set higher limits.

Routes using TimeoutAPIRoute with ``timeout_seconds`` own their own
``asyncio.wait_for``; this middleware skips the outer timeout for those
so the default 30s cannot preempt a longer per-route limit.
"""
import asyncio
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Match

logger = logging.getLogger("middleware.timeout")

# Per-prefix overrides (seconds). Most specific prefix wins.
_TIMEOUT_OVERRIDES: dict[str, int] = {
    "/api/ai/proposals/": 180,  # generate-docx belt-and-suspenders if route match misses
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


def _route_owned_timeout(request: Request) -> int | None:
    """Return timeout_seconds if the matched route owns its own wait_for.

    Middleware runs before routing, so ``scope['route']`` is often unset;
    fall back to matching against ``app.router.routes``.
    """
    route = request.scope.get("route")
    if route is not None:
        owned = getattr(route, "timeout_seconds", None)
        if owned:
            return int(owned)

    try:
        routes = request.app.router.routes
    except AttributeError:
        return None

    scope = request.scope
    for candidate in routes:
        match, _child = candidate.matches(scope)
        if match != Match.FULL:
            continue
        owned = getattr(candidate, "timeout_seconds", None)
        if owned:
            return int(owned)
    return None


class RequestTimeoutMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        route_timeout = _route_owned_timeout(request)
        if route_timeout:
            # Route-level TimeoutAPIRoute.wait_for owns the deadline.
            return await call_next(request)

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
