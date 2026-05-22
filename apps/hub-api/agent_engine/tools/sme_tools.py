from __future__ import annotations

from typing import TYPE_CHECKING

from agent_engine.tools.base import AgentTool, ToolResult

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class ListSMEsTool(AgentTool):
    name = "list_smes"
    description = "List stakeholders tagged as SMEs from the database."

    async def execute(self, db: "Session", **_) -> ToolResult:
        from models.stakeholder import Stakeholder
        smes = db.query(Stakeholder).filter(Stakeholder.role == "sme").all()
        return ToolResult(
            tool_name=self.name,
            success=True,
            data={
                "smes": [
                    {"id": str(s.id), "name": s.name, "expertise": s.expertise or []}
                    for s in smes
                ]
            },
        )


class MatchSMEToRequirementsTool(AgentTool):
    name = "match_sme_to_requirements"
    description = "Score SME expertise coverage against provided requirement keywords."

    async def execute(self, requirements: list[str], db: "Session", **_) -> ToolResult:
        from models.stakeholder import Stakeholder
        smes = db.query(Stakeholder).filter(Stakeholder.role == "sme").all()
        req_set = {r.lower() for r in requirements}
        matches = []
        for s in smes:
            expertise = [e.lower() for e in (s.expertise or [])]
            overlap = len(req_set & set(expertise))
            matches.append({
                "id": str(s.id),
                "name": s.name,
                "match_score": overlap / max(len(req_set), 1),
                "matched_skills": list(req_set & set(expertise)),
            })
        matches.sort(key=lambda x: x["match_score"], reverse=True)
        return ToolResult(tool_name=self.name, success=True, data={"matches": matches})
