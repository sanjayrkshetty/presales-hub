from __future__ import annotations

from typing import TYPE_CHECKING

from agent_engine.tools.base import AgentTool, ToolResult

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class FetchWorkflowStateTool(AgentTool):
    name = "fetch_workflow_state"
    description = "Fetch current workflow stage and pending approvals for a proposal."

    async def execute(self, proposal_id: str, db: "Session", **_) -> ToolResult:
        if not proposal_id:
            return ToolResult(tool_name=self.name, success=False, error="proposal_id required")
        from models import Proposal, Approval
        proposal = db.query(Proposal).filter(Proposal.id == proposal_id).first()
        if not proposal:
            return ToolResult(tool_name=self.name, success=False, error=f"Proposal {proposal_id} not found")
        approvals = (
            db.query(Approval)
            .filter(Approval.proposal_id == proposal_id)
            .all()
        )
        return ToolResult(
            tool_name=self.name,
            success=True,
            data={
                "stage": proposal.stage,
                "approvals": [
                    {"id": str(a.id), "stage": a.stage, "status": a.status}
                    for a in approvals
                ],
            },
        )


class ListPendingApprovalsTool(AgentTool):
    name = "list_pending_approvals"
    description = "Return all pending approval records for a proposal."

    async def execute(self, proposal_id: str, db: "Session", **_) -> ToolResult:
        if not proposal_id:
            return ToolResult(tool_name=self.name, success=False, error="proposal_id required")
        from models import Approval
        pending = (
            db.query(Approval)
            .filter(Approval.proposal_id == proposal_id, Approval.status == "pending")
            .all()
        )
        return ToolResult(
            tool_name=self.name,
            success=True,
            data={"pending": [{"id": str(a.id), "stage": a.stage} for a in pending]},
        )
