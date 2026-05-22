from __future__ import annotations

from typing import TYPE_CHECKING

from agent_engine.tools.base import AgentTool, ToolResult

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class SearchMemoryTool(AgentTool):
    name = "search_memory"
    description = "Search institutional memory for chunks relevant to a query."

    async def execute(self, query: str, db: "Session", top_k: int = 5, **_) -> ToolResult:
        if not query:
            return ToolResult(tool_name=self.name, success=False, error="query required")
        from copilot_engine.retrieval.context_retriever import ContextRetriever
        retriever = ContextRetriever(db=db)
        chunks = retriever.retrieve(query=query, top_k=top_k)
        return ToolResult(
            tool_name=self.name,
            success=True,
            data={"chunks": [c.to_dict() if hasattr(c, "to_dict") else str(c) for c in chunks]},
        )


class FetchSimilarProposalsTool(AgentTool):
    name = "fetch_similar_proposals"
    description = "Find past proposals with similar rfp_type or keywords."

    async def execute(self, rfp_type: str, db: "Session", limit: int = 3, **_) -> ToolResult:
        from models import Proposal
        from models.opportunity import Opportunity
        opps = db.query(Opportunity).filter(Opportunity.rfp_type == rfp_type).all()
        opp_ids = [o.id for o in opps]
        proposals = (
            db.query(Proposal)
            .filter(Proposal.opportunity_id.in_(opp_ids))
            .limit(limit)
            .all()
        )
        return ToolResult(
            tool_name=self.name,
            success=True,
            data={
                "similar": [
                    {"id": str(p.id), "stage": p.stage, "content_keys": list((p.content or {}).keys())}
                    for p in proposals
                ]
            },
        )
