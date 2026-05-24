"""AI governance endpoints — token usage, cost, quotas by tenant."""
from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.database import get_db
from models.tenant import UsageRecord, TenantQuota

router = APIRouter(prefix="/api/ai", tags=["ai-governance"])

# Approximate cost per 1K tokens (blended estimate — update to reflect real pricing)
_COST_PER_1K_TOKENS_USD = 0.003


@router.get("/usage/summary")
def usage_summary(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    since = datetime.utcnow() - timedelta(days=days)

    rows = db.execute(
        select(
            UsageRecord.tenant_id,
            UsageRecord.resource_type,
            func.sum(UsageRecord.quantity).label("total"),
            func.count(UsageRecord.id).label("calls"),
        )
        .where(UsageRecord.recorded_at >= since)
        .where(UsageRecord.resource_type.in_(["token", "api_call", "agent_execution"]))
        .group_by(UsageRecord.tenant_id, UsageRecord.resource_type)
    ).all()

    summary: dict[str, dict] = {}
    for row in rows:
        t = row.tenant_id
        if t not in summary:
            summary[t] = {"tenant_id": t, "tokens": 0, "api_calls": 0, "agent_executions": 0, "cost_usd": 0.0}
        if row.resource_type == "token":
            summary[t]["tokens"] += row.total
            summary[t]["cost_usd"] += (row.total / 1000) * _COST_PER_1K_TOKENS_USD
        elif row.resource_type == "api_call":
            summary[t]["api_calls"] += row.calls
        elif row.resource_type == "agent_execution":
            summary[t]["agent_executions"] += row.calls

    return {
        "period_days": days,
        "since": since.isoformat(),
        "tenants": list(summary.values()),
        "totals": {
            "tokens": sum(v["tokens"] for v in summary.values()),
            "api_calls": sum(v["api_calls"] for v in summary.values()),
            "cost_usd": round(sum(v["cost_usd"] for v in summary.values()), 4),
        },
    }


@router.get("/usage/history")
def usage_history(
    days: int = Query(30, ge=1, le=90),
    tenant_id: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """Daily token usage for the last N days."""
    since = datetime.utcnow() - timedelta(days=days)

    q = (
        select(
            func.date(UsageRecord.recorded_at).label("day"),
            func.sum(UsageRecord.quantity).label("tokens"),
            func.count(UsageRecord.id).label("calls"),
        )
        .where(UsageRecord.recorded_at >= since)
        .where(UsageRecord.resource_type == "token")
        .group_by(func.date(UsageRecord.recorded_at))
        .order_by(func.date(UsageRecord.recorded_at))
    )
    if tenant_id:
        q = q.where(UsageRecord.tenant_id == tenant_id)

    rows = db.execute(q).all()
    return [
        {"day": str(r.day), "tokens": int(r.tokens or 0), "calls": int(r.calls or 0)}
        for r in rows
    ]


@router.get("/quotas")
def quotas(db: Session = Depends(get_db)):
    rows = db.scalars(select(TenantQuota)).all()
    return [
        {
            "tenant_id": q.tenant_id,
            "resource_type": q.resource,
            "limit": q.limit_value,
            "used": q.current_usage,
            "pct_used": round((q.current_usage / q.limit_value * 100) if q.limit_value > 0 else 0, 1),
        }
        for q in rows
    ]
