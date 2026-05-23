"""
Encrypted credential storage.

Credentials are stored as base64-encoded JSON (Fernet-encrypted when key available).
Falls back to plaintext in development if INTEGRATION_CREDENTIAL_KEY is absent.
"""
from __future__ import annotations

import base64
import json
import os
from typing import Optional


def _get_fernet():
    try:
        from cryptography.fernet import Fernet
        key = os.environ.get("INTEGRATION_CREDENTIAL_KEY", "")
        if key:
            return Fernet(key.encode() if isinstance(key, str) else key)
    except ImportError:
        pass
    return None


class CredentialStore:
    """
    In-process credential store. In production, back this with Vault or AWS Secrets Manager.
    Keys: f"{tenant_id}:{platform}"
    """
    _store: dict[str, bytes] = {}

    @classmethod
    def put(cls, tenant_id: str, platform: str, credentials: dict) -> None:
        key = f"{tenant_id}:{platform}"
        raw = json.dumps(credentials).encode()
        fernet = _get_fernet()
        cls._store[key] = fernet.encrypt(raw) if fernet else base64.b64encode(raw)

    @classmethod
    def get(cls, tenant_id: str, platform: str) -> Optional[dict]:
        key = f"{tenant_id}:{platform}"
        blob = cls._store.get(key)
        if blob is None:
            return None
        fernet = _get_fernet()
        raw = fernet.decrypt(blob) if fernet else base64.b64decode(blob)
        return json.loads(raw)

    @classmethod
    def delete(cls, tenant_id: str, platform: str) -> bool:
        key = f"{tenant_id}:{platform}"
        existed = key in cls._store
        cls._store.pop(key, None)
        return existed

    @classmethod
    def list_tenants(cls) -> list[str]:
        return list({k.split(":")[0] for k in cls._store})

    @classmethod
    def clear(cls) -> None:
        cls._store.clear()


class TokenRotator:
    """
    Schedules credential rotation. Tracks last-rotated timestamps.
    Rotation policy: rotate if > ROTATION_INTERVAL_DAYS old.
    """
    ROTATION_INTERVAL_DAYS = 30
    _rotated_at: dict[str, float] = {}

    @classmethod
    def mark_rotated(cls, tenant_id: str, platform: str) -> None:
        import time
        cls._rotated_at[f"{tenant_id}:{platform}"] = time.time()

    @classmethod
    def needs_rotation(cls, tenant_id: str, platform: str) -> bool:
        import time
        key = f"{tenant_id}:{platform}"
        last = cls._rotated_at.get(key, 0)
        return (time.time() - last) > cls.ROTATION_INTERVAL_DAYS * 86400

    @classmethod
    def due_for_rotation(cls) -> list[str]:
        return [k for k in cls._rotated_at if cls.needs_rotation(*k.split(":", 1))]
