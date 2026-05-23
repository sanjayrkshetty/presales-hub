"""
Bidirectional sync engine.

Manages sync state via SyncRecord table.
Provides idempotent upsert semantics — duplicate syncs are safe.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from integration_fabric.config import SYNC_CONFLICT_STRATEGY

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _checksum(record: dict) -> str:
    body = json.dumps(record, sort_keys=True, default=str).encode()
    return hashlib.sha256(body).hexdigest()[:16]


def upsert_sync_record(
    db: "Session",
    tenant_id: str,
    platform: str,
    local_id: str,
    remote_id: Optional[str],
    resource_type: str,
    local_data: dict,
) -> "SyncRecord":
    from sqlalchemy import select
    from models.integration import SyncRecord

    existing = db.scalars(
        select(SyncRecord)
        .where(SyncRecord.tenant_id == tenant_id)
        .where(SyncRecord.platform == platform)
        .where(SyncRecord.local_id == local_id)
        .where(SyncRecord.resource_type == resource_type)
    ).first()

    checksum = _checksum(local_data)

    if existing:
        if existing.checksum == checksum:
            return existing
        existing.remote_id = remote_id or existing.remote_id
        existing.checksum = checksum
        existing.sync_status = "synced"
        existing.last_synced_at = datetime.utcnow()
        db.flush()
        return existing

    record = SyncRecord(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        platform=platform,
        local_id=local_id,
        remote_id=remote_id,
        resource_type=resource_type,
        sync_status="synced",
        last_synced_at=datetime.utcnow(),
        checksum=checksum,
        created_at=datetime.utcnow(),
    )
    db.add(record)
    db.flush()
    return record


def get_sync_record(
    db: "Session", tenant_id: str, platform: str, local_id: str, resource_type: str
) -> Optional["SyncRecord"]:
    from sqlalchemy import select
    from models.integration import SyncRecord
    return db.scalars(
        select(SyncRecord)
        .where(SyncRecord.tenant_id == tenant_id)
        .where(SyncRecord.platform == platform)
        .where(SyncRecord.local_id == local_id)
        .where(SyncRecord.resource_type == resource_type)
    ).first()


def mark_conflict(db: "Session", sync_record_id: str, conflict_data: dict) -> None:
    from models.integration import SyncRecord
    rec = db.get(SyncRecord, sync_record_id)
    if rec:
        rec.sync_status = "conflict"
        rec.conflict_data = conflict_data
        db.flush()


def list_unsynced(db: "Session", tenant_id: str, platform: str) -> list:
    from sqlalchemy import select
    from models.integration import SyncRecord
    return list(db.scalars(
        select(SyncRecord)
        .where(SyncRecord.tenant_id == tenant_id)
        .where(SyncRecord.platform == platform)
        .where(SyncRecord.sync_status.in_(["pending", "conflict", "failed"]))
    ).all())
