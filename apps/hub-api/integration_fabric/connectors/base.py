"""
Abstract base connector — every integration adapter implements this contract.

Methods:
  authenticate() → AuthResult   acquire/refresh credentials
  validate()     → ValidationResult   verify connector config is complete
  pull()         → PullResult          fetch data from remote system
  push()         → PushResult          write data to remote system
  reconcile()    → ReconcileResult     diff + resolve state with remote
  healthcheck()  → HealthResult        ping remote + report latency
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class AuthResult:
    success: bool
    token: Optional[str] = None
    expires_at: Optional[float] = None   # unix timestamp
    error: Optional[str] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class ValidationResult:
    valid: bool
    missing_fields: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class PullResult:
    success: bool
    records: list[dict] = field(default_factory=list)
    total_fetched: int = 0
    cursor: Optional[str] = None        # pagination cursor for next page
    error: Optional[str] = None
    latency_ms: float = 0.0


@dataclass
class PushResult:
    success: bool
    pushed_ids: list[str] = field(default_factory=list)
    failed_ids: list[str] = field(default_factory=list)
    error: Optional[str] = None
    latency_ms: float = 0.0


@dataclass
class ReconcileResult:
    drifted_records: int = 0
    resolved_records: int = 0
    conflicts: list[dict] = field(default_factory=list)
    error: Optional[str] = None
    strategy_applied: str = "last_write_wins"


@dataclass
class HealthResult:
    healthy: bool
    latency_ms: float = 0.0
    status_code: Optional[int] = None
    message: str = "ok"
    checked_at: float = field(default_factory=time.time)


class ConnectorConfig:
    """Holds connector-specific configuration dict."""
    def __init__(self, platform: str, tenant_id: str, credentials: dict, settings: dict | None = None):
        self.platform = platform
        self.tenant_id = tenant_id
        self.credentials = credentials      # encrypted at rest, decrypted before use
        self.settings = settings or {}


class AbstractConnector(ABC):
    """
    Every integration adapter must subclass this.
    Implementations are platform-specific; the contract is fixed.
    """
    PLATFORM: str = ""
    VERSION: str = "1.0"
    REQUIRED_CREDENTIAL_FIELDS: list[str] = []

    def __init__(self, config: ConnectorConfig):
        self.config = config
        self._auth_token: Optional[str] = None
        self._token_expires_at: float = 0.0

    # ── Mandatory interface ────────────────────────────────────────────────────

    @abstractmethod
    def authenticate(self) -> AuthResult:
        """Acquire or refresh access credentials."""

    @abstractmethod
    def validate(self) -> ValidationResult:
        """Check that all required config/credentials are present."""

    @abstractmethod
    def pull(self, resource: str, params: dict | None = None) -> PullResult:
        """Fetch records from the remote system."""

    @abstractmethod
    def push(self, resource: str, records: list[dict]) -> PushResult:
        """Write/update records in the remote system."""

    @abstractmethod
    def reconcile(self, resource: str, local_records: list[dict]) -> ReconcileResult:
        """Compare local vs remote state and resolve divergence."""

    @abstractmethod
    def healthcheck(self) -> HealthResult:
        """Ping remote endpoint and report health + latency."""

    # ── Shared helpers ─────────────────────────────────────────────────────────

    def _missing_credential_fields(self) -> list[str]:
        return [f for f in self.REQUIRED_CREDENTIAL_FIELDS if not self.config.credentials.get(f)]

    def _is_token_valid(self) -> bool:
        if not self._auth_token:
            return False
        from integration_fabric.config import OAUTH2_TOKEN_EXPIRY_BUFFER_S
        return time.time() < self._token_expires_at - OAUTH2_TOKEN_EXPIRY_BUFFER_S

    def _store_token(self, token: str, expires_in_s: float) -> None:
        self._auth_token = token
        self._token_expires_at = time.time() + expires_in_s

    def to_info(self) -> dict:
        return {
            "platform": self.PLATFORM,
            "version": self.VERSION,
            "tenant_id": self.config.tenant_id,
            "token_valid": self._is_token_valid(),
        }


class ConnectorRegistry:
    """Singleton registry of connector classes by platform name."""
    _registry: dict[str, type[AbstractConnector]] = {}

    @classmethod
    def register(cls, connector_cls: type[AbstractConnector]) -> type[AbstractConnector]:
        cls._registry[connector_cls.PLATFORM] = connector_cls
        return connector_cls

    @classmethod
    def get(cls, platform: str) -> type[AbstractConnector]:
        c = cls._registry.get(platform)
        if c is None:
            raise ValueError(f"No connector registered for platform '{platform}'")
        return c

    @classmethod
    def list_platforms(cls) -> list[str]:
        return sorted(cls._registry.keys())

    @classmethod
    def instantiate(cls, platform: str, config: ConnectorConfig) -> AbstractConnector:
        return cls.get(platform)(config)
