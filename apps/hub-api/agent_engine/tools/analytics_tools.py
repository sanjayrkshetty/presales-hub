from __future__ import annotations

from typing import TYPE_CHECKING

from agent_engine.tools.base import AgentTool, ToolResult

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class ComputeWinRateTool(AgentTool):
    name = "compute_win_rate"
    description = "Compute historical win rate for a given rfp_type."

    async def execute(self, rfp_type: str, db: "Session", **_) -> ToolResult:
        from models import Proposal
        from models.opportunity import Opportunity
        opps = db.query(Opportunity).filter(Opportunity.rfp_type == rfp_type).all()
        if not opps:
            return ToolResult(tool_name=self.name, success=True, data={"win_rate": None, "sample_size": 0})
        opp_ids = [o.id for o in opps]
        total = db.query(Proposal).filter(Proposal.opportunity_id.in_(opp_ids)).count()
        won = (
            db.query(Proposal)
            .filter(Proposal.opportunity_id.in_(opp_ids), Proposal.stage == "won")
            .count()
        )
        return ToolResult(
            tool_name=self.name,
            success=True,
            data={"win_rate": round(won / total, 3) if total else None, "sample_size": total},
        )


class SummarizeOpportunityMetricsTool(AgentTool):
    name = "summarize_opportunity_metrics"
    description = "Return deal value, stage, and client info for an opportunity."

    async def execute(self, opportunity_id: str, db: "Session", **_) -> ToolResult:
        if not opportunity_id:
            return ToolResult(tool_name=self.name, success=False, error="opportunity_id required")
        from models.opportunity import Opportunity, Client
        opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
        if not opp:
            return ToolResult(tool_name=self.name, success=False, error=f"Opportunity {opportunity_id} not found")
        client = db.query(Client).filter(Client.id == opp.client_id).first()
        return ToolResult(
            tool_name=self.name,
            success=True,
            data={
                "title": opp.title,
                "rfp_type": opp.rfp_type,
                "stage": opp.stage,
                "deal_value_cr": str(opp.deal_value_cr) if opp.deal_value_cr else None,
                "client_name": client.name if client else None,
            },
        )
