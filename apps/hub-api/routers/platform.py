"""
Platform administration API.

All /api/platform/ endpoints require X-Platform-Admin-Key header in production.
In the current stub the header is accepted but not cryptographically verified —
replace with a secrets check before going to production.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.database import get_db
from lib.dependencies import require_permission

router = APIRouter(prefix="/api/platform", tags=["platform"])

_ADMIN_KEY_ENV = "PLATFORM_ADMIN_KEY"


def _require_admin(x_platform_admin_key: str = Header(default="")):
    import os
    expected = os.environ.get(_ADMIN_KEY_ENV, "dev-admin-key")
    if x_platform_admin_key != expected:
        raise HTTPException(status_code=403, detail="Invalid platform admin key")


# ── Request models ─────────────────────────────────────────────────────────────

class ProvisionRequest(BaseModel):
    org_name: str
    tier: str = "starter"
    region: str = "us-east-1"
    admin_email: str = ""
    actor_id: str = "api"
    metadata: dict = {}


class StatusUpdateRequest(BaseModel):
    status: str       # active | suspended | archived
    actor_id: str = "api"
    reason: str = ""


class QuotaUpdateRequest(BaseModel):
    resource: str
    new_limit: int
    actor_id: str = "api"


class FeatureFlagRequest(BaseModel):
    flag_name: str
    enabled: bool
    tenant_id: Optional[str] = None    # None = global flag
    rollout_percent: int = 100
    description: str = ""


# ── Tenant management ──────────────────────────────────────────────────────────

@router.post("/tenants", status_code=201)
def provision_tenant(req: ProvisionRequest, db: Session = Depends(get_db), _authz=require_permission("user:admin")):
    from hub_platform.tenants.provisioner import TenantProvisioner
    result = TenantProvisioner(db).provision_tenant(
        org_name=req.org_name,
        tier=req.tier,
        region=req.region,
        admin_email=req.admin_email,
        actor_id=req.actor_id,
        metadata=req.metadata,
    )
    if not result.success:
        raise HTTPException(status_code=409, detail=result.errors[0] if result.errors else "provision failed")
    db.commit()
    return {
        "tenant_id": result.tenant_id,
        "org_name": result.org_name,
        "tier": result.tier,
        "status": result.status,
    }


@router.get("/tenants")
def list_tenants(
    status: Optional[str] = None,
    tier: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    from hub_platform.tenants.repository import TenantRepository
    tenants = TenantRepository(db).list(status=status, tier=tier, limit=limit, offset=offset)
    return {
        "total": len(tenants),
        "tenants": [
            {
                "id": t.id, "org_name": t.org_name, "tier": t.tier,
                "status": t.status, "region": t.region,
                "created_at": t.created_at.isoformat(),
            }
            for t in tenants
        ],
    }


@router.get("/tenants/noisy")
def detect_noisy_tenants(threshold: int = 1000, db: Session = Depends(get_db)):
    from sqlalchemy import select, func
    from models.tenant import UsageRecord

    rows = list(db.execute(
        select(UsageRecord.tenant_id, func.count(UsageRecord.id).label("cnt"))
        .group_by(UsageRecord.tenant_id)
        .having(func.count(UsageRecord.id) >= threshold)
        .order_by(func.count(UsageRecord.id).desc())
    ).all())
    return {
        "threshold": threshold,
        "noisy_tenants": [{"tenant_id": r[0], "usage_count": r[1]} for r in rows],
    }


@router.get("/tenants/{tenant_id}")
def get_tenant(tenant_id: str, db: Session = Depends(get_db)):
    from hub_platform.tenants.repository import TenantRepository
    t = TenantRepository(db).get(tenant_id)
    if t is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return {
        "id": t.id,
        "org_name": t.org_name,
        "tier": t.tier,
        "status": t.status,
        "region": t.region,
        "admin_email": t.admin_email,
        "billing_plan": t.billing_plan,
        "feature_flags": t.feature_flags,
        "quotas": t.quotas,
        "created_at": t.created_at.isoformat(),
        "updated_at": t.updated_at.isoformat(),
    }


@router.patch("/tenants/{tenant_id}/status")
def update_tenant_status(tenant_id: str, req: StatusUpdateRequest, db: Session = Depends(get_db), _authz=require_permission("user:admin")):
    from hub_platform.tenants.provisioner import TenantProvisioner
    prov = TenantProvisioner(db)

    dispatch = {
        "suspended": lambda: prov.suspend_tenant(tenant_id, req.actor_id, req.reason),
        "active": lambda: prov.activate_tenant(tenant_id, req.actor_id),
        "archived": lambda: prov.archive_tenant(tenant_id, req.actor_id),
        "deleted": lambda: prov.delete_tenant(tenant_id, req.actor_id),
    }
    fn = dispatch.get(req.status)
    if fn is None:
        raise HTTPException(status_code=400, detail=f"Invalid status {req.status!r}")
    ok = fn()
    if not ok:
        raise HTTPException(status_code=404, detail="Tenant not found")
    db.commit()
    return {"tenant_id": tenant_id, "status": req.status}


# ── Usage ──────────────────────────────────────────────────────────────────────

@router.get("/tenants/{tenant_id}/usage")
def get_tenant_usage(tenant_id: str, db: Session = Depends(get_db)):
    from hub_platform.metering.aggregator import UsageAggregator
    summary = UsageAggregator().aggregate(db, tenant_id)
    return {
        "tenant_id": summary.tenant_id,
        "total_records": summary.total_records,
        "by_resource": summary.by_resource,
        "estimated_cost_usd": summary.estimated_cost_usd,
    }


@router.get("/tenants/{tenant_id}/billing")
def get_tenant_billing(tenant_id: str, db: Session = Depends(get_db)):
    from hub_platform.metering.aggregator import UsageAggregator
    return UsageAggregator().get_billing_summary(db, tenant_id)


# ── Quotas ─────────────────────────────────────────────────────────────────────

@router.get("/tenants/{tenant_id}/quotas")
def get_tenant_quotas(tenant_id: str, db: Session = Depends(get_db)):
    from hub_platform.quotas.engine import QuotaEngine
    statuses = QuotaEngine(db).get_all_statuses(tenant_id)
    return {
        "tenant_id": tenant_id,
        "quotas": [
            {
                "resource": s.resource,
                "limit": s.limit_value,
                "used": s.current_usage,
                "remaining": s.remaining,
                "exhausted": s.exhausted,
                "percent_used": s.percent_used,
            }
            for s in statuses
        ],
    }


@router.patch("/tenants/{tenant_id}/quotas")
def update_tenant_quota(tenant_id: str, req: QuotaUpdateRequest, db: Session = Depends(get_db), _authz=require_permission("user:admin")):
    from hub_platform.quotas.engine import QuotaEngine
    from hub_platform.governance.audit_trail import GovernanceAuditTrail

    engine = QuotaEngine(db)
    old = engine.get_status(tenant_id, req.resource)
    ok = engine.update_limit(tenant_id, req.resource, req.new_limit)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Quota for resource {req.resource!r} not found")
    GovernanceAuditTrail.log(
        db=db,
        tenant_id=tenant_id,
        actor_id=req.actor_id,
        action="quota.update",
        resource_type="quota",
        resource_id=req.resource,
        before_state={"limit": old.limit_value if old else None},
        after_state={"limit": req.new_limit},
    )
    db.commit()
    return {"tenant_id": tenant_id, "resource": req.resource, "new_limit": req.new_limit}


# ── Audit ──────────────────────────────────────────────────────────────────────

@router.get("/tenants/{tenant_id}/audit")
def get_tenant_audit(tenant_id: str, limit: int = 50, db: Session = Depends(get_db)):
    from hub_platform.governance.audit_trail import GovernanceAuditTrail
    entries = GovernanceAuditTrail.get_tenant_audit(db, tenant_id, limit=limit)
    return {
        "tenant_id": tenant_id,
        "count": len(entries),
        "entries": [
            {
                "action": e.action, "actor_id": e.actor_id,
                "resource_type": e.resource_type, "resource_id": e.resource_id,
                "status": e.status, "occurred_at": e.occurred_at.isoformat(),
            }
            for e in entries
        ],
    }


# ── Feature flags ──────────────────────────────────────────────────────────────

@router.post("/feature-flags")
def set_feature_flag(req: FeatureFlagRequest, db: Session = Depends(get_db), _authz=require_permission("user:admin")):
    from hub_platform.feature_flags.manager import FeatureFlagManager
    fm = FeatureFlagManager(db)
    flag = fm.set_flag(
        flag_name=req.flag_name,
        enabled=req.enabled,
        tenant_id=req.tenant_id,
        rollout_percent=req.rollout_percent,
        description=req.description,
    )
    db.commit()
    return {
        "id": flag.id,
        "flag_name": flag.flag_name,
        "enabled": flag.enabled,
        "tenant_id": flag.tenant_id,
        "rollout_percent": flag.rollout_percent,
    }


@router.get("/tenants/{tenant_id}/feature-flags")
def get_tenant_feature_flags(tenant_id: str, db: Session = Depends(get_db)):
    from hub_platform.feature_flags.manager import FeatureFlagManager
    flags = FeatureFlagManager(db).get_tenant_flags(tenant_id)
    return {"tenant_id": tenant_id, "flags": flags}


# ── IAM ────────────────────────────────────────────────────────────────────────

@router.get("/tenants/{tenant_id}/roles")
def list_tenant_roles(tenant_id: str, db: Session = Depends(get_db)):
    from hub_platform.governance.iam import PlatformIAM
    roles = PlatformIAM(db).list_roles(tenant_id)
    return {
        "tenant_id": tenant_id,
        "roles": [
            {"role_name": r.role_name, "permissions": r.permissions, "inherits_from": r.inherits_from}
            for r in roles
        ],
    }


# ── Lifecycle + Backup ─────────────────────────────────────────────────────────

@router.get("/tenants/{tenant_id}/export")
def export_tenant_data(tenant_id: str, db: Session = Depends(get_db)):
    from hub_platform.lifecycle.backup import BackupManager
    manifest = BackupManager().export_tenant_data(db, tenant_id)
    return {
        "tenant_id": manifest.tenant_id,
        "exported_at": manifest.exported_at,
        "tables": manifest.tables,
        "total_records": manifest.total_records,
        "size_estimate_bytes": manifest.size_estimate_bytes,
    }


# ── Platform health + observability ───────────────────────────────────────────

@router.get("/health")
def platform_health(db: Session = Depends(get_db)):
    from hub_platform.deployments.manager import DeploymentManager
    info = DeploymentManager().get_deployment_info(db)
    return {
        "status": info.health,
        "environment": info.environment,
        "deployment_mode": info.deployment_mode,
        "tenant_count": info.tenant_count,
        "active_tenant_count": info.active_tenant_count,
        "warnings": info.warnings,
    }


@router.get("/metrics")
def platform_metrics(db: Session = Depends(get_db)):
    from sqlalchemy import select, func
    from models.tenant import Tenant, UsageRecord, BillingEvent

    tenant_by_tier = {}
    rows = list(db.execute(
        select(Tenant.tier, func.count(Tenant.id)).group_by(Tenant.tier)
    ).all())
    for tier, count in rows:
        tenant_by_tier[tier] = count

    total_usage = db.scalar(select(func.count()).select_from(UsageRecord)) or 0
    total_billing = db.scalar(select(func.count()).select_from(BillingEvent)) or 0

    return {
        "tenants_by_tier": tenant_by_tier,
        "total_usage_records": total_usage,
        "total_billing_events": total_billing,
    }


@router.get("/deployment")
def get_deployment_config():
    from hub_platform.environments.config import current_env
    return current_env.to_dict()
