from __future__ import annotations

from typing import TYPE_CHECKING

from agent_engine.tools.base import AgentTool, ToolResult

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class FetchProposalTool(AgentTool):
    name = "fetch_proposal"
    description = "Retrieve proposal record and its opportunity from the database."

    async def execute(self, proposal_id: str, db: "Session", **_) -> ToolResult:
        if not proposal_id:
            return ToolResult(tool_name=self.name, success=False, error="proposal_id required")
        from models import Proposal
        from models.opportunity import Opportunity
        proposal = db.query(Proposal).filter(Proposal.id == proposal_id).first()
        if not proposal:
            return ToolResult(tool_name=self.name, success=False, error=f"Proposal {proposal_id} not found")
        opp = db.query(Opportunity).filter(Opportunity.id == proposal.opportunity_id).first()
        return ToolResult(
            tool_name=self.name,
            success=True,
            data={
                "proposal_id": str(proposal.id),
                "stage": proposal.stage,
                "content": proposal.content or {},
                "opportunity": {
                    "title": opp.title if opp else None,
                    "rfp_type": opp.rfp_type if opp else None,
                    "deal_value_cr": str(opp.deal_value_cr) if opp and opp.deal_value_cr else None,
                } if opp else {},
            },
        )


class ListProposalSectionsTool(AgentTool):
    name = "list_proposal_sections"
    description = "List content section keys present in a proposal."

    async def execute(self, proposal_id: str, db: "Session", **_) -> ToolResult:
        if not proposal_id:
            return ToolResult(tool_name=self.name, success=False, error="proposal_id required")
        from models import Proposal
        proposal = db.query(Proposal).filter(Proposal.id == proposal_id).first()
        if not proposal:
            return ToolResult(tool_name=self.name, success=False, error=f"Proposal {proposal_id} not found")
        sections = list((proposal.content or {}).keys())
        return ToolResult(tool_name=self.name, success=True, data={"sections": sections})
