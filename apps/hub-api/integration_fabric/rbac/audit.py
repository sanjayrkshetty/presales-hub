"""
RBAC audit log — immutable append-only record of access decisions.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AuditEntry:
    user_id: str
    permission: str
    allowed: bool
    roles: list[str]
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    tenant_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    reason: str = ""


class AuditLog:
    """
    In-process audit log. In production, persist to append-only DB table or
    immutable audit service (CloudTrail, Datadog Audit Logs).
    """
    _entries: list[AuditEntry] = []
    MAX_SIZE = 100_000

    @classmethod
    def record(cls, entry: AuditEntry) -> None:
        if len(cls._entries) >= cls.MAX_SIZE:
            cls._entries = cls._entries[cls.MAX_SIZE // 2:]
        cls._entries.append(entry)

    @classmethod
    def log_access(
        cls,
        user_id: str,
        permission: str,
        allowed: bool,
        roles: list[str],
        resource_type: str = "",
        resource_id: str = "",
        tenant_id: str = "",
        reason: str = "",
    ) -> None:
        cls.record(AuditEntry(
            user_id=user_id,
            permission=permission,
            allowed=allowed,
            roles=roles,
            resource_type=resource_type or None,
            resource_id=resource_id or None,
            tenant_id=tenant_id or None,
            reason=reason,
        ))

    @classmethod
    def get_user_history(cls, user_id: str, limit: int = 100) -> list[AuditEntry]:
        return [e for e in reversed(cls._entries) if e.user_id == user_id][:limit]

    @classmethod
    def get_denied(cls, limit: int = 100) -> list[AuditEntry]:
        return [e for e in reversed(cls._entries) if not e.allowed][:limit]

    @classmethod
    def clear(cls) -> None:
        cls._entries.clear()
