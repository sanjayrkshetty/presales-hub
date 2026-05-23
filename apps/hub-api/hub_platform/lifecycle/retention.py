"""
Retention policy enforcement.

Applies per-tenant data retention rules:
- Purge usage records older than retention_days
- Archive (soft-delete) billing events
- Return counts of purged records
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

_DEFAULT_RETENTION_DAYS = 90


@dataclass
class RetentionResult:
    tenant_id: str
    retention_days: int
    usage_records_purged: int
    billing_events_archived: int
    applied_at: str


def apply_retention(
    db: "Session",
    tenant_id: str,
    retention_days: int | None = None,
) -> RetentionResult:
    from sqlalchemy import delete, select
    from models.tenant import Tenant, UsageRecord, BillingEvent

    if retention_days is None:
        tenant = db.get(Tenant, tenant_id)
        if tenant:
            retention_days = tenant.retention_policy.get("retention_days", _DEFAULT_RETENTION_DAYS)
        else:
            retention_days = _DEFAULT_RETENTION_DAYS

    cutoff = datetime.utcnow() - timedelta(days=retention_days)

    # Purge usage records older than cutoff
    usage_result = db.execute(
        delete(UsageRecord)
        .where(UsageRecord.tenant_id == tenant_id)
        .where(UsageRecord.recorded_at < cutoff)
    )
    usage_purged = usage_result.rowcount

    # Archive billing events (mark metadata rather than hard-delete for auditability)
    old_billing = list(
        db.scalars(
            select(BillingEvent)
            .where(BillingEvent.tenant_id == tenant_id)
            .where(BillingEvent.occurred_at < cutoff)
        ).all()
    )
    for ev in old_billing:
        ev.extra_data = {**ev.extra_data, "archived": True, "archived_at": datetime.utcnow().isoformat()}
    db.flush()

    return RetentionResult(
        tenant_id=tenant_id,
        retention_days=retention_days,
        usage_records_purged=usage_purged,
        billing_events_archived=len(old_billing),
        applied_at=datetime.utcnow().isoformat(),
    )
