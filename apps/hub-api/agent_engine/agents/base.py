from __future__ import annotations

import asyncio
import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional

from agent_engine.config import (
    AGENT_MAX_TOOL_CALLS,
    APPROVAL_REQUIRED_AGENTS,
    AGENT_TIMEOUTS,
    AGENT_DEFAULT_TIMEOUT_SECONDS,
)
from agent_engine.execution.task_contract import AgentResult, TaskContract
from agent_engine.tools.base import AgentTool, ToolResult
from copilot_engine.orchestration.copilot_runner import CopilotRunner

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from copilot_engine.providers.base import LLMProvider


class AgentBase(ABC):
    AGENT_TYPE: str = ""
    PROMPT_NAME: str = ""
    ALLOWED_TOOLS: list[str] = []
    AUTHORITY_LEVEL: str = "recommend"
    EXPECTED_OUTPUT_FIELDS: list[str] = []

    def __init__(
        self,
        db: "Session",
        provider: "LLMProvider",
        tools: Optional[list[AgentTool]] = None,
    ) -> None:
        self._db = db
        self._provider = provider
        self._tools: dict[str, AgentTool] = {}
        for tool in (tools or []):
            if tool.name in self.ALLOWED_TOOLS:
                self._tools[tool.name] = tool
        self._runner = CopilotRunner(db=db, provider=provider)

    # ------------------------------------------------------------------ #
    # Public entry point                                                   #
    # ------------------------------------------------------------------ #

    async def execute(self, contract: TaskContract) -> AgentResult:
        start = time.monotonic()
        audit_trail: list[dict] = []
        timeout = AGENT_TIMEOUTS.get(self.AGENT_TYPE, AGENT_DEFAULT_TIMEOUT_SECONDS)

        try:
            result = await asyncio.wait_for(
                self._run_pipeline(contract, audit_trail),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            return AgentResult(
                task_id=contract.task_id,
                agent_type=self.AGENT_TYPE,
                status="timeout",
                output={},
                error=f"Agent timed out after {timeout}s",
                latency_ms=(time.monotonic() - start) * 1000,
                audit_trail=audit_trail,
            )
        except Exception as exc:
            return AgentResult(
                task_id=contract.task_id,
                agent_type=self.AGENT_TYPE,
                status="failed",
                output={},
                error=str(exc),
                latency_ms=(time.monotonic() - start) * 1000,
                audit_trail=audit_trail,
            )

        result.latency_ms = (time.monotonic() - start) * 1000
        result.audit_trail = audit_trail
        return result

    # ------------------------------------------------------------------ #
    # Internal pipeline                                                    #
    # ------------------------------------------------------------------ #

    async def _run_pipeline(
        self, contract: TaskContract, audit_trail: list[dict]
    ) -> AgentResult:
        # 1. Run allowed tools (bounded by AGENT_MAX_TOOL_CALLS)
        tool_results = await self._invoke_tools(contract, audit_trail)

        # 2. Build prompt vars (agent-specific)
        prompt_vars = self._build_prompt_vars(contract, tool_results)

        # 3. Delegate to CopilotRunner (gets grounding/safety/eval for free)
        copilot_resp = await self._runner.run(
            prompt_name=self.PROMPT_NAME,
            prompt_vars=prompt_vars,
            user_query=contract.input_data.get("query", ""),
            expected_json_fields=self.EXPECTED_OUTPUT_FIELDS,
        )

        requires_approval = self.AGENT_TYPE in APPROVAL_REQUIRED_AGENTS
        status = "pending_approval" if requires_approval else "completed"

        return AgentResult(
            task_id=contract.task_id,
            agent_type=self.AGENT_TYPE,
            status=status,
            output={"content": copilot_resp.content},
            confidence=copilot_resp.evaluation.get("quality_score", 0.0),
            grounding_score=copilot_resp.grounding.get("score", 0.0),
            tools_used=[r.tool_name for r in tool_results],
            tokens_used=copilot_resp.input_tokens + copilot_resp.output_tokens,
            requires_human_review=requires_approval,
        )

    async def _invoke_tools(
        self, contract: TaskContract, audit_trail: list[dict]
    ) -> list[ToolResult]:
        results: list[ToolResult] = []
        call_count = 0
        for tool_name in self.ALLOWED_TOOLS:
            if call_count >= AGENT_MAX_TOOL_CALLS:
                break
            tool = self._tools.get(tool_name)
            if tool is None:
                continue
            kwargs = self._tool_kwargs(tool_name, contract)
            result = await tool.safe_execute(**kwargs)
            audit_trail.append(result.to_audit_entry())
            results.append(result)
            call_count += 1
        return results

    # ------------------------------------------------------------------ #
    # Override hooks                                                       #
    # ------------------------------------------------------------------ #

    @abstractmethod
    def _build_prompt_vars(
        self,
        contract: TaskContract,
        tool_results: list[ToolResult],
    ) -> dict:
        """Return kwargs dict passed to PromptTemplate.render_*."""
        ...

    def _tool_kwargs(self, tool_name: str, contract: TaskContract) -> dict:
        """Override to pass custom kwargs to specific tools."""
        return {
            "proposal_id": contract.proposal_id,
            "opportunity_id": contract.opportunity_id,
            "input_data": contract.input_data,
            "db": self._db,
        }
