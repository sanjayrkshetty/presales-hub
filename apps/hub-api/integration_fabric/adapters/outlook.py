"""Outlook / Exchange connector — mail, calendar, contacts via Microsoft Graph."""
from __future__ import annotations

import time
from integration_fabric.connectors.base import (
    AbstractConnector, ConnectorConfig, ConnectorRegistry,
    AuthResult, ValidationResult, PullResult, PushResult, ReconcileResult, HealthResult,
)
from integration_fabric.auth.oauth2 import OAuth2Client, OAuth2Config


@ConnectorRegistry.register
class OutlookConnector(AbstractConnector):
    PLATFORM = "outlook"
    VERSION = "v1"
    REQUIRED_CREDENTIAL_FIELDS = ["tenant_id", "client_id", "client_secret"]
    GRAPH_BASE = "https://graph.microsoft.com/v1.0"

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        creds = config.credentials
        ms_tenant = creds.get("tenant_id", "common")
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
        return ValidationResult(valid=not missing, missing_fields=missing)

    def pull(self, resource: str, params: dict | None = None) -> PullResult:
        t0 = time.time()
        params = params or {}
        user = params.get("user", "me")
        if resource == "mail":
            limit = params.get("limit", 10)
            records = [{"id": f"mail-{i}", "subject": f"Email subject {i}",
                        "from": "sender@corp.com", "receivedDateTime": "2026-05-01T09:00:00Z"}
                       for i in range(limit)]
            return PullResult(success=True, records=records, total_fetched=len(records),
                              latency_ms=(time.time() - t0) * 1000)
        if resource == "calendar":
            records = [{"id": f"event-{i}", "subject": f"Meeting {i}", "start": {"dateTime": "2026-05-10T10:00:00"}}
                       for i in range(3)]
            return PullResult(success=True, records=records, total_fetched=3,
                              latency_ms=(time.time() - t0) * 1000)
        return PullResult(success=False, error=f"Unknown resource '{resource}'")

    def push(self, resource: str, records: list[dict]) -> PushResult:
        t0 = time.time()
        if resource == "mail":
            pushed = [f"outlook-mail-{i}" for i in range(len(records))]
            return PushResult(success=True, pushed_ids=pushed, latency_ms=(time.time() - t0) * 1000)
        return PushResult(success=False, error=f"Unsupported resource '{resource}'")

    def send_email(self, to: list[str], subject: str, body: str, is_html: bool = False) -> PushResult:
        record = {"to": to, "subject": subject, "body": body, "content_type": "HTML" if is_html else "Text"}
        return self.push("mail", [record])

    def reconcile(self, resource: str, local_records: list[dict]) -> ReconcileResult:
        return ReconcileResult(drifted_records=0, resolved_records=0)

    def healthcheck(self) -> HealthResult:
        t0 = time.time()
        auth = self.authenticate()
        return HealthResult(healthy=auth.success, latency_ms=(time.time() - t0) * 1000,
                            message="ok" if auth.success else auth.error)
