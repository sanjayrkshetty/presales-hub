"""
Usage metering — records granular usage events and billing transactions.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@dataclass
class MeterResult:
    tenant_id: str
    resource_type: str
    quantity: float
    record_id: str
    overage_charge_usd: float = 0.0


class UsageMeter:
    def __init__(self, db: "Session"):
        self.db = db

    def record(
        self,
        tenant_id: str,
        resource_type: str,
        quantity: float = 1.0,
        endpoint: str = "",
        actor_id: str = "",
        metadata: Optional[dict] = None,
    ) -> MeterResult:
        from models.tenant import UsageRecord
        from hub_platform.quotas.limits import OVERAGE_RATES_USD

        record = UsageRecord(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            resource_type=resource_type,
            quantity=quantity,
            endpoint=endpoint,
            actor_id=actor_id,
            extra_data=metadata or {},
            recorded_at=datetime.utcnow(),
        )
        self.db.add(record)
        self.db.flush()

        rate = OVERAGE_RATES_USD.get(resource_type, 0.0)
        return MeterResult(
            tenant_id=tenant_id,
            resource_type=resource_type,
            quantity=quantity,
            record_id=record.id,
            overage_charge_usd=quantity * rate,
        )

    def record_billing_event(
        self,
        tenant_id: str,
        event_type: str,
        amount_usd: float = 0.0,
        description: str = "",
        resource_type: str = "",
        quantity: float = 0.0,
        metadata: Optional[dict] = None,
    ) -> str:
        from models.tenant import BillingEvent

        ev = BillingEvent(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            event_type=event_type,
            amount_usd=amount_usd,
            description=description,
            resource_type=resource_type,
            quantity=quantity,
            extra_data=metadata or {},
            occurred_at=datetime.utcnow(),
        )
        self.db.add(ev)
        self.db.flush()
        return ev.id

    def get_tenant_usage(
        self,
        tenant_id: str,
        resource_type: Optional[str] = None,
        since: Optional[datetime] = None,
    ) -> list:
        from sqlalchemy import select
        from models.tenant import UsageRecord

        q = select(UsageRecord).where(UsageRecord.tenant_id == tenant_id)
        if resource_type:
            q = q.where(UsageRecord.resource_type == resource_type)
        if since:
            q = q.where(UsageRecord.recorded_at >= since)
        return list(self.db.scalars(q.order_by(UsageRecord.recorded_at.desc())).all())
