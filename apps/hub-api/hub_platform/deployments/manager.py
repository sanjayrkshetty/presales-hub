"""
Deployment manager — validates and describes active deployment configuration.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from hub_platform.environments.config import EnvironmentConfig, DeploymentMode, current_env

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@dataclass
class DeploymentInfo:
    environment: str
    deployment_mode: str
    region: str
    tenant_count: int
    active_tenant_count: int
    feature_summary: dict = field(default_factory=dict)
    health: str = "ok"
    warnings: list[str] = field(default_factory=list)


class DeploymentManager:
    def __init__(self, config: EnvironmentConfig | None = None):
        self.config = config or current_env

    def get_deployment_info(self, db: "Session") -> DeploymentInfo:
        from sqlalchemy import select, func
        from models.tenant import Tenant

        total = db.scalar(select(func.count()).select_from(Tenant)) or 0
        active = db.scalar(
            select(func.count()).select_from(Tenant).where(Tenant.status == "active")
        ) or 0

        warnings: list[str] = []
        if self.config.max_tenants != -1 and active >= self.config.max_tenants * 0.9:
            warnings.append(f"Approaching max tenant limit ({active}/{self.config.max_tenants})")
        if self.config.is_production and self.config.debug_mode:
            warnings.append("Debug mode is ON in production — security risk")

        return DeploymentInfo(
            environment=self.config.name.value,
            deployment_mode=self.config.deployment_mode.value,
            region=self.config.region,
            tenant_count=total,
            active_tenant_count=active,
            feature_summary=self.config.to_dict(),
            health="degraded" if warnings else "ok",
            warnings=warnings,
        )

    def validate_config(self) -> list[str]:
        """Return list of config validation errors. Empty = valid."""
        errors: list[str] = []
        if self.config.is_production and self.config.debug_mode:
            errors.append("debug_mode must be False in production")
        if self.config.is_multi_tenant and not self.config.db_url and self.config.is_production:
            errors.append("DATABASE_URL required for multi-tenant production deployment")
        if self.config.is_airgapped and self.config.external_network:
            errors.append("external_network must be False for airgapped deployment")
        return errors
