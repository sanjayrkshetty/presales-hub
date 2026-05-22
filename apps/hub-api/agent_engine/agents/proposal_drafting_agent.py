from agent_engine.agents.base import AgentBase
from agent_engine.execution.task_contract import TaskContract
from agent_engine.tools.base import ToolResult


class ProposalDraftingAgent(AgentBase):
    AGENT_TYPE = "proposal_drafting"
    PROMPT_NAME = "agent_proposal_drafting_v1"
    ALLOWED_TOOLS = ["fetch_proposal", "fetch_similar_proposals", "search_memory"]
    AUTHORITY_LEVEL = "draft"
    EXPECTED_OUTPUT_FIELDS = []  # free-text draft, not JSON

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
