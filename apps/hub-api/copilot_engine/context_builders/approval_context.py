"""Approval context builder — assembles approval record and timeline data."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Approval, Proposal


class ApprovalContextBuilder:
    def __init__(self, db: Session):
        self._db = db

    def build(self, approval_id: str) -> dict:
        approval = self._db.scalar(
            select(Approval).where(Approval.id == approval_id)
        )
        if not approval:
            return {}

        proposal = None
        if approval.proposal_id:
            proposal = self._db.scalar(
                select(Proposal).where(Proposal.id == approval.proposal_id)
            )

        # Sibling approvals (same proposal)
        siblings = list(self._db.scalars(
            select(Approval).where(
                Approval.proposal_id == approval.proposal_id,
                Approval.id != approval_id,
            )
        ).all())

        created_at = approval.created_at.isoformat() if approval.created_at else None
        decided_at = approval.decided_at.isoformat() if approval.decided_at else None
        decision_minutes = None
        if approval.created_at and approval.decided_at:
            delta = approval.decided_at - approval.created_at
            decision_minutes = round(delta.total_seconds() / 60, 1)

        return {
            "approval_id": approval_id,
            "proposal_id": approval.proposal_id,
            "stage": approval.stage,
            "status": approval.status,
            "approver_id": approval.approver_id,
            "decision_note": approval.decision_note,
            "created_at": created_at,
            "decided_at": decided_at,
            "decision_minutes": decision_minutes,
            "proposal_stage": proposal.stage if proposal else None,
            "sibling_approvals": [
                {
                    "id": s.id,
                    "stage": s.stage,
                    "status": s.status,
                    "approver_id": s.approver_id,
                }
                for s in siblings
            ],
        }

    @staticmethod
    def to_text(ctx: dict) -> str:
        if not ctx:
            return "Approval not found."
        lines = [
            f"Approval: {ctx.get('approval_id')} [{ctx.get('stage')}] — {ctx.get('status')}",
            f"Proposal stage at time of approval: {ctx.get('proposal_stage')}",
            f"Approver: {ctx.get('approver_id') or 'unassigned'}",
        ]
        if ctx.get("decision_minutes") is not None:
            lines.append(f"Decision time: {ctx['decision_minutes']} minutes")
        if ctx.get("decision_note"):
            lines.append(f"Decision note: {ctx['decision_note'][:400]}")
        siblings = ctx.get("sibling_approvals", [])
        if siblings:
            lines.append(f"Parallel approvals ({len(siblings)}):")
            for s in siblings:
                lines.append(f"  [{s['stage']}] {s['status']} — {s.get('approver_id') or 'unassigned'}")
        return "\n".join(lines)
