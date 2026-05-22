from agent_engine.agents.base import AgentBase
from agent_engine.execution.task_contract import TaskContract
from agent_engine.tools.base import ToolResult


class SolutionArchitectureAgent(AgentBase):
    AGENT_TYPE = "solution_architecture"
    PROMPT_NAME = "agent_solution_architecture_v1"
    ALLOWED_TOOLS = ["fetch_compliance_requirements", "summarize_opportunity_metrics", "search_memory"]
    AUTHORITY_LEVEL = "recommend"
    EXPECTED_OUTPUT_FIELDS = ["architecture_layers", "integration_points", "phasing_suggestion"]

    def _build_prompt_vars(self, contract: TaskContract, tool_results: list[ToolResult]) -> dict:
        tool_map = {r.tool_name: r for r in tool_results}
        compliance = tool_map.get("fetch_compliance_requirements")
        metrics = tool_map.get("summarize_opportunity_metrics")
        memory = tool_map.get("search_memory")

        md = metrics.data if metrics and metrics.success else {}

        return {
            "rfp_type": contract.input_data.get("rfp_type", md.get("rfp_type", "")),
            "client_context": contract.input_data.get("client_context", md.get("client_name", "")),
            "key_requirements": str(contract.input_data.get("requirements", [])),
            "deal_value_cr": md.get("deal_value_cr", contract.input_data.get("deal_value_cr", "")),
            "compliance_requirements": str(compliance.data) if compliance and compliance.success else "",
            "memory_context": str(memory.data) if memory and memory.success else "",
        }

    def _tool_kwargs(self, tool_name: str, contract: TaskContract) -> dict:
        base = super()._tool_kwargs(tool_name, contract)
        if tool_name == "fetch_compliance_requirements":
            return {"rfp_type": contract.input_data.get("rfp_type", "")}
        if tool_name == "summarize_opportunity_metrics":
            return {"opportunity_id": contract.opportunity_id or "", **base}
        if tool_name == "search_memory":
            return {"query": f"solution architecture {contract.input_data.get('rfp_type', '')}", **base}
        return base
