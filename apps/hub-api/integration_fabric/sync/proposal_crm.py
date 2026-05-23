"""Proposal stage ↔ CRM opportunity bidirectional sync."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

_STAGE_TO_SF: dict[str, str] = {
    "intake": "Prospecting", "qualification": "Qualification",
    "proposal_review": "Proposal/Price Quote", "technical_review": "Value Proposition",
    "security_review": "Perception Analysis", "approval": "Negotiation/Review",
    "closed_won": "Closed Won", "closed_lost": "Closed Lost",
}

_SF_TO_STAGE: dict[str, str] = {v: k for k, v in _STAGE_TO_SF.items()}


@dataclass
class CRMSyncResult:
    proposals_pushed: int = 0
    proposals_pulled: int = 0
    conflicts: int = 0
    errors: list[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


def sync_proposals_to_crm(
    db: "Session",
    tenant_id: str,
    connector,
    dry_run: bool = False,
) -> CRMSyncResult:
    from sqlalchemy import select
    from models import Proposal
    from integration_fabric.sync.engine import upsert_sync_record

    result = CRMSyncResult()
    proposals = db.scalars(select(Proposal)).all()

    push_records = []
    for p in proposals:
        push_records.append({
            "StageName": _STAGE_TO_SF.get(p.stage, "Prospecting"),
            "local_id": p.id,
        })

    if not dry_run and push_records:
        push_result = connector.push("opportunity", push_records)
        result.proposals_pushed = len(push_result.pushed_ids)
        for i, p in enumerate(proposals):
            if i < len(push_result.pushed_ids):
                upsert_sync_record(db, tenant_id, connector.PLATFORM, p.id,
                                   push_result.pushed_ids[i], "proposal", {"stage": p.stage})
    else:
        result.proposals_pushed = len(push_records)

    return result


def sync_crm_to_proposals(
    db: "Session",
    tenant_id: str,
    connector,
    dry_run: bool = False,
) -> CRMSyncResult:
    from sqlalchemy import select
    from models import Proposal
    from integration_fabric.sync.engine import get_sync_record

    result = CRMSyncResult()
    pull = connector.pull("opportunity")
    if not pull.success:
        result.errors.append(pull.error or "pull failed")
        return result

    for remote_opp in pull.records:
        remote_stage = _SF_TO_STAGE.get(remote_opp.get("stage", ""), "intake")
        local_id = remote_opp.get("local_id")
        if not local_id:
            continue
        p = db.get(Proposal, local_id)
        if p and p.stage != remote_stage and not dry_run:
            result.proposals_pulled += 1

    return result
