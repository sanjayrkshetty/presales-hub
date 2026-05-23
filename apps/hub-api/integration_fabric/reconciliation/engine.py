from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from integration_fabric.config import SYNC_CONFLICT_STRATEGY
from integration_fabric.reconciliation.drift_detector import detect_drift
from integration_fabric.reconciliation.conflict_resolver import resolve

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@dataclass
class ReconciliationReport:
    tenant_id: str
    platform: str
    total_local: int
    total_remote: int
    drifted_count: int
    resolved_count: int
    conflict_count: int
    field_deltas: list[dict]
    strategy_applied: str
    errors: list[str] = field(default_factory=list)


class ReconciliationEngine:
    def run_reconciliation(
        self,
        db: "Session",
        tenant_id: str,
        platform: str,
        connector,
    ) -> ReconciliationReport:
        from sqlalchemy import select
        from models.integration import SyncRecord
        from integration_fabric.sync.engine import upsert_sync_record, mark_conflict

        # 1. Load all local sync records for this tenant+platform
        local_orm = list(
            db.scalars(
                select(SyncRecord)
                .where(SyncRecord.tenant_id == tenant_id)
                .where(SyncRecord.platform == platform)
            ).all()
        )
        local_dicts = [
            {
                "id": r.local_id,
                "remote_id": r.remote_id,
                "resource_type": r.resource_type,
                "sync_status": r.sync_status,
                "checksum": r.checksum,
            }
            for r in local_orm
        ]
        local_by_local_id = {r.local_id: r for r in local_orm}

        # 2. Pull remote records
        errors: list[str] = []
        remote_records: list[dict] = []
        try:
            pull_result = connector.pull("all", {})
            remote_records = pull_result.records or []
        except Exception as exc:
            errors.append(f"pull error: {exc}")

        # Normalise remote records so their "id" matches local_id where possible
        # (adapters return remote id; map via remote_id stored in SyncRecord)
        remote_id_to_local_id = {r.remote_id: r.local_id for r in local_orm if r.remote_id}
        normalised_remote: list[dict] = []
        for rec in remote_records:
            rid = rec.get("id", "")
            norm = dict(rec)
            if rid in remote_id_to_local_id:
                norm["id"] = remote_id_to_local_id[rid]
            normalised_remote.append(norm)

        # 3. Detect drift
        drift = detect_drift(local_dicts, normalised_remote)

        # 4. Resolve each drifted record
        resolved_count = 0
        conflict_count = 0
        drifted_local_ids = {d["local_id"] for d in drift.field_deltas}

        remote_by_local_id = {rec.get("id", ""): rec for rec in normalised_remote}

        for local_id in drifted_local_ids:
            orm_record = local_by_local_id.get(local_id)
            remote_rec = remote_by_local_id.get(local_id)
            if orm_record is None or remote_rec is None:
                continue

            local_dict = {
                "id": orm_record.local_id,
                "resource_type": orm_record.resource_type,
                "checksum": orm_record.checksum,
            }

            try:
                winner = resolve(local_dict, remote_rec, SYNC_CONFLICT_STRATEGY)
                if SYNC_CONFLICT_STRATEGY == "manual":
                    delta_fields = [d for d in drift.field_deltas if d["local_id"] == local_id]
                    mark_conflict(db, orm_record.id, {"deltas": delta_fields})
                    conflict_count += 1
                else:
                    upsert_sync_record(
                        db,
                        tenant_id=tenant_id,
                        platform=platform,
                        local_id=local_id,
                        remote_id=orm_record.remote_id,
                        resource_type=orm_record.resource_type,
                        local_data=winner,
                    )
                    resolved_count += 1
            except Exception as exc:
                errors.append(f"resolve error for {local_id}: {exc}")

        return ReconciliationReport(
            tenant_id=tenant_id,
            platform=platform,
            total_local=len(local_dicts),
            total_remote=len(remote_records),
            drifted_count=drift.drifted_count,
            resolved_count=resolved_count,
            conflict_count=conflict_count,
            field_deltas=drift.field_deltas,
            strategy_applied=SYNC_CONFLICT_STRATEGY,
            errors=errors,
        )
