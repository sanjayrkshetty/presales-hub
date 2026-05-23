"""
Tenant lifecycle provisioning.

provision_tenant: create tenant + seed quotas + seed feature flags + audit
suspend_tenant / activate_tenant / archive_tenant: status transitions + audit
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@dataclass
class ProvisionResult:
    success: bool
    tenant_id: str
    org_name: str
    tier: str
    status: str
    errors: list[str] = field(default_factory=list)


class TenantProvisioner:
    def __init__(self, db: "Session"):
        self.db = db

    def provision_tenant(
        self,
        org_name: str,
        tier: str = "starter",
        region: str = "us-east-1",
        admin_email: str = "",
        actor_id: str = "system",
        metadata: Optional[dict] = None,
    ) -> ProvisionResult:
        from hub_platform.tenants.repository import TenantRepository
        from hub_platform.quotas.limits import DEFAULT_QUOTAS
        from hub_platform.feature_flags.defaults import DEFAULT_FLAGS_BY_TIER
        from hub_platform.governance.audit_trail import GovernanceAuditTrail

        repo = TenantRepository(self.db)

        # Check uniqueness
        existing = repo.get_by_org_name(org_name)
        if existing and existing.status != "deleted":
            return ProvisionResult(
                success=False,
                tenant_id="",
                org_name=org_name,
                tier=tier,
                status="failed",
                errors=[f"Organisation {org_name!r} already exists (status={existing.status})"],
            )

        tenant = repo.create(
            org_name=org_name,
            tier=tier,
            region=region,
            admin_email=admin_email,
            metadata=metadata or {},
        )

        # Seed tier-appropriate quotas
        self._seed_quotas(tenant.id, tier)

        # Seed feature flags for tier
        flags = DEFAULT_FLAGS_BY_TIER.get(tier, {})
        tenant.feature_flags = flags
        tenant.status = "active"
        self.db.flush()

        # Audit
        GovernanceAuditTrail.log(
            db=self.db,
            tenant_id=tenant.id,
            actor_id=actor_id,
            action="tenant.provision",
            resource_type="tenant",
            resource_id=tenant.id,
            after_state={"org_name": org_name, "tier": tier, "region": region},
        )

        return ProvisionResult(
            success=True,
            tenant_id=tenant.id,
            org_name=org_name,
            tier=tier,
            status="active",
        )

    def suspend_tenant(self, tenant_id: str, actor_id: str = "system", reason: str = "") -> bool:
        return self._transition(tenant_id, "suspended", actor_id, "tenant.suspend", {"reason": reason})

    def activate_tenant(self, tenant_id: str, actor_id: str = "system") -> bool:
        return self._transition(tenant_id, "active", actor_id, "tenant.activate", {})

    def archive_tenant(self, tenant_id: str, actor_id: str = "system") -> bool:
        return self._transition(tenant_id, "archived", actor_id, "tenant.archive", {})

    def delete_tenant(self, tenant_id: str, actor_id: str = "system") -> bool:
        return self._transition(tenant_id, "deleted", actor_id, "tenant.delete", {})

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _transition(
        self, tenant_id: str, new_status: str, actor_id: str, action: str, extra: dict
    ) -> bool:
        from models.tenant import Tenant
        from hub_platform.governance.audit_trail import GovernanceAuditTrail

        t = self.db.get(Tenant, tenant_id)
        if t is None:
            return False
        old_status = t.status
        t.status = new_status
        t.updated_at = datetime.utcnow()
        self.db.flush()
        GovernanceAuditTrail.log(
            db=self.db,
            tenant_id=tenant_id,
            actor_id=actor_id,
            action=action,
            resource_type="tenant",
            resource_id=tenant_id,
            before_state={"status": old_status},
            after_state={"status": new_status, **extra},
        )
        return True

    def _seed_quotas(self, tenant_id: str, tier: str) -> None:
        from hub_platform.quotas.limits import DEFAULT_QUOTAS
        from models.tenant import TenantQuota

        quotas = DEFAULT_QUOTAS.get(tier, DEFAULT_QUOTAS["starter"])
        for resource, limit in quotas.items():
            q = TenantQuota(
                id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                resource=resource,
                limit_value=limit,
                current_usage=0,
                period="monthly",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            self.db.add(q)
        self.db.flush()
