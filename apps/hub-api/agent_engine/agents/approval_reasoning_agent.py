from agent_engine.agents.base import AgentBase
from agent_engine.execution.task_contract import TaskContract
from agent_engine.tools.base import ToolResult


class ApprovalReasoningAgent(AgentBase):
    AGENT_TYPE = "approval_reasoning"
    PROMPT_NAME = "agent_approval_reasoning_v1"
    ALLOWED_TOOLS = ["fetch_approval", "fetch_approval_history", "search_memory"]
    AUTHORITY_LEVEL = "recommend"
    EXPECTED_OUTPUT_FIELDS = ["recommendation", "rationale", "conditions", "risk_summary"]

    def _build_prompt_vars(self, contract: TaskContract, tool_results: list[ToolResult]) -> dict:
        tool_map = {r.tool_name: r for r in tool_results}
        approval = tool_map.get("fetch_approval")
        history = tool_map.get("fetch_approval_history")
        memory = tool_map.get("search_memory")

        ad = approval.data if approval and approval.success else {}

        return {
            "approval_id": ad.get("id", contract.input_data.get("approval_id", "")),
            "approval_stage": ad.get("stage", ""),
            "approval_status": ad.get("status", ""),
            "proposal_stage": contract.input_data.get("proposal_stage", ""),
            "approval_notes": ad.get("notes", ""),
            "approval_history": str(history.data) if history and history.success else "",
            "memory_context": str(memory.data) if memory and memory.success else "",
        }

    def _tool_kwargs(self, tool_name: str, contract: TaskContract) -> dict:
        base = super()._tool_kwargs(tool_name, contract)
        if tool_name == "fetch_approval":
            return {"approval_id": contract.input_data.get("approval_id", ""), **base}
        if tool_name == "search_memory":
            return {"query": "approval decision precedent", **base}
        return base
