from __future__ import annotations

from dataclasses import dataclass, field

_SKIP_FIELDS = {"id", "updated_at", "created_at", "last_synced_at"}


@dataclass
class DriftReport:
    drifted_count: int
    matching_count: int
    field_deltas: list[dict] = field(default_factory=list)
    # [{local_id, remote_id, field, local_val, remote_val}]


def detect_drift(
    local_records: list[dict],
    remote_records: list[dict],
) -> DriftReport:
    remote_by_id: dict[str, dict] = {r.get("id", ""): r for r in remote_records}

    drifted: list[dict] = []
    matching = 0

    for local in local_records:
        lid = local.get("id", "")
        remote = remote_by_id.get(lid)
        if remote is None:
            continue

        deltas = [
            {
                "local_id": lid,
                "remote_id": remote.get("id", lid),
                "field": key,
                "local_val": local[key],
                "remote_val": remote[key],
            }
            for key in local
            if key not in _SKIP_FIELDS and key in remote and local[key] != remote[key]
        ]

        if deltas:
            drifted.extend(deltas)
        else:
            matching += 1

    drifted_count = len({d["local_id"] for d in drifted})
    return DriftReport(
        drifted_count=drifted_count,
        matching_count=matching,
        field_deltas=drifted,
    )
