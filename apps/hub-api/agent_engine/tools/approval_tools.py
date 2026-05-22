from __future__ import annotations

from typing import TYPE_CHECKING

from agent_engine.tools.base import AgentTool, ToolResult

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class FetchApprovalHistoryTool(AgentTool):
    name = "fetch_approval_history"
    description = "Retrieve full approval history for a proposal."

    async def execute(self, proposal_id: str, db: "Session", **_) -> ToolResult:
        if not proposal_id:
            return ToolResult(tool_name=self.name, success=False, error="proposal_id required")
        from models import Approval
        approvals = (
            db.query(Approval)
            .filter(Approval.proposal_id == proposal_id)
            .order_by(Approval.created_at)
            .all()
        )
        return ToolResult(
            tool_name=self.name,
            success=True,
            data={
                "history": [
                    {
                        "id": str(a.id),
                        "stage": a.stage,
                        "status": a.status,
                        "notes": a.notes,
                        "created_at": a.created_at.isoformat() if a.created_at else None,
                    }
                    for a in approvals
                ]
            },
        )


class FetchApprovalTool(AgentTool):
    name = "fetch_approval"
    description = "Retrieve a single approval record by ID."

    async def execute(self, approval_id: str, db: "Session", **_) -> ToolResult:
        if not approval_id:
            return ToolResult(tool_name=self.name, success=False, error="approval_id required")
        from models import Approval
        approval = db.query(Approval).filter(Approval.id == approval_id).first()
        if not approval:
            return ToolResult(tool_name=self.name, success=False, error=f"Approval {approval_id} not found")
        return ToolResult(
            tool_name=self.name,
            success=True,
            data={
                "id": str(approval.id),
                "proposal_id": str(approval.proposal_id),
                "stage": approval.stage,
                "status": approval.status,
                "notes": approval.notes,
            },
        )
