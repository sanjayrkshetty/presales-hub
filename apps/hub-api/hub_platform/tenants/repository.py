"""Tenant CRUD repository."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class TenantRepository:
    def __init__(self, db: "Session"):
        self.db = db

    def create(
        self,
        org_name: str,
        tier: str = "starter",
        region: str = "us-east-1",
        admin_email: str = "",
        quotas: Optional[dict] = None,
        feature_flags: Optional[dict] = None,
        billing_plan: str = "",
        metadata: Optional[dict] = None,
    ) -> "Tenant":
        from models.tenant import Tenant

        tenant = Tenant(
            id=str(uuid.uuid4()),
            org_name=org_name,
            tier=tier,
            region=region,
            status="provisioning",
            admin_email=admin_email,
            quotas=quotas or {},
            feature_flags=feature_flags or {},
            billing_plan=billing_plan,
            extra_data=metadata or {},
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(tenant)
        self.db.flush()
        return tenant

    def get(self, tenant_id: str) -> Optional["Tenant"]:
        from models.tenant import Tenant
        return self.db.get(Tenant, tenant_id)

    def get_by_org_name(self, org_name: str) -> Optional["Tenant"]:
        from sqlalchemy import select
        from models.tenant import Tenant
        return self.db.scalars(
            select(Tenant).where(Tenant.org_name == org_name)
        ).first()

    def list(
        self,
        status: Optional[str] = None,
        tier: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list:
        from sqlalchemy import select
        from models.tenant import Tenant

        q = select(Tenant)
        if status:
            q = q.where(Tenant.status == status)
        if tier:
            q = q.where(Tenant.tier == tier)
        q = q.order_by(Tenant.created_at.desc()).limit(limit).offset(offset)
        return list(self.db.scalars(q).all())

    def update(self, tenant_id: str, **fields) -> Optional["Tenant"]:
        from models.tenant import Tenant
        t = self.db.get(Tenant, tenant_id)
        if t is None:
            return None
        for k, v in fields.items():
            if hasattr(t, k):
                setattr(t, k, v)
        t.updated_at = datetime.utcnow()
        self.db.flush()
        return t

    def delete(self, tenant_id: str) -> bool:
        from models.tenant import Tenant
        t = self.db.get(Tenant, tenant_id)
        if t is None:
            return False
        t.status = "deleted"
        t.updated_at = datetime.utcnow()
        self.db.flush()
        return True

    def count(self, status: Optional[str] = None) -> int:
        from sqlalchemy import select, func
        from models.tenant import Tenant
        q = select(func.count()).select_from(Tenant)
        if status:
            q = q.where(Tenant.status == status)
        return self.db.scalar(q) or 0
