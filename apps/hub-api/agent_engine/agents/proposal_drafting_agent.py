from agent_engine.agents.base import AgentBase
from agent_engine.execution.task_contract import TaskContract, AgentResult
from agent_engine.tools.base import ToolResult
from agent_engine.config import APPROVAL_REQUIRED_AGENTS
from copilot_engine.graphs.draft_graph import run_section_draft_graph


class ProposalDraftingAgent(AgentBase):
    AGENT_TYPE = "proposal_drafting"
    PROMPT_NAME = "agent_proposal_drafting_v1"
    ALLOWED_TOOLS = ["fetch_proposal", "fetch_similar_proposals", "search_memory"]
    AUTHORITY_LEVEL = "draft"
    EXPECTED_OUTPUT_FIELDS = []  # free-text draft, not JSON

    async def _run_pipeline(self, contract: TaskContract, audit_trail: list[dict]) -> AgentResult:
        tool_results = await self._invoke_tools(contract, audit_trail)
        section = contract.input_data.get("section_name", "executive_summary")
        instructions = contract.input_data.get("instructions", "")
        result = await run_section_draft_graph(
            self._db,
            proposal_id=contract.proposal_id or "",
            section=section,
            user_query=instructions or contract.input_data.get("query", ""),
            provider=self._provider,
        )
        grounding = result.meta.get("grounding", {}) if result.meta else {}
        requires_approval = self.AGENT_TYPE in APPROVAL_REQUIRED_AGENTS
        status = "pending_approval" if requires_approval else "completed"
        return AgentResult(
            task_id=contract.task_id,
            agent_type=self.AGENT_TYPE,
            status=status,
            output={
                "content": result.content,
                "section_map": result.section_map,
                "mode": result.meta.get("mode", ""),
            },
            confidence=float(grounding.get("grounding_score", 0.0)),
            grounding_score=float(grounding.get("grounding_score", 0.0)),
            tools_used=[r.tool_name for r in tool_results],
            tokens_used=int(result.meta.get("input_tokens", 0)) + int(result.meta.get("output_tokens", 0)),
            requires_human_review=requires_approval,
        )

    def _build_prompt_vars(self, contract: TaskContract, tool_results: list[ToolResult]) -> dict:
        tool_map = {r.tool_name: r for r in tool_results}
        proposal = tool_map.get("fetch_proposal")
        similar = tool_map.get("fetch_similar_proposals")
        memory = tool_map.get("search_memory")

        pd = proposal.data if proposal and proposal.success else {}
        opp = pd.get("opportunity", {})

        return {
            "section_name": contract.input_data.get("section_name", "executive_summary"),
            "opportunity_title": opp.get("title", ""),
            "rfp_type": opp.get("rfp_type", ""),
            "deal_value_cr": opp.get("deal_value_cr", ""),
            "instructions": contract.input_data.get("instructions", ""),
            "proposal_context": str(pd),
            "similar_proposals": str(similar.data) if similar and similar.success else "",
            "memory_context": str(memory.data) if memory and memory.success else "",
        }

    def _tool_kwargs(self, tool_name: str, contract: TaskContract) -> dict:
        base = super()._tool_kwargs(tool_name, contract)
        if tool_name == "fetch_similar_proposals":
            return {"rfp_type": contract.input_data.get("rfp_type", ""), **base}
        if tool_name == "search_memory":
            return {"query": contract.input_data.get("section_name", "proposal section"), **base}
        return base
