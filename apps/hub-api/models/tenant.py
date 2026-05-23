"""
Multi-tenant platform data models.

All platform entities are logically isolated per tenant.
Physical isolation (separate DB per tenant) is a future migration path.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Boolean, Float, Integer, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.database import Base


class Tenant(Base):
    """Core tenant entity — one row per organisation."""
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    org_name: Mapped[str] = mapped_column(String, nullable=False)
    tier: Mapped[str] = mapped_column(String, default="starter")       # free|starter|professional|enterprise
    region: Mapped[str] = mapped_column(String, default="us-east-1")
    status: Mapped[str] = mapped_column(String, default="active")      # active|suspended|archived|deleted
    quotas: Mapped[dict] = mapped_column(JSON, default=dict)
    feature_flags: Mapped[dict] = mapped_column(JSON, default=dict)
    retention_policy: Mapped[dict] = mapped_column(JSON, default=dict)
    billing_plan: Mapped[str] = mapped_column(String, default="")
    admin_email: Mapped[str] = mapped_column(String, default="")
    extra_data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TenantQuota(Base):
    """Per-tenant resource quota tracking."""
    __tablename__ = "tenant_quotas"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String, nullable=False)
    resource: Mapped[str] = mapped_column(String, nullable=False)      # api_calls|tokens|workflows|storage_mb|agents|simulations|connectors
    limit_value: Mapped[int] = mapped_column(Integer, default=0)       # -1 = unlimited
    current_usage: Mapped[int] = mapped_column(Integer, default=0)
    period: Mapped[str] = mapped_column(String, default="monthly")     # hourly|daily|monthly|total
    reset_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FeatureFlag(Base):
    """Tenant-scoped or global feature flag."""
    __tablename__ = "feature_flags"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # None = platform-global flag
    flag_name: Mapped[str] = mapped_column(String, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    rollout_percent: Mapped[int] = mapped_column(Integer, default=100)         # 0–100
    tier_minimum: Mapped[str] = mapped_column(String, default="free")          # minimum tier to access flag
    description: Mapped[str] = mapped_column(Text, default="")
    extra_data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class UsageRecord(Base):
    """Granular usage event — feeds billing and quota systems."""
    __tablename__ = "usage_records"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String, nullable=False)
    resource_type: Mapped[str] = mapped_column(String, nullable=False)  # api_call|token|workflow|storage_mb|agent_execution|simulation|connector_sync
    quantity: Mapped[float] = mapped_column(Float, default=1.0)
    endpoint: Mapped[str] = mapped_column(String, default="")
    actor_id: Mapped[str] = mapped_column(String, default="")
    extra_data: Mapped[dict] = mapped_column(JSON, default=dict)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BillingEvent(Base):
    """Billing state change or charge event."""
    __tablename__ = "billing_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String, nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)   # usage_charge|plan_change|overage|credit|refund|quota_breach
    amount_usd: Mapped[float] = mapped_column(Float, default=0.0)
    description: Mapped[str] = mapped_column(String, default="")
    resource_type: Mapped[str] = mapped_column(String, default="")
    quantity: Mapped[float] = mapped_column(Float, default=0.0)
    extra_data: Mapped[dict] = mapped_column(JSON, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TenantAuditLog(Base):
    """Immutable audit trail for all platform admin and tenant-affecting actions."""
    __tablename__ = "tenant_audit_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String, nullable=False)
    actor_id: Mapped[str] = mapped_column(String, default="system")
    action: Mapped[str] = mapped_column(String, nullable=False)          # tenant.provision|tenant.suspend|quota.update|flag.change|iam.role_assign|etc.
    resource_type: Mapped[str] = mapped_column(String, default="")
    resource_id: Mapped[str] = mapped_column(String, default="")
    before_state: Mapped[dict] = mapped_column(JSON, default=dict)
    after_state: Mapped[dict] = mapped_column(JSON, default=dict)
    ip_address: Mapped[str] = mapped_column(String, default="")
    status: Mapped[str] = mapped_column(String, default="success")      # success|failed|blocked
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TenantRole(Base):
    """Custom RBAC roles scoped to a tenant."""
    __tablename__ = "tenant_roles"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String, nullable=False)
    role_name: Mapped[str] = mapped_column(String, nullable=False)
    permissions: Mapped[list] = mapped_column(JSON, default=list)       # list of permission strings
    inherits_from: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # parent role name
    description: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TenantRoleAssignment(Base):
    """User → role assignment within a tenant."""
    __tablename__ = "tenant_role_assignments"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    role_name: Mapped[str] = mapped_column(String, nullable=False)
    granted_by: Mapped[str] = mapped_column(String, default="system")
    granted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
