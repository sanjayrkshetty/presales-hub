from agent_engine.agents.base import AgentBase
from agent_engine.execution.task_contract import TaskContract
from agent_engine.tools.base import ToolResult


class SMECoordinationAgent(AgentBase):
    AGENT_TYPE = "sme_coordination"
    PROMPT_NAME = "agent_sme_coordination_v1"
    ALLOWED_TOOLS = ["match_sme_to_requirements", "list_smes", "search_memory"]
    AUTHORITY_LEVEL = "recommend"
    EXPECTED_OUTPUT_FIELDS = ["recommended_smes", "coverage_gaps", "coordination_notes"]

    def _build_prompt_vars(self, contract: TaskContract, tool_results: list[ToolResult]) -> dict:
        tool_map = {r.tool_name: r for r in tool_results}
        matches = tool_map.get("match_sme_to_requirements")
        memory = tool_map.get("search_memory")

        return {
            "opportunity_title": contract.input_data.get("opportunity_title", ""),
            "rfp_type": contract.input_data.get("rfp_type", ""),
            "key_requirements": str(contract.input_data.get("requirements", [])),
            "sme_matches": str(matches.data) if matches and matches.success else "",
            "memory_context": str(memory.data) if memory and memory.success else "",
        }

    def _tool_kwargs(self, tool_name: str, contract: TaskContract) -> dict:
        base = super()._tool_kwargs(tool_name, contract)
        if tool_name == "match_sme_to_requirements":
            return {"requirements": contract.input_data.get("requirements", []), **base}
        if tool_name == "search_memory":
            return {"query": f"SME {contract.input_data.get('rfp_type', '')}", **base}
        return base
