"""Usage aggregation for billing summaries."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@dataclass
class UsageSummary:
    tenant_id: str
    period_start: str
    period_end: str
    by_resource: dict[str, float] = field(default_factory=dict)   # resource_type → total quantity
    total_records: int = 0
    estimated_cost_usd: float = 0.0


class UsageAggregator:
    def aggregate(
        self,
        db: "Session",
        tenant_id: str,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
    ) -> UsageSummary:
        from sqlalchemy import select
        from models.tenant import UsageRecord
        from hub_platform.quotas.limits import OVERAGE_RATES_USD

        q = select(UsageRecord).where(UsageRecord.tenant_id == tenant_id)
        if period_start:
            q = q.where(UsageRecord.recorded_at >= period_start)
        if period_end:
            q = q.where(UsageRecord.recorded_at <= period_end)

        records = list(db.scalars(q).all())

        by_resource: dict[str, float] = {}
        for r in records:
            by_resource[r.resource_type] = by_resource.get(r.resource_type, 0.0) + r.quantity

        cost = sum(
            qty * OVERAGE_RATES_USD.get(rtype, 0.0)
            for rtype, qty in by_resource.items()
        )

        return UsageSummary(
            tenant_id=tenant_id,
            period_start=period_start.isoformat() if period_start else "",
            period_end=period_end.isoformat() if period_end else "",
            by_resource=by_resource,
            total_records=len(records),
            estimated_cost_usd=round(cost, 4),
        )

    def get_billing_summary(self, db: "Session", tenant_id: str) -> dict:
        from sqlalchemy import select
        from models.tenant import BillingEvent

        events = list(
            db.scalars(
                select(BillingEvent)
                .where(BillingEvent.tenant_id == tenant_id)
                .order_by(BillingEvent.occurred_at.desc())
                .limit(100)
            ).all()
        )
        total_charges = sum(e.amount_usd for e in events if e.event_type not in ("credit", "refund"))
        total_credits = sum(e.amount_usd for e in events if e.event_type in ("credit", "refund"))
        return {
            "tenant_id": tenant_id,
            "total_charges_usd": round(total_charges, 4),
            "total_credits_usd": round(total_credits, 4),
            "net_usd": round(total_charges - total_credits, 4),
            "event_count": len(events),
            "recent_events": [
                {"type": e.event_type, "amount": e.amount_usd, "desc": e.description}
                for e in events[:5]
            ],
        }
