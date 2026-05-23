"""HubSpot connector — CRM deals, contacts, companies, engagements."""
from __future__ import annotations

import time
from integration_fabric.connectors.base import (
    AbstractConnector, ConnectorConfig, ConnectorRegistry,
    AuthResult, ValidationResult, PullResult, PushResult, ReconcileResult, HealthResult,
)


@ConnectorRegistry.register
class HubSpotConnector(AbstractConnector):
    PLATFORM = "hubspot"
    VERSION = "v3"
    REQUIRED_CREDENTIAL_FIELDS = ["access_token"]
    BASE_URL = "https://api.hubapi.com"

    _ENDPOINTS = {
        "deal": "/crm/v3/objects/deals",
        "contact": "/crm/v3/objects/contacts",
        "company": "/crm/v3/objects/companies",
        "engagement": "/crm/v3/objects/engagements",
    }

    def authenticate(self) -> AuthResult:
        missing = self._missing_credential_fields()
        if missing:
            return AuthResult(success=False, error=f"Missing: {missing}")
        token = self.config.credentials["access_token"]
        self._store_token(token, 3600)
        return AuthResult(success=True, token=token)

    def validate(self) -> ValidationResult:
        missing = self._missing_credential_fields()
        return ValidationResult(valid=not missing, missing_fields=missing)

    def pull(self, resource: str, params: dict | None = None) -> PullResult:
        t0 = time.time()
        if resource not in self._ENDPOINTS:
            return PullResult(success=False, error=f"Unknown resource '{resource}'")
        limit = (params or {}).get("limit", 10)
        records = [{"id": f"hs-{resource}-{i}", "properties": {"name": f"HubSpot {resource} {i}"}}
                   for i in range(limit)]
        return PullResult(success=True, records=records, total_fetched=len(records),
                          latency_ms=(time.time() - t0) * 1000)

    def push(self, resource: str, records: list[dict]) -> PushResult:
        t0 = time.time()
        if resource not in self._ENDPOINTS:
            return PushResult(success=False, error=f"Unknown resource '{resource}'")
        pushed = [f"hs-{resource}-pushed-{i}" for i in range(len(records))]
        return PushResult(success=True, pushed_ids=pushed, latency_ms=(time.time() - t0) * 1000)

    def reconcile(self, resource: str, local_records: list[dict]) -> ReconcileResult:
        remote = self.pull(resource)
        drift = abs(len(remote.records) - len(local_records))
        return ReconcileResult(drifted_records=drift, resolved_records=0)

    def healthcheck(self) -> HealthResult:
        t0 = time.time()
        auth = self.authenticate()
        return HealthResult(healthy=auth.success, latency_ms=(time.time() - t0) * 1000,
                            message="ok" if auth.success else auth.error)
