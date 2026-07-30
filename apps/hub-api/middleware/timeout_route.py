"""Per-route request timeout via FastAPI APIRoute.

Attach ``timeout_seconds`` on a route (via ``with_timeout`` or by setting the
attribute on the route) so ``asyncio.wait_for`` wraps only that endpoint.
RequestTimeoutMiddleware skips its outer wait_for when the matched route
owns a timeout, so the default 30s middleware limit cannot preempt a longer
route timeout (e.g. generate-docx at 180s).
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from fastapi.routing import APIRoute
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger("middleware.timeout_route")


class TimeoutAPIRoute(APIRoute):
    """APIRoute that optionally enforces ``timeout_seconds`` around the handler."""

    timeout_seconds: int | None = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        endpoint_timeout = getattr(self.endpoint, "__timeout_seconds__", None)
        if endpoint_timeout is not None:
            self.timeout_seconds = int(endpoint_timeout)

    def get_route_handler(self) -> Callable:
        original = super().get_route_handler()
        timeout = self.timeout_seconds
        if not timeout:
            return original

        async def timed_handler(request: Request) -> Response:
            try:
                return await asyncio.wait_for(original(request), timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning(
                    "Route timed out after %ds: %s %s",
                    timeout,
                    request.method,
                    request.url.path,
                )
                return JSONResponse(
                    {
                        "detail": f"Request timed out after {timeout}s",
                        "path": request.url.path,
                    },
                    status_code=504,
                )

        return timed_handler


def with_timeout(seconds: int) -> Callable[[Callable], Callable]:
    """Mark an endpoint so TimeoutAPIRoute applies ``asyncio.wait_for``."""

    def decorator(fn: Callable) -> Callable:
        fn.__timeout_seconds__ = int(seconds)  # type: ignore[attr-defined]
        return fn

    return decorator
