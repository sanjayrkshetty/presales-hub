"""
Per-tenant, per-connector token-bucket rate limiter.

Thread-safe in-process implementation. For multi-process deployments,
replace _buckets with Redis-backed counters.
"""
from __future__ import annotations

import time
import threading
from dataclasses import dataclass, field
from typing import Optional

from integration_fabric import config as cfg

_PLATFORM_LIMITS: dict[str, int] = {
    "salesforce": cfg.SALESFORCE_RATE_LIMIT_RPM,
    "hubspot": cfg.HUBSPOT_RATE_LIMIT_RPM,
    "jira": cfg.JIRA_RATE_LIMIT_RPM,
    "servicenow": cfg.SERVICENOW_RATE_LIMIT_RPM,
    "slack": cfg.SLACK_RATE_LIMIT_RPM,
    "teams": cfg.TEAMS_RATE_LIMIT_RPM,
    "outlook": cfg.OUTLOOK_RATE_LIMIT_RPM,
    "gmail": cfg.GMAIL_RATE_LIMIT_RPM,
    "sharepoint": cfg.SHAREPOINT_RATE_LIMIT_RPM,
    "confluence": cfg.CONFLUENCE_RATE_LIMIT_RPM,
    "gdrive": cfg.GDRIVE_RATE_LIMIT_RPM,
    "webhook": cfg.WEBHOOK_RATE_LIMIT_RPM,
}


@dataclass
class TokenBucket:
    capacity: int           # max tokens (= RPM)
    tokens: float = 0.0
    last_refill: float = field(default_factory=time.time)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self):
        self.tokens = float(self.capacity)

    def _refill(self) -> None:
        now = time.time()
        elapsed = now - self.last_refill
        refill = elapsed * (self.capacity / 60.0)
        self.tokens = min(self.capacity, self.tokens + refill)
        self.last_refill = now

    def consume(self, count: int = 1) -> bool:
        with self.lock:
            self._refill()
            if self.tokens >= count:
                self.tokens -= count
                return True
            return False

    def remaining(self) -> float:
        with self.lock:
            self._refill()
            return self.tokens


class RateLimiter:
    """Singleton rate limiter keyed by (tenant_id, platform)."""
    _buckets: dict[str, TokenBucket] = {}
    _lock = threading.Lock()

    @classmethod
    def _key(cls, tenant_id: str, platform: str) -> str:
        return f"{tenant_id}:{platform}"

    @classmethod
    def _get_bucket(cls, tenant_id: str, platform: str) -> TokenBucket:
        key = cls._key(tenant_id, platform)
        if key not in cls._buckets:
            with cls._lock:
                if key not in cls._buckets:
                    rpm = _PLATFORM_LIMITS.get(platform, cfg.DEFAULT_RATE_LIMIT_RPM)
                    cls._buckets[key] = TokenBucket(capacity=rpm)
        return cls._buckets[key]

    @classmethod
    def check(cls, tenant_id: str, platform: str, count: int = 1) -> bool:
        return cls._get_bucket(tenant_id, platform).consume(count)

    @classmethod
    def remaining(cls, tenant_id: str, platform: str) -> float:
        return cls._get_bucket(tenant_id, platform).remaining()

    @classmethod
    def reset(cls, tenant_id: str, platform: str) -> None:
        key = cls._key(tenant_id, platform)
        cls._buckets.pop(key, None)

    @classmethod
    def status(cls, tenant_id: str) -> dict:
        return {
            k.split(":", 1)[1]: round(v.remaining(), 1)
            for k, v in cls._buckets.items()
            if k.startswith(f"{tenant_id}:")
        }


_limiter = RateLimiter()
