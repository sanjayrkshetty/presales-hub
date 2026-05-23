"""
Platform governance audit trail.

Immutable append-only audit log for all admin and tenant-affecting actions.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class GovernanceAuditTrail:
    @staticmethod
    def log(
        db: "Session",
        tenant_id: str,
        action: str,
        actor_id: str = "system",
        resource_type: str = "",
        resource_id: str = "",
        before_state: Optional[dict] = None,
        after_state: Optional[dict] = None,
        ip_address: str = "",
        status: str = "success",
    ) -> str:
        from models.tenant import TenantAuditLog

        entry = TenantAuditLog(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            before_state=before_state or {},
            after_state=after_state or {},
            ip_address=ip_address,
            status=status,
            occurred_at=datetime.utcnow(),
        )
        db.add(entry)
        db.flush()
        return entry.id

    @staticmethod
    def get_tenant_audit(
        db: "Session",
        tenant_id: str,
        action_prefix: Optional[str] = None,
        limit: int = 100,
    ) -> list:
        from sqlalchemy import select
        from models.tenant import TenantAuditLog

        q = select(TenantAuditLog).where(TenantAuditLog.tenant_id == tenant_id)
        if action_prefix:
            q = q.where(TenantAuditLog.action.like(f"{action_prefix}%"))
        q = q.order_by(TenantAuditLog.occurred_at.desc()).limit(limit)
        return list(db.scalars(q).all())

    @staticmethod
    def get_platform_audit(
        db: "Session",
        action_prefix: Optional[str] = None,
        actor_id: Optional[str] = None,
        limit: int = 200,
    ) -> list:
        from sqlalchemy import select
        from models.tenant import TenantAuditLog

        q = select(TenantAuditLog)
        if action_prefix:
            q = q.where(TenantAuditLog.action.like(f"{action_prefix}%"))
        if actor_id:
            q = q.where(TenantAuditLog.actor_id == actor_id)
        q = q.order_by(TenantAuditLog.occurred_at.desc()).limit(limit)
        return list(db.scalars(q).all())
