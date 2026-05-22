from agent_engine.agents.base import AgentBase
from agent_engine.execution.task_contract import TaskContract
from agent_engine.tools.base import ToolResult


class TimelinePlanningAgent(AgentBase):
    AGENT_TYPE = "timeline_planning"
    PROMPT_NAME = "agent_timeline_planning_v1"
    ALLOWED_TOOLS = ["fetch_workflow_state", "list_smes", "search_memory"]
    AUTHORITY_LEVEL = "draft"
    EXPECTED_OUTPUT_FIELDS = ["milestones", "total_weeks", "critical_path", "assumptions"]

    def _build_prompt_vars(self, contract: TaskContract, tool_results: list[ToolResult]) -> dict:
        tool_map = {r.tool_name: r for r in tool_results}
        workflow = tool_map.get("fetch_workflow_state")
        smes = tool_map.get("list_smes")
        memory = tool_map.get("search_memory")

        sme_names = []
        if smes and smes.success:
            sme_names = [s.get("name", "") for s in smes.data.get("smes", [])]

        return {
            "rfp_type": contract.input_data.get("rfp_type", ""),
            "deal_value_cr": contract.input_data.get("deal_value_cr", ""),
            "proposal_stage": contract.input_data.get("proposal_stage", ""),
            "sme_notes": f"Available SMEs: {', '.join(sme_names)}" if sme_names else "No SME data available",
            "workflow_state": str(workflow.data) if workflow and workflow.success else "",
            "memory_context": str(memory.data) if memory and memory.success else "",
        }

    def _tool_kwargs(self, tool_name: str, contract: TaskContract) -> dict:
        base = super()._tool_kwargs(tool_name, contract)
        if tool_name == "search_memory":
            return {"query": f"timeline {contract.input_data.get('rfp_type', '')} delivery", **base}
        return base
