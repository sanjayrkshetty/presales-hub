from agent_engine.agents.base import AgentBase
from agent_engine.execution.task_contract import TaskContract
from agent_engine.tools.base import ToolResult


class ExecutiveBriefingAgent(AgentBase):
    AGENT_TYPE = "executive_briefing"
    PROMPT_NAME = "agent_executive_briefing_v1"
    ALLOWED_TOOLS = ["fetch_proposal", "fetch_workflow_state", "assess_proposal_risk", "search_memory"]
    AUTHORITY_LEVEL = "recommend"
    EXPECTED_OUTPUT_FIELDS = ["headline", "deal_snapshot", "key_risks", "decisions_needed"]

    def _build_prompt_vars(self, contract: TaskContract, tool_results: list[ToolResult]) -> dict:
        tool_map = {r.tool_name: r for r in tool_results}
        proposal = tool_map.get("fetch_proposal")
        workflow = tool_map.get("fetch_workflow_state")
        risk = tool_map.get("assess_proposal_risk")
        memory = tool_map.get("search_memory")

        pd = proposal.data if proposal and proposal.success else {}
        opp = pd.get("opportunity", {})
        wd = workflow.data if workflow and workflow.success else {}
        rd = risk.data if risk and risk.success else {}

        return {
            "opportunity_title": opp.get("title", ""),
            "proposal_stage": pd.get("stage", ""),
            "deal_value_cr": opp.get("deal_value_cr", ""),
            "risk_level": rd.get("risk_level", "unknown"),
            "pending_approvals": str(wd.get("approvals", [])),
            "workflow_state": str(wd),
            "memory_context": str(memory.data) if memory and memory.success else "",
        }
