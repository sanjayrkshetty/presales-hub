"""Tenant domain enumerations and constants."""
from __future__ import annotations

from enum import Enum


class TenantTier(str, Enum):
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"

    @property
    def rank(self) -> int:
        return {"free": 0, "starter": 1, "professional": 2, "enterprise": 3}[self.value]

    def meets_minimum(self, minimum: "TenantTier") -> bool:
        return self.rank >= minimum.rank


class TenantStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"
    DELETED = "deleted"
    PROVISIONING = "provisioning"


class TenantRegion(str, Enum):
    US_EAST = "us-east-1"
    US_WEST = "us-west-2"
    EU_WEST = "eu-west-1"
    EU_CENTRAL = "eu-central-1"
    AP_SOUTH = "ap-south-1"
    AP_SOUTHEAST = "ap-southeast-1"


TIER_DEFAULTS: dict[TenantTier, dict] = {
    TenantTier.FREE: {
        "billing_plan": "free",
        "retention_days": 30,
        "max_users": 3,
    },
    TenantTier.STARTER: {
        "billing_plan": "starter_monthly",
        "retention_days": 90,
        "max_users": 10,
    },
    TenantTier.PROFESSIONAL: {
        "billing_plan": "professional_monthly",
        "retention_days": 365,
        "max_users": 50,
    },
    TenantTier.ENTERPRISE: {
        "billing_plan": "enterprise_annual",
        "retention_days": 2555,  # 7 years
        "max_users": -1,          # unlimited
    },
}
