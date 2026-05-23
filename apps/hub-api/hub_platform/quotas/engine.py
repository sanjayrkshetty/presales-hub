"""
Quota engine — check, consume, and reset tenant resource quotas.

All quota checks are DB-backed (TenantQuota rows).
Thread-safe via flush semantics; for distributed deployments replace with
Redis atomic counters.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@dataclass
class QuotaStatus:
    tenant_id: str
    resource: str
    limit_value: int       # -1 = unlimited
    current_usage: int
    remaining: int         # -1 = unlimited
    exhausted: bool
    percent_used: float    # 0.0–100.0; 0.0 if unlimited
    period: str


@dataclass
class QuotaCheckResult:
    allowed: bool
    resource: str
    requested: int
    current_usage: int
    limit_value: int
    reason: str = ""


class QuotaEngine:
    def __init__(self, db: "Session"):
        self.db = db

    def check_quota(
        self,
        tenant_id: str,
        resource: str,
        requested: int = 1,
    ) -> QuotaCheckResult:
        quota = self._get_quota(tenant_id, resource)
        if quota is None:
            return QuotaCheckResult(
                allowed=True,
                resource=resource,
                requested=requested,
                current_usage=0,
                limit_value=-1,
                reason="no_quota_defined",
            )
        if quota.limit_value == -1:
            return QuotaCheckResult(
                allowed=True,
                resource=resource,
                requested=requested,
                current_usage=quota.current_usage,
                limit_value=-1,
                reason="unlimited",
            )
        if quota.current_usage + requested > quota.limit_value:
            return QuotaCheckResult(
                allowed=False,
                resource=resource,
                requested=requested,
                current_usage=quota.current_usage,
                limit_value=quota.limit_value,
                reason="quota_exceeded",
            )
        return QuotaCheckResult(
            allowed=True,
            resource=resource,
            requested=requested,
            current_usage=quota.current_usage,
            limit_value=quota.limit_value,
            reason="ok",
        )

    def consume_quota(
        self,
        tenant_id: str,
        resource: str,
        amount: int = 1,
    ) -> bool:
        result = self.check_quota(tenant_id, resource, amount)
        if not result.allowed:
            return False
        quota = self._get_quota(tenant_id, resource)
        if quota and quota.limit_value != -1:
            quota.current_usage += amount
            quota.updated_at = datetime.utcnow()
            self.db.flush()
        return True

    def get_status(self, tenant_id: str, resource: str) -> Optional[QuotaStatus]:
        quota = self._get_quota(tenant_id, resource)
        if quota is None:
            return None
        unlimited = quota.limit_value == -1
        remaining = -1 if unlimited else max(0, quota.limit_value - quota.current_usage)
        percent = 0.0 if unlimited else round(quota.current_usage / quota.limit_value * 100, 1)
        return QuotaStatus(
            tenant_id=tenant_id,
            resource=resource,
            limit_value=quota.limit_value,
            current_usage=quota.current_usage,
            remaining=remaining,
            exhausted=(not unlimited and quota.current_usage >= quota.limit_value),
            percent_used=percent,
            period=quota.period,
        )

    def get_all_statuses(self, tenant_id: str) -> list[QuotaStatus]:
        from sqlalchemy import select
        from models.tenant import TenantQuota

        quotas = list(
            self.db.scalars(
                select(TenantQuota).where(TenantQuota.tenant_id == tenant_id)
            ).all()
        )
        return [
            self.get_status(tenant_id, q.resource)
            for q in quotas
            if self.get_status(tenant_id, q.resource) is not None
        ]

    def reset_quota(self, tenant_id: str, resource: str) -> bool:
        quota = self._get_quota(tenant_id, resource)
        if quota is None:
            return False
        quota.current_usage = 0
        quota.reset_at = datetime.utcnow()
        quota.updated_at = datetime.utcnow()
        self.db.flush()
        return True

    def update_limit(self, tenant_id: str, resource: str, new_limit: int) -> bool:
        quota = self._get_quota(tenant_id, resource)
        if quota is None:
            return False
        quota.limit_value = new_limit
        quota.updated_at = datetime.utcnow()
        self.db.flush()
        return True

    def _get_quota(self, tenant_id: str, resource: str) -> Optional["TenantQuota"]:
        from sqlalchemy import select
        from models.tenant import TenantQuota

        return self.db.scalars(
            select(TenantQuota)
            .where(TenantQuota.tenant_id == tenant_id)
            .where(TenantQuota.resource == resource)
        ).first()
