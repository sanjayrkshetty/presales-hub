"""
Deployment mode and environment configuration.

Supports 5 deployment topologies:
1. single_tenant    — single org, on-prem or cloud
2. saas             — multi-tenant SaaS
3. airgapped        — no external network, fully on-prem
4. onprem           — on-premises with optional external connectivity
5. hybrid           — mix of on-prem and cloud components
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class DeploymentMode(str, Enum):
    SINGLE_TENANT = "single_tenant"
    SAAS = "saas"
    AIRGAPPED = "airgapped"
    ONPREM = "onprem"
    HYBRID = "hybrid"


class EnvironmentName(str, Enum):
    DEV = "dev"
    STAGING = "staging"
    PRODUCTION = "production"
    SANDBOX = "sandbox"


@dataclass
class EnvironmentConfig:
    name: EnvironmentName
    deployment_mode: DeploymentMode
    region: str = "us-east-1"
    # Feature overrides per environment
    llm_provider: str = "mock"          # mock | anthropic | azure_openai
    telemetry_enabled: bool = True
    debug_mode: bool = False
    allow_cross_tenant_admin: bool = False
    max_tenants: int = -1               # -1 = unlimited
    # Network / auth
    base_url: str = ""
    cors_origins: list[str] = field(default_factory=list)
    # Storage
    db_url: str = ""
    redis_url: str = ""
    # Secrets
    secret_backend: str = "env"         # env | vault | aws_secrets
    # AI
    ai_enabled: bool = True
    external_network: bool = True

    @classmethod
    def from_env(cls) -> "EnvironmentConfig":
        raw_env = os.environ.get("HUB_ENV", "dev").lower()
        raw_mode = os.environ.get("HUB_DEPLOYMENT_MODE", "saas").lower()
        try:
            env_name = EnvironmentName(raw_env)
        except ValueError:
            env_name = EnvironmentName.DEV
        try:
            mode = DeploymentMode(raw_mode)
        except ValueError:
            mode = DeploymentMode.SAAS
        return cls(
            name=env_name,
            deployment_mode=mode,
            llm_provider=os.environ.get("LLM_PROVIDER", "mock"),
            db_url=os.environ.get("DATABASE_URL", ""),
            redis_url=os.environ.get("REDIS_URL", ""),
            debug_mode=os.environ.get("DEBUG", "").lower() in ("1", "true"),
            telemetry_enabled=os.environ.get("TELEMETRY_ENABLED", "true").lower() != "false",
            external_network=mode not in (DeploymentMode.AIRGAPPED,),
        )

    @property
    def is_production(self) -> bool:
        return self.name == EnvironmentName.PRODUCTION

    @property
    def is_airgapped(self) -> bool:
        return self.deployment_mode == DeploymentMode.AIRGAPPED

    @property
    def is_multi_tenant(self) -> bool:
        return self.deployment_mode == DeploymentMode.SAAS

    def to_dict(self) -> dict:
        return {
            "name": self.name.value,
            "deployment_mode": self.deployment_mode.value,
            "region": self.region,
            "llm_provider": self.llm_provider,
            "telemetry_enabled": self.telemetry_enabled,
            "debug_mode": self.debug_mode,
            "allow_cross_tenant_admin": self.allow_cross_tenant_admin,
            "max_tenants": self.max_tenants,
            "secret_backend": self.secret_backend,
            "ai_enabled": self.ai_enabled,
            "external_network": self.external_network,
            "is_production": self.is_production,
            "is_airgapped": self.is_airgapped,
            "is_multi_tenant": self.is_multi_tenant,
        }


# Module-level singleton loaded from environment
current_env: EnvironmentConfig = EnvironmentConfig.from_env()
