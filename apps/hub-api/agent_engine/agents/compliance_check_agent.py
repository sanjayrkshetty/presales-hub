from agent_engine.agents.base import AgentBase
from agent_engine.execution.task_contract import TaskContract
from agent_engine.tools.base import ToolResult


class ComplianceCheckAgent(AgentBase):
    AGENT_TYPE = "compliance_check"
    PROMPT_NAME = "agent_compliance_check_v1"
    ALLOWED_TOOLS = ["fetch_proposal", "fetch_compliance_requirements", "summarize_document", "search_memory"]
    AUTHORITY_LEVEL = "recommend"
    EXPECTED_OUTPUT_FIELDS = ["covered", "gaps", "coverage_score", "recommended_additions"]

    def _build_prompt_vars(self, contract: TaskContract, tool_results: list[ToolResult]) -> dict:
        tool_map = {r.tool_name: r for r in tool_results}
        proposal = tool_map.get("fetch_proposal")
        compliance = tool_map.get("fetch_compliance_requirements")
        summary = tool_map.get("summarize_document")
        memory = tool_map.get("search_memory")

        pd = proposal.data if proposal and proposal.success else {}
        opp = pd.get("opportunity", {})
        content = pd.get("content", {})

        return {
            "rfp_type": opp.get("rfp_type", contract.input_data.get("rfp_type", "")),
            "proposal_sections": str(list(content.keys())),
            "content_summary": str(summary.data) if summary and summary.success else str(content)[:500],
            "framework_requirements": str(compliance.data) if compliance and compliance.success else "",
            "memory_context": str(memory.data) if memory and memory.success else "",
        }

    def _tool_kwargs(self, tool_name: str, contract: TaskContract) -> dict:
        base = super()._tool_kwargs(tool_name, contract)
        if tool_name == "fetch_compliance_requirements":
            return {"rfp_type": contract.input_data.get("rfp_type", "")}
        if tool_name == "summarize_document":
            return {"content": contract.input_data.get("content", {})}
        if tool_name == "search_memory":
            return {"query": f"compliance {contract.input_data.get('rfp_type', '')}", **base}
        return base
