"""
Quota enforcement middleware.

Checks api_call quota before each request if tenant_id is known.
Returns HTTP 429 when quota is exhausted.
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from hub_platform.middleware.tenant_context import get_current_tenant_id

# Paths that skip quota enforcement
_EXEMPT_PREFIXES = {"/api/platform/", "/api/health", "/docs", "/openapi"}


class QuotaEnforcementMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        tenant_id = get_current_tenant_id() or getattr(request.state, "tenant_id", None)

        if tenant_id and not any(request.url.path.startswith(p) for p in _EXEMPT_PREFIXES):
            from db.database import SessionLocal
            db = SessionLocal()
            try:
                from hub_platform.quotas.engine import QuotaEngine
                engine = QuotaEngine(db)
                result = engine.check_quota(tenant_id, "api_calls", requested=1)
                if not result.allowed:
                    return JSONResponse(
                        status_code=429,
                        content={
                            "error": "quota_exceeded",
                            "resource": "api_calls",
                            "tenant_id": tenant_id,
                            "limit": result.limit_value,
                            "current_usage": result.current_usage,
                        },
                    )
                # Consume the quota token (best-effort — don't fail request on error)
                try:
                    engine.consume_quota(tenant_id, "api_calls", 1)
                    db.commit()
                except Exception:
                    db.rollback()
            finally:
                db.close()

        return await call_next(request)
