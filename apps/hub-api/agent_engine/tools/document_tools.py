from __future__ import annotations

from typing import TYPE_CHECKING

from agent_engine.tools.base import AgentTool, ToolResult

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class ExtractRFPRequirementsTool(AgentTool):
    name = "extract_rfp_requirements"
    description = "Parse raw RFP text and extract structured requirement categories."

    _CATEGORY_KEYWORDS = {
        "security": ["encrypt", "firewall", "vulnerability", "pen test", "soc", "siem", "iam"],
        "compliance": ["iso", "pci", "hipaa", "gdpr", "audit", "certif"],
        "delivery": ["timeline", "milestone", "phase", "delivery", "go-live", "deadline"],
        "commercials": ["price", "cost", "budget", "commercial", "rate", "cr", "lakh"],
        "technical": ["architecture", "integration", "api", "cloud", "infra", "stack", "sla"],
    }

    async def execute(self, rfp_text: str, **_) -> ToolResult:
        if not rfp_text:
            return ToolResult(tool_name=self.name, success=False, error="rfp_text required")
        text_lower = rfp_text.lower()
        categorized: dict[str, list[str]] = {cat: [] for cat in self._CATEGORY_KEYWORDS}

        for line in rfp_text.splitlines():
            line_lower = line.lower().strip()
            if not line_lower:
                continue
            for cat, keywords in self._CATEGORY_KEYWORDS.items():
                if any(kw in line_lower for kw in keywords):
                    categorized[cat].append(line.strip())

        non_empty = {k: v for k, v in categorized.items() if v}
        return ToolResult(
            tool_name=self.name,
            success=True,
            data={"categories": non_empty, "total_lines": len(rfp_text.splitlines())},
        )


class SummarizeDocumentTool(AgentTool):
    name = "summarize_document"
    description = "Return a character-count and section-key summary of a document dict."

    async def execute(self, content: dict, **_) -> ToolResult:
        if not isinstance(content, dict):
            return ToolResult(tool_name=self.name, success=False, error="content must be a dict")
        section_summary = {
            k: len(str(v)) for k, v in content.items()
        }
        total_chars = sum(section_summary.values())
        return ToolResult(
            tool_name=self.name,
            success=True,
            data={"sections": section_summary, "total_chars": total_chars},
        )
