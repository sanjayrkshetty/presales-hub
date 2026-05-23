from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def build_dashboard(db: "Session", tenant_id: str) -> dict:
    from sqlalchemy import select, func
    from models.integration import (
        IntegrationConnector,
        SyncRecord,
        WebhookDelivery,
        RetryJob,
    )
    from integration_fabric.retry.dlq import dlq_summary
    from integration_fabric.rate_limits.limiter import RateLimiter

    # Connector status from DB
    connectors = list(
        db.scalars(
            select(IntegrationConnector).where(
                IntegrationConnector.tenant_id == tenant_id
            )
        ).all()
    )
    connector_status = {c.platform: c.health_status for c in connectors}

    # Sync health
    sync_rows = list(
        db.scalars(
            select(SyncRecord).where(SyncRecord.tenant_id == tenant_id)
        ).all()
    )
    sync_health = {
        "total": len(sync_rows),
        "synced": sum(1 for r in sync_rows if r.sync_status == "synced"),
        "conflict": sum(1 for r in sync_rows if r.sync_status == "conflict"),
        "failed": sum(1 for r in sync_rows if r.sync_status == "failed"),
    }

    # Webhook delivery (last 100)
    deliveries = list(
        db.scalars(
            select(WebhookDelivery)
            .order_by(WebhookDelivery.id.desc())
            .limit(100)
        ).all()
    )
    webhook_delivery = {
        "total": len(deliveries),
        "delivered": sum(1 for d in deliveries if d.status == "delivered"),
        "failed": sum(1 for d in deliveries if d.status == "failed"),
        "dlq": sum(1 for d in deliveries if d.status == "dlq"),
    }

    # Rate limit status per registered connector platform
    from integration_fabric.connectors.base import ConnectorRegistry
    rate_limit_status = {
        platform: RateLimiter.status(tenant_id).get(platform, {})
        for platform in ConnectorRegistry.list_platforms()
    }

    # DLQ summary
    dlq = dlq_summary(db, tenant_id)

    # Failed retry jobs
    failed_jobs = list(
        db.scalars(
            select(RetryJob)
            .where(RetryJob.tenant_id == tenant_id)
            .where(RetryJob.status == "failed")
        ).all()
    )

    return {
        "connector_status": connector_status,
        "sync_health": sync_health,
        "webhook_delivery": webhook_delivery,
        "rate_limit_status": rate_limit_status,
        "dlq_summary": dlq,
        "failed_jobs": len(failed_jobs),
    }
