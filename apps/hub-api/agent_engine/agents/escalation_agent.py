from agent_engine.agents.base import AgentBase
from agent_engine.execution.task_contract import TaskContract
from agent_engine.tools.base import ToolResult


class EscalationAgent(AgentBase):
    AGENT_TYPE = "escalation"
    PROMPT_NAME = "agent_escalation_v1"
    ALLOWED_TOOLS = ["assess_proposal_risk", "fetch_approval_history", "fetch_workflow_state", "search_memory"]
    AUTHORITY_LEVEL = "draft"
    EXPECTED_OUTPUT_FIELDS = ["escalation_required", "severity", "issue_summary", "suggested_actions"]

    def _build_prompt_vars(self, contract: TaskContract, tool_results: list[ToolResult]) -> dict:
        tool_map = {r.tool_name: r for r in tool_results}
        risk = tool_map.get("assess_proposal_risk")
        history = tool_map.get("fetch_approval_history")
        workflow = tool_map.get("fetch_workflow_state")
        memory = tool_map.get("search_memory")

        wd = workflow.data if workflow and workflow.success else {}
        pending = [a for a in wd.get("approvals", []) if a.get("status") == "pending"]

        return {
            "proposal_stage": wd.get("stage", contract.input_data.get("proposal_stage", "")),
            "opportunity_title": contract.input_data.get("opportunity_title", ""),
            "deal_value_cr": contract.input_data.get("deal_value_cr", ""),
            "pending_approvals": str(pending),
            "trigger_reason": contract.input_data.get("trigger_reason", "Manual escalation request"),
            "risk_profile": str(risk.data) if risk and risk.success else "",
            "approval_history": str(history.data) if history and history.success else "",
            "memory_context": str(memory.data) if memory and memory.success else "",
        }

    def _tool_kwargs(self, tool_name: str, contract: TaskContract) -> dict:
        base = super()._tool_kwargs(tool_name, contract)
        if tool_name == "search_memory":
            return {"query": "escalation precedent approval blocked", **base}
        return base
