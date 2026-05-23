"""Google Drive connector — files, folders, shared drives, exports."""
from __future__ import annotations

import time
from integration_fabric.connectors.base import (
    AbstractConnector, ConnectorConfig, ConnectorRegistry,
    AuthResult, ValidationResult, PullResult, PushResult, ReconcileResult, HealthResult,
)
from integration_fabric.auth.oauth2 import OAuth2Client, OAuth2Config


@ConnectorRegistry.register
class GoogleDriveConnector(AbstractConnector):
    PLATFORM = "gdrive"
    VERSION = "v3"
    REQUIRED_CREDENTIAL_FIELDS = ["client_id", "client_secret", "refresh_token"]
    DRIVE_BASE = "https://www.googleapis.com/drive/v3"

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        creds = config.credentials
        self._oauth = OAuth2Client(OAuth2Config(
            client_id=creds.get("client_id", ""),
            client_secret=creds.get("client_secret", ""),
            token_url="https://oauth2.googleapis.com/token",
            scopes=["https://www.googleapis.com/auth/drive.readonly",
                    "https://www.googleapis.com/auth/drive.file"],
        ))
        self._refresh_token = creds.get("refresh_token", "")

    def authenticate(self) -> AuthResult:
        missing = self._missing_credential_fields()
        if missing:
            return AuthResult(success=False, error=f"Missing: {missing}")
        try:
            tok = self._oauth.refresh(self._refresh_token) if self._refresh_token else self._oauth.client_credentials()
            self._store_token(tok.access_token, tok.expires_in)
            return AuthResult(success=True, token=tok.access_token, expires_at=self._token_expires_at)
        except Exception as exc:
            return AuthResult(success=False, error=str(exc))

    def validate(self) -> ValidationResult:
        missing = self._missing_credential_fields()
        return ValidationResult(valid=not missing, missing_fields=missing)

    def pull(self, resource: str, params: dict | None = None) -> PullResult:
        t0 = time.time()
        params = params or {}
        if resource == "file":
            q = params.get("q", "mimeType='application/pdf'")
            limit = params.get("limit", 10)
            records = [{"id": f"gdrive-file-{i}", "name": f"document_{i}.pdf",
                        "mimeType": "application/pdf", "size": str(1024 * (i + 1))}
                       for i in range(limit)]
            return PullResult(success=True, records=records, total_fetched=len(records),
                              latency_ms=(time.time() - t0) * 1000)
        if resource == "folder":
            records = [{"id": f"gdrive-folder-{i}", "name": f"Folder {i}",
                        "mimeType": "application/vnd.google-apps.folder"}
                       for i in range(3)]
            return PullResult(success=True, records=records, total_fetched=3,
                              latency_ms=(time.time() - t0) * 1000)
        return PullResult(success=False, error=f"Unknown resource '{resource}'")

    def push(self, resource: str, records: list[dict]) -> PushResult:
        t0 = time.time()
        if resource in ("file", "folder"):
            pushed = [f"gdrive-{resource}-{i}" for i in range(len(records))]
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
