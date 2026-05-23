"""
Tenant context extraction and propagation.

Extracts tenant_id from:
  1. X-Tenant-Id request header (primary)
  2. ?tenant_id query param (fallback for GET requests)
  3. Authorization Bearer JWT sub claim (future — stub)

Stores in a contextvars.ContextVar so downstream code can call
get_current_tenant_id() without threading issues.
"""
from __future__ import annotations

import contextvars
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_tenant_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "tenant_id", default=None
)

TENANT_HEADER = "X-Tenant-Id"
PLATFORM_ADMIN_HEADER = "X-Platform-Admin-Key"


def get_current_tenant_id() -> Optional[str]:
    return _tenant_id_var.get()


def set_current_tenant_id(tenant_id: Optional[str]) -> None:
    _tenant_id_var.set(tenant_id)


class TenantContextMiddleware(BaseHTTPMiddleware):
    """
    Injects tenant_id into request.state and context var.
    Does NOT enforce that the tenant exists — that's the router's job.
    Platform admin endpoints (X-Platform-Admin-Key present) bypass tenant scoping.
    """
    def __init__(self, app, require_tenant: bool = False):
        super().__init__(app)
        self.require_tenant = require_tenant

    async def dispatch(self, request: Request, call_next) -> Response:
        # Extract tenant_id
        tenant_id: Optional[str] = (
            request.headers.get(TENANT_HEADER)
            or request.query_params.get("tenant_id")
        )

        request.state.tenant_id = tenant_id
        request.state.is_platform_admin = bool(request.headers.get(PLATFORM_ADMIN_HEADER))

        token = _tenant_id_var.set(tenant_id)
        try:
            response = await call_next(request)
        finally:
            _tenant_id_var.reset(token)

        if tenant_id:
            response.headers[TENANT_HEADER] = tenant_id
        return response
