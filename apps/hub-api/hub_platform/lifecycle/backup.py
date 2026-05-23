"""
Tenant data export and backup.

Produces a serialisable dict of all tenant-scoped data for:
- GDPR export requests
- Tenant migration
- Scheduled backups
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@dataclass
class BackupManifest:
    tenant_id: str
    exported_at: str
    tables: list[str] = field(default_factory=list)
    total_records: int = 0
    size_estimate_bytes: int = 0
    data: dict = field(default_factory=dict)


class BackupManager:
    def export_tenant_data(
        self,
        db: "Session",
        tenant_id: str,
        include_tables: list[str] | None = None,
    ) -> BackupManifest:
        from sqlalchemy import select, text
        from models.tenant import (
            Tenant, TenantQuota, FeatureFlag, UsageRecord,
            BillingEvent, TenantAuditLog, TenantRole, TenantRoleAssignment,
        )

        all_tables = {
            "tenant": (Tenant, lambda t: t.id == tenant_id),
            "quotas": (TenantQuota, lambda t: t.tenant_id == tenant_id),
            "feature_flags": (FeatureFlag, lambda t: t.tenant_id == tenant_id),
            "usage_records": (UsageRecord, lambda t: t.tenant_id == tenant_id),
            "billing_events": (BillingEvent, lambda t: t.tenant_id == tenant_id),
            "audit_logs": (TenantAuditLog, lambda t: t.tenant_id == tenant_id),
            "roles": (TenantRole, lambda t: t.tenant_id == tenant_id),
            "role_assignments": (TenantRoleAssignment, lambda t: t.tenant_id == tenant_id),
        }

        tables = include_tables or list(all_tables.keys())
        data: dict = {}
        total = 0

        for table_name in tables:
            model_cls, filter_fn = all_tables[table_name]
            rows = list(
                db.scalars(
                    select(model_cls).where(filter_fn(model_cls))
                ).all()
            )
            data[table_name] = [
                {c.name: getattr(row, c.name) for c in model_cls.__table__.columns}
                for row in rows
            ]
            total += len(rows)

        import json
        size = len(json.dumps(data, default=str).encode())

        return BackupManifest(
            tenant_id=tenant_id,
            exported_at=datetime.utcnow().isoformat(),
            tables=tables,
            total_records=total,
            size_estimate_bytes=size,
            data=data,
        )
