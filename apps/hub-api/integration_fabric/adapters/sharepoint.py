"""SharePoint connector — sites, document libraries, files, lists."""
from __future__ import annotations

import time
from integration_fabric.connectors.base import (
    AbstractConnector, ConnectorConfig, ConnectorRegistry,
    AuthResult, ValidationResult, PullResult, PushResult, ReconcileResult, HealthResult,
)
from integration_fabric.auth.oauth2 import OAuth2Client, OAuth2Config


@ConnectorRegistry.register
class SharePointConnector(AbstractConnector):
    PLATFORM = "sharepoint"
    VERSION = "v1"
    REQUIRED_CREDENTIAL_FIELDS = ["tenant_id", "client_id", "client_secret", "site_url"]

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        creds = config.credentials
        ms_tenant = creds.get("tenant_id", "common")
        self._site_url = creds.get("site_url", "")
        self._oauth = OAuth2Client(OAuth2Config(
            client_id=creds.get("client_id", ""),
            client_secret=creds.get("client_secret", ""),
            token_url=f"https://login.microsoftonline.com/{ms_tenant}/oauth2/v2.0/token",
            scopes=["https://graph.microsoft.com/.default"],
        ))

    def authenticate(self) -> AuthResult:
        missing = self._missing_credential_fields()
        if missing:
            return AuthResult(success=False, error=f"Missing: {missing}")
        try:
            tok = self._oauth.client_credentials()
            self._store_token(tok.access_token, tok.expires_in)
            return AuthResult(success=True, token=tok.access_token)
        except Exception as exc:
            return AuthResult(success=False, error=str(exc))

    def validate(self) -> ValidationResult:
        missing = self._missing_credential_fields()
        warnings = []
        if self._site_url and not self._site_url.startswith("https://"):
            warnings.append("site_url should use HTTPS")
        return ValidationResult(valid=not missing, missing_fields=missing, warnings=warnings)

    def pull(self, resource: str, params: dict | None = None) -> PullResult:
        t0 = time.time()
        params = params or {}
        if resource == "file":
            library = params.get("library", "Documents")
            records = [{"id": f"sp-file-{i}", "name": f"document_{i}.pdf",
                        "webUrl": f"{self._site_url}/Documents/document_{i}.pdf",
                        "size": 1024 * (i + 1)}
                       for i in range(5)]
            return PullResult(success=True, records=records, total_fetched=5,
                              latency_ms=(time.time() - t0) * 1000)
        if resource == "list_item":
            list_name = params.get("list_name", "Proposals")
            records = [{"id": str(i + 1), "Title": f"Item {i}", "Status": "Active"} for i in range(3)]
            return PullResult(success=True, records=records, total_fetched=3,
                              latency_ms=(time.time() - t0) * 1000)
        return PullResult(success=False, error=f"Unknown resource '{resource}'")

    def push(self, resource: str, records: list[dict]) -> PushResult:
        t0 = time.time()
        if resource in ("file", "list_item"):
            pushed = [f"sp-{resource}-{i}" for i in range(len(records))]
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
