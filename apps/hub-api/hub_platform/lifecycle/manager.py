"""
Tenant lifecycle management — wraps provisioner with higher-level operations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@dataclass
class LifecycleEvent:
    tenant_id: str
    event_type: str
    old_status: str
    new_status: str
    actor_id: str
    occurred_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict = field(default_factory=dict)


class TenantLifecycleManager:
    def __init__(self, db: "Session"):
        self.db = db

    def create(self, org_name: str, tier: str = "starter", **kwargs) -> "ProvisionResult":
        from hub_platform.tenants.provisioner import TenantProvisioner
        return TenantProvisioner(self.db).provision_tenant(org_name=org_name, tier=tier, **kwargs)

    def suspend(self, tenant_id: str, reason: str = "", actor_id: str = "system") -> LifecycleEvent:
        return self._apply("suspended", tenant_id, actor_id, reason=reason)

    def activate(self, tenant_id: str, actor_id: str = "system") -> LifecycleEvent:
        return self._apply("active", tenant_id, actor_id)

    def archive(self, tenant_id: str, actor_id: str = "system") -> LifecycleEvent:
        return self._apply("archived", tenant_id, actor_id)

    def delete(self, tenant_id: str, actor_id: str = "system") -> LifecycleEvent:
        return self._apply("deleted", tenant_id, actor_id)

    def get_history(self, tenant_id: str, limit: int = 50) -> list[dict]:
        from sqlalchemy import select
        from models.tenant import TenantAuditLog

        rows = list(
            self.db.scalars(
                select(TenantAuditLog)
                .where(TenantAuditLog.tenant_id == tenant_id)
                .where(TenantAuditLog.action.like("tenant.%"))
                .order_by(TenantAuditLog.occurred_at.desc())
                .limit(limit)
            ).all()
        )
        return [
            {
                "action": r.action,
                "actor_id": r.actor_id,
                "before_state": r.before_state,
                "after_state": r.after_state,
                "occurred_at": r.occurred_at.isoformat(),
            }
            for r in rows
        ]

    def _apply(self, new_status: str, tenant_id: str, actor_id: str, **meta) -> LifecycleEvent:
        from models.tenant import Tenant

        t = self.db.get(Tenant, tenant_id)
        if t is None:
            raise ValueError(f"Tenant {tenant_id!r} not found")
        old_status = t.status
        t.status = new_status
        t.updated_at = datetime.utcnow()
        self.db.flush()
        return LifecycleEvent(
            tenant_id=tenant_id,
            event_type=f"tenant.{new_status}",
            old_status=old_status,
            new_status=new_status,
            actor_id=actor_id,
            metadata=meta,
        )
