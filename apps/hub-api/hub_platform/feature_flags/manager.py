"""
Feature flag manager.

Checks:
1. Emergency disable list
2. Tenant-specific DB override
3. Tier-gating (tier must meet minimum)
4. Default for tier
5. Global platform flag (no tenant_id)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from hub_platform.feature_flags.defaults import (
    DEFAULT_FLAGS_BY_TIER,
    EMERGENCY_DISABLED_FLAGS,
    FLAG_TIER_MINIMUMS,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@dataclass
class FlagResult:
    flag_name: str
    enabled: bool
    source: str      # "emergency_disable"|"tenant_override"|"tier_gate"|"tier_default"|"global"|"not_found"
    tenant_id: Optional[str] = None


class FeatureFlagManager:
    def __init__(self, db: "Session"):
        self.db = db

    def is_enabled(
        self,
        flag_name: str,
        tenant_id: Optional[str] = None,
        tier: Optional[str] = None,
    ) -> bool:
        return self.evaluate(flag_name, tenant_id=tenant_id, tier=tier).enabled

    def evaluate(
        self,
        flag_name: str,
        tenant_id: Optional[str] = None,
        tier: Optional[str] = None,
    ) -> FlagResult:
        # 1. Emergency kill-switch
        if flag_name in EMERGENCY_DISABLED_FLAGS:
            return FlagResult(flag_name=flag_name, enabled=False, source="emergency_disable", tenant_id=tenant_id)

        # 2. Resolve tier from DB if not supplied
        if tier is None and tenant_id:
            tier = self._get_tier(tenant_id)

        # 3. Tenant DB override — explicit override beats tier gate
        if tenant_id:
            db_flag = self._get_db_flag(flag_name, tenant_id)
            if db_flag is not None:
                return FlagResult(flag_name=flag_name, enabled=db_flag.enabled, source="tenant_override", tenant_id=tenant_id)

        # 4. Tier gate — flag requires higher tier
        min_tier = FLAG_TIER_MINIMUMS.get(flag_name)
        if min_tier and tier:
            from hub_platform.tenants.schemas import TenantTier
            try:
                if not TenantTier(tier).meets_minimum(TenantTier(min_tier)):
                    return FlagResult(flag_name=flag_name, enabled=False, source="tier_gate", tenant_id=tenant_id)
            except ValueError:
                pass  # Unknown tier — fall through

        # 5. Global platform flag (tenant_id = NULL)
        global_flag = self._get_db_flag(flag_name, tenant_id=None)
        if global_flag is not None:
            return FlagResult(flag_name=flag_name, enabled=global_flag.enabled, source="global")

        # 6. Tier default
        if tier:
            tier_flags = DEFAULT_FLAGS_BY_TIER.get(tier, {})
            if flag_name in tier_flags:
                return FlagResult(flag_name=flag_name, enabled=tier_flags[flag_name], source="tier_default", tenant_id=tenant_id)

        return FlagResult(flag_name=flag_name, enabled=False, source="not_found", tenant_id=tenant_id)

    def set_flag(
        self,
        flag_name: str,
        enabled: bool,
        tenant_id: Optional[str] = None,
        rollout_percent: int = 100,
        description: str = "",
    ) -> "FeatureFlag":
        import uuid
        from sqlalchemy import select
        from models.tenant import FeatureFlag

        existing = self._get_db_flag(flag_name, tenant_id)
        if existing:
            existing.enabled = enabled
            existing.rollout_percent = rollout_percent
            existing.updated_at = datetime.utcnow()
            self.db.flush()
            return existing

        flag = FeatureFlag(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            flag_name=flag_name,
            enabled=enabled,
            rollout_percent=rollout_percent,
            description=description,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        self.db.add(flag)
        self.db.flush()
        return flag

    def get_tenant_flags(self, tenant_id: str, tier: Optional[str] = None) -> dict[str, bool]:
        if tier is None:
            tier = self._get_tier(tenant_id) or "starter"
        defaults = DEFAULT_FLAGS_BY_TIER.get(tier, {})
        result = dict(defaults)

        # Apply DB overrides
        from sqlalchemy import select
        from models.tenant import FeatureFlag
        db_flags = list(
            self.db.scalars(
                select(FeatureFlag).where(FeatureFlag.tenant_id == tenant_id)
            ).all()
        )
        for f in db_flags:
            result[f.flag_name] = f.enabled

        # Apply emergency disables
        for name in EMERGENCY_DISABLED_FLAGS:
            result[name] = False

        return result

    def _get_tier(self, tenant_id: str) -> Optional[str]:
        from models.tenant import Tenant
        t = self.db.get(Tenant, tenant_id)
        return t.tier if t else None

    def _get_db_flag(self, flag_name: str, tenant_id: Optional[str]) -> Optional["FeatureFlag"]:
        from sqlalchemy import select
        from models.tenant import FeatureFlag

        q = select(FeatureFlag).where(FeatureFlag.flag_name == flag_name)
        if tenant_id is None:
            q = q.where(FeatureFlag.tenant_id.is_(None))
        else:
            q = q.where(FeatureFlag.tenant_id == tenant_id)
        return self.db.scalars(q).first()
