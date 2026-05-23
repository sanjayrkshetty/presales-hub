from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def record_metric(
    db: "Session",
    tenant_id: str,
    platform: str,
    name: str,
    value: float,
    tags: Optional[dict] = None,
) -> str:
    from models.integration import IntegrationMetric

    metric = IntegrationMetric(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        platform=platform,
        metric_name=name,
        value=value,
        tags=tags or {},
        recorded_at=datetime.utcnow(),
    )
    db.add(metric)
    db.flush()
    return metric.id


def get_connector_metrics(db: "Session", tenant_id: str, platform: str) -> dict:
    from sqlalchemy import select
    from models.integration import IntegrationMetric

    rows = list(
        db.scalars(
            select(IntegrationMetric)
            .where(IntegrationMetric.tenant_id == tenant_id)
            .where(IntegrationMetric.platform == platform)
            .order_by(IntegrationMetric.recorded_at.asc())
        ).all()
    )

    by_name: dict[str, list] = {}
    for row in rows:
        by_name.setdefault(row.metric_name, []).append(row)

    result: dict = {}
    for name, entries in by_name.items():
        values = [e.value for e in entries]
        latest = entries[-1]
        result[name] = {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "latest_value": latest.value,
            "latest_recorded_at": latest.recorded_at.isoformat(),
        }
    return result
