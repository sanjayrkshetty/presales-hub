"""Slack connector — messages, channels, user lookup, escalation alerts."""
from __future__ import annotations

import time
from integration_fabric.connectors.base import (
    AbstractConnector, ConnectorConfig, ConnectorRegistry,
    AuthResult, ValidationResult, PullResult, PushResult, ReconcileResult, HealthResult,
)


@ConnectorRegistry.register
class SlackConnector(AbstractConnector):
    PLATFORM = "slack"
    VERSION = "v2"
    REQUIRED_CREDENTIAL_FIELDS = ["bot_token"]

    _SCOPES = ["channels:read", "chat:write", "users:read", "files:read"]

    def authenticate(self) -> AuthResult:
        missing = self._missing_credential_fields()
        if missing:
            return AuthResult(success=False, error=f"Missing: {missing}")
        token = self.config.credentials["bot_token"]
        if not token.startswith("xoxb-"):
            return AuthResult(success=False, error="bot_token must start with 'xoxb-'")
        self._store_token(token, 86400 * 365)
        return AuthResult(success=True, token=token)

    def validate(self) -> ValidationResult:
        missing = self._missing_credential_fields()
        warnings = []
        token = self.config.credentials.get("bot_token", "")
        if token and not token.startswith("xoxb-"):
            warnings.append("bot_token should be a Bot User OAuth token (xoxb-...)")
        return ValidationResult(valid=not missing, missing_fields=missing, warnings=warnings)

    def pull(self, resource: str, params: dict | None = None) -> PullResult:
        t0 = time.time()
        params = params or {}
        if resource == "channel":
            records = [
                {"id": "C001", "name": "presales-alerts", "is_private": False},
                {"id": "C002", "name": "escalations", "is_private": True},
            ]
            return PullResult(success=True, records=records, total_fetched=2,
                              latency_ms=(time.time() - t0) * 1000)
        if resource == "message":
            channel = params.get("channel", "C001")
            records = [{"ts": f"1700000{i:03d}.000", "text": f"Message {i}", "channel": channel}
                       for i in range(5)]
            return PullResult(success=True, records=records, total_fetched=5,
                              latency_ms=(time.time() - t0) * 1000)
        return PullResult(success=False, error=f"Unknown resource '{resource}'")

    def push(self, resource: str, records: list[dict]) -> PushResult:
        t0 = time.time()
        if resource == "message":
            pushed = [f"slack-msg-{i}" for i in range(len(records))]
            return PushResult(success=True, pushed_ids=pushed, latency_ms=(time.time() - t0) * 1000)
        return PushResult(success=False, error=f"Unsupported push resource '{resource}'")

    def send_alert(self, channel: str, text: str, blocks: list | None = None) -> PushResult:
        record = {"channel": channel, "text": text}
        if blocks:
            record["blocks"] = blocks
        return self.push("message", [record])

    def reconcile(self, resource: str, local_records: list[dict]) -> ReconcileResult:
        return ReconcileResult(drifted_records=0, resolved_records=0)

    def healthcheck(self) -> HealthResult:
        t0 = time.time()
        auth = self.authenticate()
        return HealthResult(healthy=auth.success, latency_ms=(time.time() - t0) * 1000,
                            message="ok" if auth.success else auth.error)
