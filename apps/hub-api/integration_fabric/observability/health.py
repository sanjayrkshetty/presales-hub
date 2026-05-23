from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@dataclass
class ConnectorHealth:
    platform: str
    healthy: bool
    latency_ms: float
    message: str
    last_checked: str  # ISO datetime string


@dataclass
class HealthReport:
    tenant_id: str
    checked_at: str
    connectors: list[ConnectorHealth]
    overall_healthy: bool


def run_health_checks(
    db: "Session",
    tenant_id: str,
    connectors: list,
) -> HealthReport:
    from sqlalchemy import select
    from models.integration import IntegrationConnector

    connector_healths: list[ConnectorHealth] = []
    now = datetime.utcnow().isoformat()

    for connector in connectors:
        platform = getattr(connector, "platform", connector.__class__.__name__.lower())
        try:
            result = connector.healthcheck()
            health = ConnectorHealth(
                platform=platform,
                healthy=result.healthy,
                latency_ms=result.latency_ms,
                message=result.message,
                last_checked=now,
            )
        except Exception as exc:
            health = ConnectorHealth(
                platform=platform,
                healthy=False,
                latency_ms=0.0,
                message=str(exc),
                last_checked=now,
            )

        connector_healths.append(health)

        # Update DB record if it exists — don't create
        ic = db.scalars(
            select(IntegrationConnector)
            .where(IntegrationConnector.tenant_id == tenant_id)
            .where(IntegrationConnector.platform == platform)
        ).first()
        if ic:
            ic.health_status = "healthy" if health.healthy else "unhealthy"
            db.flush()

    overall = all(c.healthy for c in connector_healths) if connector_healths else True

    return HealthReport(
        tenant_id=tenant_id,
        checked_at=now,
        connectors=connector_healths,
        overall_healthy=overall,
    )
