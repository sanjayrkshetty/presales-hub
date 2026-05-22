"""
Proposal context builder.

Assembles structured data from DB (proposal, opportunity, approvals)
into both a dict and a flat text block for LLM prompt injection.
"""
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Proposal, Opportunity, Approval


class ProposalContextBuilder:
    def __init__(self, db: Session):
        self._db = db

    def build(self, proposal_id: str) -> dict:
        proposal = self._db.scalar(
            select(Proposal).where(Proposal.id == proposal_id)
        )
        if not proposal:
            return {}

        opp = None
        if proposal.opportunity_id:
            opp = self._db.scalar(
                select(Opportunity).where(Opportunity.id == proposal.opportunity_id)
            )

        approvals = list(self._db.scalars(
            select(Approval).where(Approval.proposal_id == proposal_id)
        ).all())

        created_at = proposal.created_at.isoformat() if proposal.created_at else None
        days_active = None
        if proposal.created_at:
            days_active = (datetime.utcnow() - proposal.created_at).days

        return {
            "proposal_id": proposal_id,
            "title": opp.title if opp else "(no title)",
            "stage": proposal.stage,
            "rfp_type": opp.rfp_type if opp else None,
            "content": proposal.content or {},
            "created_at": created_at,
            "days_active": days_active,
            "opportunity": {
                "id": opp.id,
                "title": opp.title,
                "client_id": opp.client_id,
                "deal_value_cr": str(opp.deal_value_cr) if opp.deal_value_cr else None,
                "stage": opp.stage,
            } if opp else {},
            "approvals": [
                {
                    "id": a.id,
                    "stage": a.stage,
                    "status": a.status,
                    "approver_id": a.approver_id,
                    "decision_note": a.decision_note,
                    "decided_at": a.decided_at.isoformat() if a.decided_at else None,
                }
                for a in approvals
            ],
        }

    @staticmethod
    def to_text(ctx: dict) -> str:
        """Flatten proposal context dict to LLM-readable text."""
        if not ctx:
            return "Proposal not found."

        lines = [
            f"Proposal: {ctx.get('title', 'Untitled')} [Stage: {ctx.get('stage', '?')}]",
            f"RFP Type: {ctx.get('rfp_type', 'N/A')} | Days Active: {ctx.get('days_active', '?')}",
        ]

        opp = ctx.get("opportunity") or {}
        if opp:
            lines.append(
                f"Opportunity: {opp.get('title')} | Client: {opp.get('client_id')} | Value: {opp.get('deal_value_cr')}"
            )

        approvals = ctx.get("approvals", [])
        if approvals:
            pending = sum(1 for a in approvals if a["status"] == "pending")
            approved = sum(1 for a in approvals if a["status"] == "approved")
            rejected = sum(1 for a in approvals if a["status"] == "rejected")
            lines.append(f"Approvals: {pending} pending, {approved} approved, {rejected} rejected")
            for a in approvals:
                note = f" — {a['decision_note'][:100]}" if a.get("decision_note") else ""
                lines.append(f"  [{a['stage']}] {a['status']}{note}")

        content = ctx.get("content") or {}
        for section, text in content.items():
            if text:
                preview = str(text)[:300]
                ellipsis = "..." if len(str(text)) > 300 else ""
                lines.append(f"\n[Section: {section}]\n{preview}{ellipsis}")

        return "\n".join(lines)
