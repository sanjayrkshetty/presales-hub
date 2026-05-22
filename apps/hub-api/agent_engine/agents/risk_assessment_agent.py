from agent_engine.agents.base import AgentBase
from agent_engine.execution.task_contract import TaskContract
from agent_engine.tools.base import ToolResult


class RiskAssessmentAgent(AgentBase):
    AGENT_TYPE = "risk_assessment"
    PROMPT_NAME = "agent_risk_assessment_v1"
    ALLOWED_TOOLS = ["assess_proposal_risk", "fetch_compliance_requirements", "search_memory"]
    AUTHORITY_LEVEL = "recommend"
    EXPECTED_OUTPUT_FIELDS = ["risk_register", "overall_risk_level", "recommended_actions"]

    def _build_prompt_vars(self, contract: TaskContract, tool_results: list[ToolResult]) -> dict:
        tool_map = {r.tool_name: r for r in tool_results}
        risk = tool_map.get("assess_proposal_risk")
        compliance = tool_map.get("fetch_compliance_requirements")
        memory = tool_map.get("search_memory")

        return {
            "stage": contract.input_data.get("stage", ""),
            "opportunity_title": contract.input_data.get("opportunity_title", ""),
            "rfp_type": contract.input_data.get("rfp_type", ""),
            "deal_value_cr": contract.input_data.get("deal_value_cr", ""),
            "risk_profile": str(risk.data) if risk and risk.success else "",
            "compliance_requirements": str(compliance.data) if compliance and compliance.success else "",
            "memory_context": str(memory.data) if memory and memory.success else "",
        }

    def _tool_kwargs(self, tool_name: str, contract: TaskContract) -> dict:
        base = super()._tool_kwargs(tool_name, contract)
        if tool_name == "fetch_compliance_requirements":
            return {"rfp_type": contract.input_data.get("rfp_type", "")}
        if tool_name == "search_memory":
            return {"query": f"risk {contract.input_data.get('rfp_type', '')}", **base}
        return base
