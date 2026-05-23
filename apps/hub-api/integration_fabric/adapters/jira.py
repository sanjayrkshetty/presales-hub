"""Jira connector — issues, projects, workflows, transitions."""
from __future__ import annotations

import time
from integration_fabric.connectors.base import (
    AbstractConnector, ConnectorConfig, ConnectorRegistry,
    AuthResult, ValidationResult, PullResult, PushResult, ReconcileResult, HealthResult,
)


@ConnectorRegistry.register
class JiraConnector(AbstractConnector):
    PLATFORM = "jira"
    VERSION = "3"
    REQUIRED_CREDENTIAL_FIELDS = ["base_url", "email", "api_token"]

    _JQL_TEMPLATES = {
        "issue": "project IS NOT EMPTY ORDER BY updated DESC",
        "project": "",
        "transition": "",
    }

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self._base_url = config.credentials.get("base_url", "").rstrip("/")

    def authenticate(self) -> AuthResult:
        missing = self._missing_credential_fields()
        if missing:
            return AuthResult(success=False, error=f"Missing: {missing}")
        token = f"Basic:{self.config.credentials['email']}:{self.config.credentials['api_token']}"
        self._store_token(token, 86400)
        return AuthResult(success=True, token=token)

    def validate(self) -> ValidationResult:
        missing = self._missing_credential_fields()
        warnings = []
        base = self.config.credentials.get("base_url", "")
        if base and not base.startswith("https://"):
            warnings.append("base_url should use HTTPS")
        return ValidationResult(valid=not missing, missing_fields=missing, warnings=warnings)

    def pull(self, resource: str, params: dict | None = None) -> PullResult:
        t0 = time.time()
        params = params or {}
        if resource == "issue":
            jql = params.get("jql", self._JQL_TEMPLATES["issue"])
            max_results = params.get("limit", 50)
            records = [{"id": f"PROJ-{i}", "key": f"PROJ-{i}", "summary": f"Jira issue {i}", "status": "Open"}
                       for i in range(1, min(max_results + 1, 6))]
            return PullResult(success=True, records=records, total_fetched=len(records),
                              latency_ms=(time.time() - t0) * 1000)
        elif resource == "project":
            records = [{"id": "10000", "key": "PROJ", "name": "Presales Project"}]
            return PullResult(success=True, records=records, total_fetched=1,
                              latency_ms=(time.time() - t0) * 1000)
        return PullResult(success=False, error=f"Unknown resource '{resource}'")

    def push(self, resource: str, records: list[dict]) -> PushResult:
        t0 = time.time()
        if resource == "issue":
            pushed = [f"PROJ-{1000 + i}" for i in range(len(records))]
            return PushResult(success=True, pushed_ids=pushed, latency_ms=(time.time() - t0) * 1000)
        if resource == "transition":
            pushed = [r.get("issue_id", f"issue-{i}") for i, r in enumerate(records)]
            return PushResult(success=True, pushed_ids=pushed, latency_ms=(time.time() - t0) * 1000)
        return PushResult(success=False, error=f"Unknown resource '{resource}'")

    def reconcile(self, resource: str, local_records: list[dict]) -> ReconcileResult:
        remote = self.pull(resource)
        remote_keys = {r.get("key") for r in remote.records}
        local_keys = {r.get("jira_key") for r in local_records if r.get("jira_key")}
        drift = len(remote_keys.symmetric_difference(local_keys))
        return ReconcileResult(drifted_records=drift, resolved_records=0)

    def healthcheck(self) -> HealthResult:
        t0 = time.time()
        auth = self.authenticate()
        return HealthResult(healthy=auth.success, latency_ms=(time.time() - t0) * 1000,
                            message="ok" if auth.success else auth.error)
