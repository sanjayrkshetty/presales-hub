from datetime import datetime
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.orm import Session, joinedload

from db.database import get_db
from models import Opportunity, Client, Proposal, SlaConfig, AuditLog

router = APIRouter(prefix="/api/opportunities", tags=["opportunities"])


class OpportunityCreate(BaseModel):
    title: str
    client_name: str
    sector: str | None = None
    region: str | None = None
    rfp_type: str | None = None
    deal_value_cr: float | None = None
    win_probability: int = 50
    deadline: str | None = None
    owner_id: str | None = None


def _sla_hours_remaining(stage: str, updated_at: datetime, sla_map: dict[str, int]) -> dict:
    hours_allowed = sla_map.get(stage, 0)
    if not hours_allowed:
        return {"status": "ok", "hours_remaining": None, "hours_allowed": None}
    elapsed = (datetime.utcnow() - updated_at).total_seconds() / 3600
    remaining = hours_allowed - elapsed
    if remaining < 0:
        return {"status": "breached", "hours_remaining": round(remaining, 1), "hours_allowed": hours_allowed}
    elif remaining < hours_allowed * 0.25:
        return {"status": "warning", "hours_remaining": round(remaining, 1), "hours_allowed": hours_allowed}
    return {"status": "ok", "hours_remaining": round(remaining, 1), "hours_allowed": hours_allowed}


def _opportunity_dict(opp: Opportunity, sla_map: dict[str, int]) -> dict[str, Any]:
    sla = _sla_hours_remaining(
        opp.stage,
        opp.updated_at or opp.created_at,
        sla_map,
    )
    proposal = opp.proposal
    return {
        "id": opp.id,
        "title": opp.title,
        "rfp_type": opp.rfp_type,
        "stage": opp.stage,
        "deal_value_cr": float(opp.deal_value_cr) if opp.deal_value_cr else None,
        "win_probability": opp.win_probability,
        "deadline": opp.deadline.isoformat() if opp.deadline else None,
        "created_at": opp.created_at.isoformat(),
        "updated_at": (opp.updated_at or opp.created_at).isoformat(),
        "client": {
            "id": opp.client.id,
            "name": opp.client.name,
            "sector": opp.client.sector,
            "tier": opp.client.tier,
        } if opp.client else None,
        "proposal_id": proposal.id if proposal else None,
        "health_score": proposal.health_score if proposal else None,
        "sla": sla,
    }


@router.get("")
def list_opportunities(db: Session = Depends(get_db)):
    opps = db.scalars(
        select(Opportunity)
        .options(joinedload(Opportunity.client), joinedload(Opportunity.proposal))
        .order_by(Opportunity.updated_at.desc())
    ).all()
    sla_configs = db.scalars(select(SlaConfig)).all()
    sla_map = {s.stage: s.hours_allowed for s in sla_configs}
    return [_opportunity_dict(o, sla_map) for o in opps]


@router.get("/{opp_id}")
def get_opportunity(opp_id: str, db: Session = Depends(get_db)):
    opp = db.scalar(
        select(Opportunity)
        .where(Opportunity.id == opp_id)
        .options(
            joinedload(Opportunity.client),
            joinedload(Opportunity.proposal).joinedload(Proposal.assignments),
            joinedload(Opportunity.proposal).joinedload(Proposal.approvals),
            joinedload(Opportunity.proposal).joinedload(Proposal.activity),
        )
    )
    if not opp:
        raise HTTPException(404, "Opportunity not found")

    sla_configs = db.scalars(select(SlaConfig)).all()
    sla_map = {s.stage: s.hours_allowed for s in sla_configs}
    base = _opportunity_dict(opp, sla_map)

    if opp.proposal:
        p = opp.proposal
        base["proposal"] = {
            "id": p.id,
            "stage": p.stage,
            "health_score": p.health_score,
            "version": p.version,
            "content": p.content,
            "submitted_at": p.submitted_at.isoformat() if p.submitted_at else None,
            "assignments": [
                {
                    "id": a.id,
                    "stakeholder_id": a.stakeholder_id,
                    "role": a.role,
                    "bu": a.bu,
                    "status": a.status,
                    "due_at": a.due_at.isoformat() if a.due_at else None,
                }
                for a in p.assignments
            ],
            "approvals": [
                {
                    "id": a.id,
                    "approver_id": a.approver_id,
                    "stage": a.stage,
                    "order_index": a.order_index,
                    "parallel_group": a.parallel_group,
                    "status": a.status,
                    "due_at": a.due_at.isoformat() if a.due_at else None,
                }
                for a in sorted(p.approvals, key=lambda x: x.order_index)
            ],
            "recent_activity": [
                {
                    "id": act.id,
                    "actor_name": act.actor_name,
                    "action_type": act.action_type,
                    "description": act.description,
                    "is_alert": act.is_alert,
                    "created_at": act.created_at.isoformat(),
                }
                for act in sorted(p.activity, key=lambda x: x.created_at, reverse=True)[:10]
            ],
        }

    return base


@router.post("")
def create_opportunity(payload: OpportunityCreate, db: Session = Depends(get_db)):
    # Find or create client
    client = db.scalar(select(Client).where(Client.name == payload.client_name))
    if not client:
        client = Client(
            name=payload.client_name,
            sector=payload.sector,
            region=payload.region,
            tier="Enterprise",
        )
        db.add(client)
        db.flush()

    opp = Opportunity(
        client_id=client.id,
        title=payload.title,
        rfp_type=payload.rfp_type,
        deal_value_cr=payload.deal_value_cr,
        win_probability=payload.win_probability,
        stage="intake",
        owner_id=payload.owner_id,
        deadline=datetime.fromisoformat(payload.deadline).date() if payload.deadline else None,
    )
    db.add(opp)
    db.flush()

    proposal = Proposal(opportunity_id=opp.id, stage="intake")
    db.add(proposal)

    audit = AuditLog(
        entity_type="opportunity",
        entity_id=opp.id,
        action="created",
        to_state="intake",
    )
    db.add(audit)
    db.commit()
    db.refresh(opp)

    sla_map = {s.stage: s.hours_allowed for s in db.scalars(select(SlaConfig)).all()}
    opp.client = client
    return _opportunity_dict(opp, sla_map)
