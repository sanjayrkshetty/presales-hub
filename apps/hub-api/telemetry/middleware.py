import uuid
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from telemetry.context import set_correlation_id, set_request_id, get_correlation_id

logger = logging.getLogger("telemetry.middleware")

_HEADER_CORRELATION = "X-Correlation-ID"
_HEADER_REQUEST = "X-Request-ID"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Per-request correlation ID middleware.

    Reads X-Correlation-ID from incoming headers (use this to chain
    requests across services) or generates a new UUID4.  Generates a
    fresh per-request UUID4 for X-Request-ID regardless.

    Both IDs are:
    - stored in ContextVars so all downstream code can read them
    - echoed in response headers for client-side tracing
    - attached to the current OTel span (set by FastAPI auto-instrumentation)
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        correlation_id = request.headers.get(_HEADER_CORRELATION) or str(uuid.uuid4())
        request_id = str(uuid.uuid4())

        set_correlation_id(correlation_id)
        set_request_id(request_id)

        # Enrich the OTel span created by FastAPI auto-instrumentation.
        # safe: get_current_span() returns a no-op span when OTel is absent.
        try:
            from opentelemetry import trace
            span = trace.get_current_span()
            if span.is_recording():
                span.set_attribute("http.correlation_id", correlation_id)
                span.set_attribute("http.request_id", request_id)
        except ImportError:
            pass

        response = await call_next(request)
        response.headers[_HEADER_CORRELATION] = correlation_id
        response.headers[_HEADER_REQUEST] = request_id
        return response
