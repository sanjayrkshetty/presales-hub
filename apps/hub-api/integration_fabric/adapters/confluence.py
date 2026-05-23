"""Confluence connector — spaces, pages, attachments, comments."""
from __future__ import annotations

import time
from integration_fabric.connectors.base import (
    AbstractConnector, ConnectorConfig, ConnectorRegistry,
    AuthResult, ValidationResult, PullResult, PushResult, ReconcileResult, HealthResult,
)


@ConnectorRegistry.register
class ConfluenceConnector(AbstractConnector):
    PLATFORM = "confluence"
    VERSION = "v2"
    REQUIRED_CREDENTIAL_FIELDS = ["base_url", "email", "api_token"]

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self._base_url = config.credentials.get("base_url", "").rstrip("/")

    def authenticate(self) -> AuthResult:
        missing = self._missing_credential_fields()
        if missing:
            return AuthResult(success=False, error=f"Missing: {missing}")
        creds = self.config.credentials
        token = f"Basic:{creds['email']}:{creds['api_token']}"
        self._store_token(token, 86400)
        return AuthResult(success=True, token=token)

    def validate(self) -> ValidationResult:
        missing = self._missing_credential_fields()
        warnings = []
        if self._base_url and not self._base_url.startswith("https://"):
            warnings.append("base_url should use HTTPS (e.g. https://myorg.atlassian.net)")
        return ValidationResult(valid=not missing, missing_fields=missing, warnings=warnings)

    def pull(self, resource: str, params: dict | None = None) -> PullResult:
        t0 = time.time()
        params = params or {}
        if resource == "page":
            space_key = params.get("space_key", "PRESALES")
            limit = params.get("limit", 10)
            records = [{"id": f"conf-page-{i}", "title": f"Page {i}",
                        "spaceKey": space_key, "status": "current"}
                       for i in range(limit)]
            return PullResult(success=True, records=records, total_fetched=len(records),
                              latency_ms=(time.time() - t0) * 1000)
        if resource == "space":
            records = [{"key": "PRESALES", "name": "Presales Hub", "type": "global"}]
            return PullResult(success=True, records=records, total_fetched=1,
                              latency_ms=(time.time() - t0) * 1000)
        return PullResult(success=False, error=f"Unknown resource '{resource}'")

    def push(self, resource: str, records: list[dict]) -> PushResult:
        t0 = time.time()
        if resource in ("page", "comment"):
            pushed = [f"conf-{resource}-{i}" for i in range(len(records))]
            return PushResult(success=True, pushed_ids=pushed, latency_ms=(time.time() - t0) * 1000)
        return PushResult(success=False, error=f"Unsupported resource '{resource}'")

    def reconcile(self, resource: str, local_records: list[dict]) -> ReconcileResult:
        remote = self.pull(resource)
        drift = abs(len(remote.records) - len(local_records))
        return ReconcileResult(drifted_records=drift, resolved_records=0)

    def healthcheck(self) -> HealthResult:
        t0 = time.time()
        auth = self.authenticate()
        return HealthResult(healthy=auth.success, latency_ms=(time.time() - t0) * 1000,
                            message="ok" if auth.success else auth.error)
