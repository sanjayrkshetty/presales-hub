"""Opportunity context builder — assembles opportunity and stakeholder data."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Opportunity, Stakeholder


class OpportunityContextBuilder:
    def __init__(self, db: Session):
        self._db = db

    def build(self, opportunity_id: str) -> dict:
        opp = self._db.scalar(
            select(Opportunity).where(Opportunity.id == opportunity_id)
        )
        if not opp:
            return {}

        stakeholders = list(self._db.scalars(
            select(Stakeholder).where(Stakeholder.opportunity_id == opportunity_id)
        ).all())

        return {
            "opportunity_id": opportunity_id,
            "title": opp.title,
            "client_id": opp.client_id,
            "deal_value_cr": str(opp.deal_value_cr) if opp.deal_value_cr else None,
            "stage": opp.stage,
            "created_at": opp.created_at.isoformat() if opp.created_at else None,
            "stakeholders": [
                {
                    "id": s.id,
                    "name": s.name,
                    "role": s.role,
                    "bu": s.bu,
                    "expertise": s.expertise or [],
                }
                for s in stakeholders
            ],
        }

    @staticmethod
    def to_text(ctx: dict) -> str:
        if not ctx:
            return "Opportunity not found."
        lines = [
            f"Opportunity: {ctx.get('title')} [Stage: {ctx.get('stage')}]",
            f"Client: {ctx.get('client_id')} | Value: {ctx.get('deal_value_cr')}",
        ]
        for s in ctx.get("stakeholders", []):
            exp = ", ".join(s.get("expertise") or [])
            lines.append(f"  Stakeholder: {s['name']} ({s['role']}) | BU: {s.get('bu')} | Expertise: {exp}")
        return "\n".join(lines)
