"""
Salesforce connector.

Authenticates via OAuth2 client credentials (Connected App).
Resources: opportunity, account, contact, lead, task.
"""
from __future__ import annotations

import time
from integration_fabric.connectors.base import (
    AbstractConnector, ConnectorConfig, ConnectorRegistry,
    AuthResult, ValidationResult, PullResult, PushResult, ReconcileResult, HealthResult,
)
from integration_fabric.auth.oauth2 import OAuth2Client, OAuth2Config


@ConnectorRegistry.register
class SalesforceConnector(AbstractConnector):
    PLATFORM = "salesforce"
    VERSION = "59.0"
    REQUIRED_CREDENTIAL_FIELDS = ["client_id", "client_secret", "instance_url"]

    _RESOURCE_OBJECTS = {
        "opportunity": "Opportunity",
        "account": "Account",
        "contact": "Contact",
        "lead": "Lead",
        "task": "Task",
    }

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        creds = config.credentials
        self._instance_url = creds.get("instance_url", "")
        self._oauth = OAuth2Client(OAuth2Config(
            client_id=creds.get("client_id", ""),
            client_secret=creds.get("client_secret", ""),
            token_url=f"{self._instance_url}/services/oauth2/token",
            scopes=["api", "refresh_token"],
        ))

    def authenticate(self) -> AuthResult:
        missing = self._missing_credential_fields()
        if missing:
            return AuthResult(success=False, error=f"Missing credentials: {missing}")
        try:
            tok = self._oauth.client_credentials()
            self._store_token(tok.access_token, tok.expires_in)
            return AuthResult(success=True, token=tok.access_token, expires_at=self._token_expires_at)
        except Exception as exc:
            return AuthResult(success=False, error=str(exc))

    def validate(self) -> ValidationResult:
        missing = self._missing_credential_fields()
        warnings = []
        if not self._instance_url.startswith("https://"):
            warnings.append("instance_url should begin with https://")
        return ValidationResult(valid=not missing, missing_fields=missing, warnings=warnings)

    def pull(self, resource: str, params: dict | None = None) -> PullResult:
        t0 = time.time()
        sf_object = self._RESOURCE_OBJECTS.get(resource)
        if not sf_object:
            return PullResult(success=False, error=f"Unknown resource '{resource}'")
        params = params or {}
        limit = params.get("limit", 100)
        soql = params.get("soql", f"SELECT Id, Name FROM {sf_object} LIMIT {limit}")
        records = [{"id": f"sf-{i:04d}", "name": f"{sf_object} {i}", "_soql": soql} for i in range(3)]
        return PullResult(success=True, records=records, total_fetched=len(records),
                          latency_ms=(time.time() - t0) * 1000)

    def push(self, resource: str, records: list[dict]) -> PushResult:
        t0 = time.time()
        sf_object = self._RESOURCE_OBJECTS.get(resource)
        if not sf_object:
            return PushResult(success=False, error=f"Unknown resource '{resource}'")
        pushed = [f"sf-pushed-{i}" for i in range(len(records))]
        return PushResult(success=True, pushed_ids=pushed, latency_ms=(time.time() - t0) * 1000)

    def reconcile(self, resource: str, local_records: list[dict]) -> ReconcileResult:
        remote = self.pull(resource)
        remote_ids = {r["id"] for r in remote.records}
        local_ids = {r.get("remote_id") for r in local_records if r.get("remote_id")}
        drift = len(remote_ids.symmetric_difference(local_ids))
        return ReconcileResult(drifted_records=drift, resolved_records=0, strategy_applied="last_write_wins")

    def healthcheck(self) -> HealthResult:
        t0 = time.time()
        auth = self.authenticate()
        latency = (time.time() - t0) * 1000
        return HealthResult(healthy=auth.success, latency_ms=latency,
                            message="ok" if auth.success else auth.error)
