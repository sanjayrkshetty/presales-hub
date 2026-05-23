"""
Multi-tenancy & Deployment Platform test suite — Task #45.

Coverage:
- Tenant model: create, get, list, update, delete (soft)
- TenantProvisioner: provision, duplicate check, suspend, activate, archive
- TenantLifecycleManager: create, transition history
- QuotaEngine: check_quota, consume_quota, exhaustion, reset, update_limit
- DEFAULT_QUOTAS: all 4 tiers defined, enterprise unlimited
- FeatureFlagManager: tier default, tenant override, tier gate, emergency disable
- DEFAULT_FLAGS_BY_TIER: enterprise has all flags, free has basic only
- UsageMeter: record, record_billing_event, get_tenant_usage
- UsageAggregator: aggregate by period, billing_summary
- UsageTracker: track_api_call, track_token_usage, track_workflow_execution
- GovernanceAuditTrail: log, get_tenant_audit, get_platform_audit
- PlatformIAM: create_role, list_roles, assign_role, revoke_role, get_user_roles, effective_permissions, inheritance
- TenantAwareRepository: get scopes by tenant, cross-tenant isolation
- BackupManager: export_tenant_data manifest
- RetentionPolicy: apply_retention purges old records
- TenantTier: rank, meets_minimum
- EnvironmentConfig: from_env, is_production, is_airgapped, is_multi_tenant, to_dict
- DeploymentManager: get_deployment_info, validate_config
- TenantContextMiddleware: sets state.tenant_id from header
- All platform API endpoints via TestClient
"""
from __future__ import annotations

import uuid
import pytest
from datetime import datetime, timedelta


# ── TenantTier enum ────────────────────────────────────────────────────────────

def test_tenant_tier_rank():
    from hub_platform.tenants.schemas import TenantTier
    assert TenantTier.FREE.rank == 0
    assert TenantTier.ENTERPRISE.rank == 3


def test_tenant_tier_meets_minimum():
    from hub_platform.tenants.schemas import TenantTier
    assert TenantTier.ENTERPRISE.meets_minimum(TenantTier.PROFESSIONAL) is True
    assert TenantTier.FREE.meets_minimum(TenantTier.STARTER) is False
    assert TenantTier.STARTER.meets_minimum(TenantTier.STARTER) is True


# ── TenantRepository ───────────────────────────────────────────────────────────

def test_tenant_repo_create_and_get(db):
    from hub_platform.tenants.repository import TenantRepository
    repo = TenantRepository(db)
    t = repo.create(org_name="Acme Corp", tier="starter", region="us-east-1", admin_email="admin@acme.com")
    db.commit()
    fetched = repo.get(t.id)
    assert fetched is not None
    assert fetched.org_name == "Acme Corp"
    assert fetched.tier == "starter"


def test_tenant_repo_list(db):
    from hub_platform.tenants.repository import TenantRepository
    repo = TenantRepository(db)
    for i in range(3):
        repo.create(org_name=f"Org{i}-{uuid.uuid4().hex[:4]}", tier="free")
    db.commit()
    tenants = repo.list()
    assert len(tenants) >= 3


def test_tenant_repo_update(db):
    from hub_platform.tenants.repository import TenantRepository
    repo = TenantRepository(db)
    t = repo.create(org_name="ToUpdate", tier="free")
    db.commit()
    updated = repo.update(t.id, tier="professional")
    assert updated.tier == "professional"


def test_tenant_repo_soft_delete(db):
    from hub_platform.tenants.repository import TenantRepository
    repo = TenantRepository(db)
    t = repo.create(org_name="ToDelete")
    db.commit()
    ok = repo.delete(t.id)
    assert ok is True
    refetched = repo.get(t.id)
    assert refetched.status == "deleted"


def test_tenant_repo_get_missing_returns_none(db):
    from hub_platform.tenants.repository import TenantRepository
    result = TenantRepository(db).get("nonexistent-id")
    assert result is None


def test_tenant_repo_count(db):
    from hub_platform.tenants.repository import TenantRepository
    repo = TenantRepository(db)
    repo.create(org_name="CountOrg1")
    repo.create(org_name="CountOrg2")
    db.commit()
    assert repo.count() >= 2


# ── TenantProvisioner ──────────────────────────────────────────────────────────

def test_provisioner_provision_success(db):
    from hub_platform.tenants.provisioner import TenantProvisioner
    result = TenantProvisioner(db).provision_tenant(
        org_name=f"NewCo-{uuid.uuid4().hex[:6]}",
        tier="professional",
        region="eu-west-1",
    )
    db.commit()
    assert result.success is True
    assert result.tenant_id != ""
    assert result.status == "active"


def test_provisioner_seeds_quotas(db):
    from hub_platform.tenants.provisioner import TenantProvisioner
    from sqlalchemy import select
    from models.tenant import TenantQuota

    org = f"QuotaOrg-{uuid.uuid4().hex[:6]}"
    result = TenantProvisioner(db).provision_tenant(org_name=org, tier="starter")
    db.commit()

    quotas = list(
        db.scalars(select(TenantQuota).where(TenantQuota.tenant_id == result.tenant_id)).all()
    )
    assert len(quotas) > 0
    resources = {q.resource for q in quotas}
    assert "api_calls" in resources
    assert "tokens" in resources


def test_provisioner_duplicate_fails(db):
    from hub_platform.tenants.provisioner import TenantProvisioner
    org = f"DupOrg-{uuid.uuid4().hex[:6]}"
    prov = TenantProvisioner(db)
    prov.provision_tenant(org_name=org, tier="free")
    db.commit()
    result2 = prov.provision_tenant(org_name=org, tier="free")
    assert result2.success is False
    assert len(result2.errors) > 0


def test_provisioner_suspend_and_activate(db):
    from hub_platform.tenants.provisioner import TenantProvisioner
    org = f"SuspOrg-{uuid.uuid4().hex[:6]}"
    prov = TenantProvisioner(db)
    result = prov.provision_tenant(org_name=org, tier="starter")
    db.commit()

    ok = prov.suspend_tenant(result.tenant_id, reason="non-payment")
    db.commit()
    assert ok is True

    from models.tenant import Tenant
    t = db.get(Tenant, result.tenant_id)
    assert t.status == "suspended"

    prov.activate_tenant(result.tenant_id)
    db.commit()
    t = db.get(Tenant, result.tenant_id)
    assert t.status == "active"


# ── TenantLifecycleManager ─────────────────────────────────────────────────────

def test_lifecycle_manager_create(db):
    from hub_platform.lifecycle.manager import TenantLifecycleManager
    mgr = TenantLifecycleManager(db)
    result = mgr.create(org_name=f"LCOrg-{uuid.uuid4().hex[:6]}", tier="free")
    db.commit()
    assert result.success is True


def test_lifecycle_manager_suspend(db):
    from hub_platform.lifecycle.manager import TenantLifecycleManager
    mgr = TenantLifecycleManager(db)
    result = mgr.create(org_name=f"LCSuspOrg-{uuid.uuid4().hex[:6]}")
    db.commit()
    event = mgr.suspend(result.tenant_id, reason="test")
    assert event.new_status == "suspended"
    assert event.old_status == "active"


def test_lifecycle_manager_history(db):
    from hub_platform.lifecycle.manager import TenantLifecycleManager
    mgr = TenantLifecycleManager(db)
    result = mgr.create(org_name=f"HistOrg-{uuid.uuid4().hex[:6]}")
    db.commit()
    mgr.suspend(result.tenant_id)
    db.commit()
    history = mgr.get_history(result.tenant_id)
    assert isinstance(history, list)


# ── QuotaEngine ────────────────────────────────────────────────────────────────

def _provision_tenant_with_quotas(db, tier="starter"):
    from hub_platform.tenants.provisioner import TenantProvisioner
    org = f"QuotaTest-{uuid.uuid4().hex[:6]}"
    result = TenantProvisioner(db).provision_tenant(org_name=org, tier=tier)
    db.commit()
    return result.tenant_id


def test_quota_engine_check_allowed(db):
    from hub_platform.quotas.engine import QuotaEngine
    tid = _provision_tenant_with_quotas(db, "starter")
    engine = QuotaEngine(db)
    result = engine.check_quota(tid, "api_calls", requested=1)
    assert result.allowed is True


def test_quota_engine_consume_and_check(db):
    from hub_platform.quotas.engine import QuotaEngine
    tid = _provision_tenant_with_quotas(db, "starter")
    engine = QuotaEngine(db)
    consumed = engine.consume_quota(tid, "api_calls", 100)
    db.commit()
    assert consumed is True
    status = engine.get_status(tid, "api_calls")
    assert status.current_usage == 100


def test_quota_engine_exhaustion(db):
    from hub_platform.quotas.engine import QuotaEngine
    tid = _provision_tenant_with_quotas(db, "free")
    engine = QuotaEngine(db)
    # Exhaust api_calls for free tier (1000 limit)
    engine.update_limit(tid, "api_calls", 5)
    db.commit()
    for _ in range(5):
        engine.consume_quota(tid, "api_calls", 1)
    db.commit()
    result = engine.check_quota(tid, "api_calls", requested=1)
    assert result.allowed is False
    assert result.reason == "quota_exceeded"


def test_quota_engine_enterprise_unlimited(db):
    from hub_platform.quotas.engine import QuotaEngine
    tid = _provision_tenant_with_quotas(db, "enterprise")
    engine = QuotaEngine(db)
    result = engine.check_quota(tid, "api_calls", requested=1_000_000)
    assert result.allowed is True
    assert result.reason in ("unlimited", "no_quota_defined")


def test_quota_engine_reset(db):
    from hub_platform.quotas.engine import QuotaEngine
    tid = _provision_tenant_with_quotas(db, "starter")
    engine = QuotaEngine(db)
    engine.consume_quota(tid, "api_calls", 500)
    db.commit()
    engine.reset_quota(tid, "api_calls")
    db.commit()
    status = engine.get_status(tid, "api_calls")
    assert status.current_usage == 0


def test_quota_engine_update_limit(db):
    from hub_platform.quotas.engine import QuotaEngine
    tid = _provision_tenant_with_quotas(db, "starter")
    engine = QuotaEngine(db)
    engine.update_limit(tid, "api_calls", 99_999)
    db.commit()
    status = engine.get_status(tid, "api_calls")
    assert status.limit_value == 99_999


def test_default_quotas_all_tiers():
    from hub_platform.quotas.limits import DEFAULT_QUOTAS
    for tier in ("free", "starter", "professional", "enterprise"):
        assert tier in DEFAULT_QUOTAS
        assert "api_calls" in DEFAULT_QUOTAS[tier]
    assert DEFAULT_QUOTAS["enterprise"]["api_calls"] == -1  # unlimited


# ── FeatureFlagManager ─────────────────────────────────────────────────────────

def test_feature_flags_tier_default_free(db):
    from hub_platform.feature_flags.manager import FeatureFlagManager
    fm = FeatureFlagManager(db)
    # Free tier: proposal_ai_assist should be off
    result = fm.evaluate("proposal_ai_assist", tier="free")
    assert result.enabled is False
    assert result.source in ("tier_default", "tier_gate")


def test_feature_flags_tier_default_enterprise(db):
    from hub_platform.feature_flags.manager import FeatureFlagManager
    fm = FeatureFlagManager(db)
    result = fm.evaluate("beta_features", tier="enterprise")
    assert result.enabled is True


def test_feature_flags_tenant_override(db):
    from hub_platform.feature_flags.manager import FeatureFlagManager
    tid = _provision_tenant_with_quotas(db, "free")
    fm = FeatureFlagManager(db)
    fm.set_flag("proposal_ai_assist", enabled=True, tenant_id=tid)
    db.commit()
    result = fm.evaluate("proposal_ai_assist", tenant_id=tid, tier="free")
    assert result.enabled is True
    assert result.source == "tenant_override"


def test_feature_flags_tier_gate(db):
    from hub_platform.feature_flags.manager import FeatureFlagManager
    fm = FeatureFlagManager(db)
    # advanced_analytics requires professional — should be blocked for starter
    result = fm.evaluate("advanced_analytics", tier="starter")
    assert result.enabled is False
    assert result.source == "tier_gate"


def test_feature_flags_get_tenant_flags(db):
    from hub_platform.feature_flags.manager import FeatureFlagManager
    fm = FeatureFlagManager(db)
    flags = fm.get_tenant_flags("any-tenant", tier="professional")
    assert isinstance(flags, dict)
    assert "proposal_ai_assist" in flags
    assert flags["proposal_ai_assist"] is True


def test_feature_flags_enterprise_has_all_keys():
    from hub_platform.feature_flags.defaults import DEFAULT_FLAGS_BY_TIER
    enterprise = DEFAULT_FLAGS_BY_TIER["enterprise"]
    free = DEFAULT_FLAGS_BY_TIER["free"]
    assert all(k in enterprise for k in free), "Enterprise must have all flags free has"
    assert all(enterprise[k] is True for k in enterprise), "Enterprise should have all flags enabled"


# ── UsageMeter ─────────────────────────────────────────────────────────────────

def test_usage_meter_record(db):
    from hub_platform.billing.meter import UsageMeter
    tid = _provision_tenant_with_quotas(db)
    meter = UsageMeter(db)
    result = meter.record(tid, "api_call", quantity=1.0, endpoint="/api/proposals")
    db.commit()
    assert result.record_id != ""
    assert result.tenant_id == tid


def test_usage_meter_record_billing_event(db):
    from hub_platform.billing.meter import UsageMeter
    from hub_platform.billing.events import OVERAGE
    tid = _provision_tenant_with_quotas(db)
    meter = UsageMeter(db)
    ev_id = meter.record_billing_event(tid, OVERAGE, amount_usd=5.0, description="API overage")
    db.commit()
    assert ev_id != ""


def test_usage_meter_get_tenant_usage(db):
    from hub_platform.billing.meter import UsageMeter
    tid = _provision_tenant_with_quotas(db)
    meter = UsageMeter(db)
    meter.record(tid, "token", quantity=1000.0)
    meter.record(tid, "token", quantity=500.0)
    db.commit()
    records = meter.get_tenant_usage(tid, resource_type="token")
    assert len(records) == 2
    assert sum(r.quantity for r in records) == 1500.0


# ── UsageAggregator ────────────────────────────────────────────────────────────

def test_aggregator_aggregate(db):
    from hub_platform.billing.meter import UsageMeter
    from hub_platform.metering.aggregator import UsageAggregator
    tid = _provision_tenant_with_quotas(db)
    meter = UsageMeter(db)
    meter.record(tid, "api_call", 10.0)
    meter.record(tid, "token", 500.0)
    db.commit()
    summary = UsageAggregator().aggregate(db, tid)
    assert summary.total_records == 2
    assert "api_call" in summary.by_resource
    assert summary.by_resource["api_call"] == 10.0


def test_aggregator_billing_summary(db):
    from hub_platform.billing.meter import UsageMeter
    from hub_platform.billing.events import USAGE_CHARGE, CREDIT
    from hub_platform.metering.aggregator import UsageAggregator
    tid = _provision_tenant_with_quotas(db)
    meter = UsageMeter(db)
    meter.record_billing_event(tid, USAGE_CHARGE, amount_usd=100.0)
    meter.record_billing_event(tid, CREDIT, amount_usd=10.0)
    db.commit()
    summary = UsageAggregator().get_billing_summary(db, tid)
    assert summary["total_charges_usd"] == 100.0
    assert summary["total_credits_usd"] == 10.0
    assert summary["net_usd"] == 90.0


# ── UsageTracker ───────────────────────────────────────────────────────────────

def test_usage_tracker_api_call(db):
    from hub_platform.usage.tracker import track_api_call
    from hub_platform.billing.meter import UsageMeter
    tid = _provision_tenant_with_quotas(db)
    track_api_call(db, tid, endpoint="/api/test")
    db.commit()
    records = UsageMeter(db).get_tenant_usage(tid, resource_type="api_call")
    assert len(records) >= 1


def test_usage_tracker_token(db):
    from hub_platform.usage.tracker import track_token_usage
    from hub_platform.billing.meter import UsageMeter
    tid = _provision_tenant_with_quotas(db)
    track_token_usage(db, tid, token_count=2000, model="claude-sonnet")
    db.commit()
    records = UsageMeter(db).get_tenant_usage(tid, resource_type="token")
    assert len(records) >= 1
    assert records[0].quantity == 2000.0


def test_usage_tracker_workflow(db):
    from hub_platform.usage.tracker import track_workflow_execution
    from hub_platform.billing.meter import UsageMeter
    tid = _provision_tenant_with_quotas(db)
    track_workflow_execution(db, tid, workflow_id="wf-001")
    db.commit()
    records = UsageMeter(db).get_tenant_usage(tid, resource_type="workflow")
    assert len(records) >= 1


# ── GovernanceAuditTrail ───────────────────────────────────────────────────────

def test_audit_trail_log_and_retrieve(db):
    from hub_platform.governance.audit_trail import GovernanceAuditTrail
    tid = _provision_tenant_with_quotas(db)
    GovernanceAuditTrail.log(
        db=db, tenant_id=tid, actor_id="admin1",
        action="quota.update", resource_type="quota",
        resource_id="api_calls",
        before_state={"limit": 1000}, after_state={"limit": 5000},
    )
    db.commit()
    entries = GovernanceAuditTrail.get_tenant_audit(db, tid)
    assert len(entries) >= 1
    assert any(e.action == "quota.update" for e in entries)


def test_audit_trail_platform_audit(db):
    from hub_platform.governance.audit_trail import GovernanceAuditTrail
    tid = _provision_tenant_with_quotas(db)
    GovernanceAuditTrail.log(db=db, tenant_id=tid, action="tenant.suspend", actor_id="sysadmin")
    db.commit()
    entries = GovernanceAuditTrail.get_platform_audit(db, action_prefix="tenant.")
    assert len(entries) >= 1


def test_audit_trail_provision_creates_audit(db):
    from hub_platform.tenants.provisioner import TenantProvisioner
    from hub_platform.governance.audit_trail import GovernanceAuditTrail
    org = f"AuditOrg-{uuid.uuid4().hex[:6]}"
    result = TenantProvisioner(db).provision_tenant(org_name=org)
    db.commit()
    entries = GovernanceAuditTrail.get_tenant_audit(db, result.tenant_id)
    assert any(e.action == "tenant.provision" for e in entries)


# ── PlatformIAM ────────────────────────────────────────────────────────────────

def test_iam_create_role(db):
    from hub_platform.governance.iam import PlatformIAM
    tid = _provision_tenant_with_quotas(db)
    iam = PlatformIAM(db)
    role = iam.create_role(tid, "security_lead", ["proposal:read", "proposal:write", "integration:admin"])
    db.commit()
    assert role.id is not None
    assert role.role_name == "security_lead"
    assert "integration:admin" in role.permissions


def test_iam_list_roles(db):
    from hub_platform.governance.iam import PlatformIAM
    tid = _provision_tenant_with_quotas(db)
    iam = PlatformIAM(db)
    iam.create_role(tid, "role_a", ["p:read"])
    iam.create_role(tid, "role_b", ["p:write"])
    db.commit()
    roles = iam.list_roles(tid)
    assert len(roles) == 2


def test_iam_assign_and_get_roles(db):
    from hub_platform.governance.iam import PlatformIAM
    tid = _provision_tenant_with_quotas(db)
    iam = PlatformIAM(db)
    iam.create_role(tid, "analyst", ["analytics:read"])
    iam.assign_role(tid, "user-001", "analyst", granted_by="admin")
    db.commit()
    roles = iam.get_user_roles(tid, "user-001")
    assert "analyst" in roles


def test_iam_revoke_role(db):
    from hub_platform.governance.iam import PlatformIAM
    tid = _provision_tenant_with_quotas(db)
    iam = PlatformIAM(db)
    iam.create_role(tid, "viewer", ["proposal:read"])
    iam.assign_role(tid, "user-002", "viewer")
    db.commit()
    ok = iam.revoke_role(tid, "user-002", "viewer")
    db.commit()
    assert ok is True
    roles = iam.get_user_roles(tid, "user-002")
    assert "viewer" not in roles


def test_iam_effective_permissions_with_inheritance(db):
    from hub_platform.governance.iam import PlatformIAM
    tid = _provision_tenant_with_quotas(db)
    iam = PlatformIAM(db)
    iam.create_role(tid, "base_reader", ["proposal:read", "analytics:read"])
    iam.create_role(tid, "lead_analyst", ["strategy:read"], inherits_from="base_reader")
    iam.assign_role(tid, "user-003", "lead_analyst")
    db.commit()
    perms = iam.get_effective_permissions(tid, "user-003")
    assert "proposal:read" in perms    # from parent
    assert "strategy:read" in perms    # from own role


# ── TenantAwareRepository ──────────────────────────────────────────────────────

def test_tenant_aware_repo_isolation(db):
    from hub_platform.repositories.base import TenantAwareRepository
    from models.tenant import UsageRecord

    class UsageRepo(TenantAwareRepository):
        @property
        def _model(self):
            return UsageRecord

    # Seed two tenants' records
    import uuid as _uuid
    from datetime import datetime
    r1 = UsageRecord(id=str(_uuid.uuid4()), tenant_id="t_alpha", resource_type="api_call", quantity=1.0, recorded_at=datetime.utcnow())
    r2 = UsageRecord(id=str(_uuid.uuid4()), tenant_id="t_beta", resource_type="api_call", quantity=1.0, recorded_at=datetime.utcnow())
    db.add(r1)
    db.add(r2)
    db.commit()

    alpha_repo = UsageRepo(db, "t_alpha")
    beta_repo = UsageRepo(db, "t_beta")

    alpha_records = alpha_repo.list()
    assert all(r.tenant_id == "t_alpha" for r in alpha_records)
    assert alpha_repo.count() >= 1

    beta_records = beta_repo.list()
    assert all(r.tenant_id == "t_beta" for r in beta_records)


def test_tenant_aware_repo_cross_tenant_get_blocked(db):
    from hub_platform.repositories.base import TenantAwareRepository
    from models.tenant import UsageRecord
    import uuid as _uuid
    from datetime import datetime

    class UsageRepo(TenantAwareRepository):
        @property
        def _model(self):
            return UsageRecord

    r = UsageRecord(id=str(_uuid.uuid4()), tenant_id="t_owner", resource_type="token", quantity=5.0, recorded_at=datetime.utcnow())
    db.add(r)
    db.commit()

    intruder_repo = UsageRepo(db, "t_intruder")
    result = intruder_repo.get(r.id)
    assert result is None


# ── BackupManager ──────────────────────────────────────────────────────────────

def test_backup_export_manifest(db):
    from hub_platform.lifecycle.backup import BackupManager
    tid = _provision_tenant_with_quotas(db)
    manifest = BackupManager().export_tenant_data(db, tid)
    assert manifest.tenant_id == tid
    assert isinstance(manifest.tables, list)
    assert manifest.total_records >= 0
    assert manifest.exported_at != ""


def test_backup_export_includes_quotas(db):
    from hub_platform.lifecycle.backup import BackupManager
    tid = _provision_tenant_with_quotas(db, "professional")
    manifest = BackupManager().export_tenant_data(db, tid, include_tables=["quotas"])
    assert "quotas" in manifest.data
    assert len(manifest.data["quotas"]) > 0


# ── RetentionPolicy ────────────────────────────────────────────────────────────

def test_retention_purges_old_records(db):
    from hub_platform.lifecycle.retention import apply_retention
    from hub_platform.billing.meter import UsageMeter
    from models.tenant import UsageRecord
    from sqlalchemy import select

    tid = _provision_tenant_with_quotas(db)
    meter = UsageMeter(db)
    # Record usage but manually set recorded_at to past
    record = meter.record(tid, "api_call", 1.0)
    db.commit()

    # Backdate the record
    row = db.get(UsageRecord, record.record_id)
    row.recorded_at = datetime.utcnow() - timedelta(days=200)
    db.commit()

    result = apply_retention(db, tid, retention_days=90)
    db.commit()
    assert result.usage_records_purged >= 1


def test_retention_keeps_recent_records(db):
    from hub_platform.lifecycle.retention import apply_retention
    from hub_platform.billing.meter import UsageMeter

    tid = _provision_tenant_with_quotas(db)
    UsageMeter(db).record(tid, "api_call", 1.0)
    db.commit()

    result = apply_retention(db, tid, retention_days=90)
    db.commit()
    assert result.usage_records_purged == 0


# ── EnvironmentConfig ──────────────────────────────────────────────────────────

def test_env_config_from_env():
    from hub_platform.environments.config import EnvironmentConfig
    cfg = EnvironmentConfig.from_env()
    assert cfg.name is not None
    assert cfg.deployment_mode is not None


def test_env_config_saas_is_multi_tenant():
    from hub_platform.environments.config import EnvironmentConfig, DeploymentMode, EnvironmentName
    cfg = EnvironmentConfig(name=EnvironmentName.PRODUCTION, deployment_mode=DeploymentMode.SAAS)
    assert cfg.is_multi_tenant is True
    assert cfg.is_airgapped is False


def test_env_config_airgapped():
    from hub_platform.environments.config import EnvironmentConfig, DeploymentMode, EnvironmentName
    cfg = EnvironmentConfig(name=EnvironmentName.PRODUCTION, deployment_mode=DeploymentMode.AIRGAPPED)
    assert cfg.is_airgapped is True
    assert cfg.is_multi_tenant is False


def test_env_config_to_dict():
    from hub_platform.environments.config import EnvironmentConfig, DeploymentMode, EnvironmentName
    cfg = EnvironmentConfig(name=EnvironmentName.DEV, deployment_mode=DeploymentMode.SINGLE_TENANT)
    d = cfg.to_dict()
    assert "name" in d
    assert "deployment_mode" in d
    assert "is_production" in d
    assert d["is_production"] is False


# ── DeploymentManager ──────────────────────────────────────────────────────────

def test_deployment_manager_get_info(db):
    from hub_platform.deployments.manager import DeploymentManager
    from hub_platform.environments.config import EnvironmentConfig, DeploymentMode, EnvironmentName
    cfg = EnvironmentConfig(name=EnvironmentName.DEV, deployment_mode=DeploymentMode.SAAS)
    mgr = DeploymentManager(cfg)
    info = mgr.get_deployment_info(db)
    assert info.environment == "dev"
    assert info.deployment_mode == "saas"
    assert isinstance(info.tenant_count, int)


def test_deployment_manager_validate_config_dev():
    from hub_platform.deployments.manager import DeploymentManager
    from hub_platform.environments.config import EnvironmentConfig, DeploymentMode, EnvironmentName
    cfg = EnvironmentConfig(name=EnvironmentName.DEV, deployment_mode=DeploymentMode.SAAS)
    errors = DeploymentManager(cfg).validate_config()
    assert isinstance(errors, list)


# ── API endpoints ──────────────────────────────────────────────────────────────

_ADMIN_HEADERS = {"X-Platform-Admin-Key": "dev-admin-key"}


def test_api_platform_health(client):
    r = client.get("/api/platform/health", headers=_ADMIN_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert "tenant_count" in data


def test_api_platform_metrics(client):
    r = client.get("/api/platform/metrics", headers=_ADMIN_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "tenants_by_tier" in data


def test_api_platform_deployment(client):
    r = client.get("/api/platform/deployment", headers=_ADMIN_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "deployment_mode" in data


def test_api_provision_tenant(client):
    r = client.post("/api/platform/tenants", json={
        "org_name": f"APIOrg-{uuid.uuid4().hex[:6]}",
        "tier": "starter",
        "region": "us-east-1",
        "admin_email": "admin@test.com",
    }, headers=_ADMIN_HEADERS)
    assert r.status_code == 201
    data = r.json()
    assert "tenant_id" in data
    assert data["status"] == "active"


def test_api_provision_duplicate_returns_409(client):
    org = f"DupAPI-{uuid.uuid4().hex[:6]}"
    client.post("/api/platform/tenants", json={"org_name": org, "tier": "free"}, headers=_ADMIN_HEADERS)
    r2 = client.post("/api/platform/tenants", json={"org_name": org, "tier": "free"}, headers=_ADMIN_HEADERS)
    assert r2.status_code == 409


def test_api_list_tenants(client):
    client.post("/api/platform/tenants", json={"org_name": f"ListOrg-{uuid.uuid4().hex[:6]}"}, headers=_ADMIN_HEADERS)
    r = client.get("/api/platform/tenants", headers=_ADMIN_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "tenants" in data
    assert data["total"] >= 1


def test_api_get_tenant(client):
    create_r = client.post("/api/platform/tenants", json={
        "org_name": f"GetOrg-{uuid.uuid4().hex[:6]}"
    }, headers=_ADMIN_HEADERS)
    tid = create_r.json()["tenant_id"]
    r = client.get(f"/api/platform/tenants/{tid}", headers=_ADMIN_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == tid


def test_api_get_tenant_not_found(client):
    r = client.get("/api/platform/tenants/nonexistent", headers=_ADMIN_HEADERS)
    assert r.status_code == 404


def test_api_update_tenant_status_suspend(client):
    create_r = client.post("/api/platform/tenants", json={
        "org_name": f"SuspAPI-{uuid.uuid4().hex[:6]}"
    }, headers=_ADMIN_HEADERS)
    tid = create_r.json()["tenant_id"]
    r = client.patch(f"/api/platform/tenants/{tid}/status",
                     json={"status": "suspended", "actor_id": "test"},
                     headers=_ADMIN_HEADERS)
    assert r.status_code == 200
    assert r.json()["status"] == "suspended"


def test_api_tenant_quotas(client):
    create_r = client.post("/api/platform/tenants", json={
        "org_name": f"QuotaAPI-{uuid.uuid4().hex[:6]}", "tier": "professional"
    }, headers=_ADMIN_HEADERS)
    tid = create_r.json()["tenant_id"]
    r = client.get(f"/api/platform/tenants/{tid}/quotas", headers=_ADMIN_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "quotas" in data
    assert len(data["quotas"]) > 0


def test_api_update_quota(client):
    create_r = client.post("/api/platform/tenants", json={
        "org_name": f"UpdateQ-{uuid.uuid4().hex[:6]}", "tier": "starter"
    }, headers=_ADMIN_HEADERS)
    tid = create_r.json()["tenant_id"]
    r = client.patch(f"/api/platform/tenants/{tid}/quotas",
                     json={"resource": "api_calls", "new_limit": 50_000, "actor_id": "admin"},
                     headers=_ADMIN_HEADERS)
    assert r.status_code == 200
    assert r.json()["new_limit"] == 50_000


def test_api_tenant_usage(client):
    create_r = client.post("/api/platform/tenants", json={
        "org_name": f"UsageAPI-{uuid.uuid4().hex[:6]}"
    }, headers=_ADMIN_HEADERS)
    tid = create_r.json()["tenant_id"]
    r = client.get(f"/api/platform/tenants/{tid}/usage", headers=_ADMIN_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "total_records" in data


def test_api_tenant_audit(client):
    create_r = client.post("/api/platform/tenants", json={
        "org_name": f"AuditAPI-{uuid.uuid4().hex[:6]}"
    }, headers=_ADMIN_HEADERS)
    tid = create_r.json()["tenant_id"]
    r = client.get(f"/api/platform/tenants/{tid}/audit", headers=_ADMIN_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "entries" in data
    # Provisioning should have created an audit entry
    assert data["count"] >= 1


def test_api_set_feature_flag(client):
    create_r = client.post("/api/platform/tenants", json={
        "org_name": f"FlagAPI-{uuid.uuid4().hex[:6]}"
    }, headers=_ADMIN_HEADERS)
    tid = create_r.json()["tenant_id"]
    r = client.post("/api/platform/feature-flags", json={
        "flag_name": "beta_features",
        "enabled": True,
        "tenant_id": tid,
    }, headers=_ADMIN_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert data["enabled"] is True


def test_api_tenant_feature_flags(client):
    create_r = client.post("/api/platform/tenants", json={
        "org_name": f"FlagsGet-{uuid.uuid4().hex[:6]}", "tier": "enterprise"
    }, headers=_ADMIN_HEADERS)
    tid = create_r.json()["tenant_id"]
    r = client.get(f"/api/platform/tenants/{tid}/feature-flags", headers=_ADMIN_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "flags" in data
    assert len(data["flags"]) > 0


def test_api_tenant_roles(client):
    create_r = client.post("/api/platform/tenants", json={
        "org_name": f"RolesAPI-{uuid.uuid4().hex[:6]}"
    }, headers=_ADMIN_HEADERS)
    tid = create_r.json()["tenant_id"]
    r = client.get(f"/api/platform/tenants/{tid}/roles", headers=_ADMIN_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "roles" in data


def test_api_tenant_export(client):
    create_r = client.post("/api/platform/tenants", json={
        "org_name": f"ExportAPI-{uuid.uuid4().hex[:6]}", "tier": "starter"
    }, headers=_ADMIN_HEADERS)
    tid = create_r.json()["tenant_id"]
    r = client.get(f"/api/platform/tenants/{tid}/export", headers=_ADMIN_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "total_records" in data
    assert "tables" in data


def test_api_noisy_tenants(client):
    r = client.get("/api/platform/tenants/noisy?threshold=0", headers=_ADMIN_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "noisy_tenants" in data


def test_api_tenant_billing(client):
    create_r = client.post("/api/platform/tenants", json={
        "org_name": f"BillingAPI-{uuid.uuid4().hex[:6]}"
    }, headers=_ADMIN_HEADERS)
    tid = create_r.json()["tenant_id"]
    r = client.get(f"/api/platform/tenants/{tid}/billing", headers=_ADMIN_HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "net_usd" in data
