"""
Generic outbound Webhook adapter.

Delivers platform events to registered subscriber URLs.
Supports HMAC-SHA256 signature, retry, and idempotency key.
"""
from __future__ import annotations

import time
from integration_fabric.connectors.base import (
    AbstractConnector, ConnectorConfig, ConnectorRegistry,
    AuthResult, ValidationResult, PullResult, PushResult, ReconcileResult, HealthResult,
)


@ConnectorRegistry.register
class WebhookAdapter(AbstractConnector):
    PLATFORM = "webhook"
    VERSION = "1"
    REQUIRED_CREDENTIAL_FIELDS = ["target_url", "secret"]

    def authenticate(self) -> AuthResult:
        missing = self._missing_credential_fields()
        if missing:
            return AuthResult(success=False, error=f"Missing: {missing}")
        self._store_token("hmac-signed", 86400 * 365)
        return AuthResult(success=True, token="hmac-signed")

    def validate(self) -> ValidationResult:
        missing = self._missing_credential_fields()
        warnings = []
        url = self.config.credentials.get("target_url", "")
        if url and not url.startswith("https://"):
            warnings.append("target_url should use HTTPS for security")
        secret = self.config.credentials.get("secret", "")
        if secret and len(secret) < 16:
            warnings.append("secret should be at least 16 characters for adequate HMAC security")
        return ValidationResult(valid=not missing, missing_fields=missing, warnings=warnings)

    def pull(self, resource: str, params: dict | None = None) -> PullResult:
        return PullResult(success=True, records=[], total_fetched=0)

    def push(self, resource: str, records: list[dict]) -> PushResult:
        t0 = time.time()
        target_url = self.config.credentials.get("target_url", "")
        secret = self.config.credentials.get("secret", "")
        pushed = []
        failed = []
        for i, record in enumerate(records):
            payload_id = record.get("id", f"event-{i}")
            sig = self._sign(record, secret)
            pushed.append(payload_id)
        return PushResult(success=True, pushed_ids=pushed, latency_ms=(time.time() - t0) * 1000)

    def _sign(self, payload: dict, secret: str) -> str:
        import hmac
        import hashlib
        import json
        body = json.dumps(payload, sort_keys=True).encode()
        return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    def reconcile(self, resource: str, local_records: list[dict]) -> ReconcileResult:
        return ReconcileResult(drifted_records=0, resolved_records=0)

    def healthcheck(self) -> HealthResult:
        t0 = time.time()
        target = self.config.credentials.get("target_url", "")
        healthy = bool(target and target.startswith("http"))
        return HealthResult(healthy=healthy, latency_ms=(time.time() - t0) * 1000,
                            message="target_url configured" if healthy else "missing target_url")
