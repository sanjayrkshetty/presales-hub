"""
Usage tracker — thin wrapper used by middleware and endpoint hooks
to record API calls without requiring the caller to instantiate UsageMeter.
"""
from __future__ import annotations

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def track_api_call(
    db: "Session",
    tenant_id: str,
    endpoint: str = "",
    actor_id: str = "",
    metadata: Optional[dict] = None,
) -> None:
    from hub_platform.billing.meter import UsageMeter
    meter = UsageMeter(db)
    meter.record(
        tenant_id=tenant_id,
        resource_type="api_call",
        quantity=1.0,
        endpoint=endpoint,
        actor_id=actor_id,
        metadata=metadata or {},
    )


def track_token_usage(
    db: "Session",
    tenant_id: str,
    token_count: int,
    model: str = "",
    actor_id: str = "",
) -> None:
    from hub_platform.billing.meter import UsageMeter
    meter = UsageMeter(db)
    meter.record(
        tenant_id=tenant_id,
        resource_type="token",
        quantity=float(token_count),
        endpoint=model,
        actor_id=actor_id,
    )


def track_workflow_execution(
    db: "Session",
    tenant_id: str,
    workflow_id: str = "",
    actor_id: str = "",
) -> None:
    from hub_platform.billing.meter import UsageMeter
    meter = UsageMeter(db)
    meter.record(
        tenant_id=tenant_id,
        resource_type="workflow",
        quantity=1.0,
        endpoint=workflow_id,
        actor_id=actor_id,
    )
