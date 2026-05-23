"""ServiceNow connector — incidents, change requests, CMDB records."""
from __future__ import annotations

import time
from integration_fabric.connectors.base import (
    AbstractConnector, ConnectorConfig, ConnectorRegistry,
    AuthResult, ValidationResult, PullResult, PushResult, ReconcileResult, HealthResult,
)


@ConnectorRegistry.register
class ServiceNowConnector(AbstractConnector):
    PLATFORM = "servicenow"
    VERSION = "v2"
    REQUIRED_CREDENTIAL_FIELDS = ["instance", "username", "password"]

    _TABLES = {
        "incident": "incident",
        "change_request": "change_request",
        "cmdb_ci": "cmdb_ci",
        "task": "task",
    }

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self._instance = config.credentials.get("instance", "")
        self._base = f"https://{self._instance}.service-now.com/api/now"

    def authenticate(self) -> AuthResult:
        missing = self._missing_credential_fields()
        if missing:
            return AuthResult(success=False, error=f"Missing: {missing}")
        creds = self.config.credentials
        token = f"BasicAuth:{creds['username']}"
        self._store_token(token, 86400)
        return AuthResult(success=True, token=token)

    def validate(self) -> ValidationResult:
        missing = self._missing_credential_fields()
        warnings = []
        if not self._instance:
            warnings.append("instance field should be your ServiceNow subdomain (e.g. 'mycompany')")
        return ValidationResult(valid=not missing, missing_fields=missing, warnings=warnings)

    def pull(self, resource: str, params: dict | None = None) -> PullResult:
        t0 = time.time()
        table = self._TABLES.get(resource)
        if not table:
            return PullResult(success=False, error=f"Unknown resource '{resource}'")
        limit = (params or {}).get("limit", 10)
        records = [{"sys_id": f"snow-{resource}-{i}", "number": f"INC{1000 + i:04d}", "state": "Open"}
                   for i in range(limit)]
        return PullResult(success=True, records=records, total_fetched=len(records),
                          latency_ms=(time.time() - t0) * 1000)

    def push(self, resource: str, records: list[dict]) -> PushResult:
        t0 = time.time()
        if resource not in self._TABLES:
            return PushResult(success=False, error=f"Unknown resource '{resource}'")
        pushed = [f"snow-{resource}-created-{i}" for i in range(len(records))]
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
