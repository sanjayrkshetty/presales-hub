"""Request body size limit middleware."""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

MAX_BODY_BYTES = 10 * 1024 * 1024  # 10 MB


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_BODY_BYTES:
            return JSONResponse({"detail": "Request body too large (max 10 MB)"}, status_code=413)
        return await call_next(request)
