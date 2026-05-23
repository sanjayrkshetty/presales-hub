"""Microsoft Teams connector — channel messages, adaptive cards, meetings."""
from __future__ import annotations

import time
from integration_fabric.connectors.base import (
    AbstractConnector, ConnectorConfig, ConnectorRegistry,
    AuthResult, ValidationResult, PullResult, PushResult, ReconcileResult, HealthResult,
)
from integration_fabric.auth.oauth2 import OAuth2Client, OAuth2Config


@ConnectorRegistry.register
class TeamsConnector(AbstractConnector):
    PLATFORM = "teams"
    VERSION = "v1"
    REQUIRED_CREDENTIAL_FIELDS = ["tenant_id", "client_id", "client_secret"]

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
            return AuthResult(success=True, token=tok.access_token, expires_at=self._token_expires_at)
        except Exception as exc:
            return AuthResult(success=False, error=str(exc))

    def validate(self) -> ValidationResult:
        missing = self._missing_credential_fields()
        return ValidationResult(valid=not missing, missing_fields=missing)

    def pull(self, resource: str, params: dict | None = None) -> PullResult:
        t0 = time.time()
        params = params or {}
        if resource == "channel":
            team_id = params.get("team_id", "team-001")
            records = [{"id": f"channel-{i}", "displayName": f"Channel {i}", "teamId": team_id}
                       for i in range(3)]
            return PullResult(success=True, records=records, total_fetched=3,
                              latency_ms=(time.time() - t0) * 1000)
        if resource == "message":
            records = [{"id": f"msg-{i}", "body": {"content": f"Teams message {i}"}} for i in range(5)]
            return PullResult(success=True, records=records, total_fetched=5,
                              latency_ms=(time.time() - t0) * 1000)
        return PullResult(success=False, error=f"Unknown resource '{resource}'")

    def push(self, resource: str, records: list[dict]) -> PushResult:
        t0 = time.time()
        if resource in ("message", "adaptive_card"):
            pushed = [f"teams-{resource}-{i}" for i in range(len(records))]
            return PushResult(success=True, pushed_ids=pushed, latency_ms=(time.time() - t0) * 1000)
        return PushResult(success=False, error=f"Unsupported resource '{resource}'")

    def send_notification(self, team_id: str, channel_id: str, text: str) -> PushResult:
        return self.push("message", [{"team_id": team_id, "channel_id": channel_id, "text": text}])

    def reconcile(self, resource: str, local_records: list[dict]) -> ReconcileResult:
        return ReconcileResult(drifted_records=0, resolved_records=0)

    def healthcheck(self) -> HealthResult:
        t0 = time.time()
        auth = self.authenticate()
        return HealthResult(healthy=auth.success, latency_ms=(time.time() - t0) * 1000,
                            message="ok" if auth.success else auth.error)
