from agent_engine.agents.base import AgentBase
from agent_engine.execution.task_contract import TaskContract
from agent_engine.tools.base import ToolResult


class RFPAnalysisAgent(AgentBase):
    AGENT_TYPE = "rfp_analysis"
    PROMPT_NAME = "agent_rfp_analysis_v1"
    ALLOWED_TOOLS = ["extract_rfp_requirements", "compute_win_rate", "search_memory"]
    AUTHORITY_LEVEL = "recommend"
    EXPECTED_OUTPUT_FIELDS = ["requirements", "compliance_flags", "risk_factors", "recommended_approach"]

    def _build_prompt_vars(self, contract: TaskContract, tool_results: list[ToolResult]) -> dict:
        tool_map = {r.tool_name: r for r in tool_results}
        extracted = tool_map.get("extract_rfp_requirements")
        win_rate = tool_map.get("compute_win_rate")
        memory = tool_map.get("search_memory")

        return {
            "rfp_text": contract.input_data.get("rfp_text", ""),
            "extracted_categories": str(extracted.data) if extracted and extracted.success else "",
            "win_rate": str(win_rate.data.get("win_rate", "unknown")) if win_rate and win_rate.success else "unknown",
            "tool_context": f"extract_rfp_requirements: {extracted.data if extracted else None}",
            "memory_context": str(memory.data) if memory and memory.success else "",
        }

    def _tool_kwargs(self, tool_name: str, contract: TaskContract) -> dict:
        base = super()._tool_kwargs(tool_name, contract)
        if tool_name == "extract_rfp_requirements":
            return {"rfp_text": contract.input_data.get("rfp_text", "")}
        if tool_name == "compute_win_rate":
            return {"rfp_type": contract.input_data.get("rfp_type", ""), **base}
        if tool_name == "search_memory":
            return {"query": contract.input_data.get("rfp_text", "")[:500], **base}
        return base
