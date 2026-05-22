from __future__ import annotations

import re
from typing import TYPE_CHECKING

from agent_engine.tools.base import AgentTool, ToolResult

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

_HIGH_RISK_KEYWORDS = [
    "government", "banking", "healthcare", "critical infrastructure",
    "pci dss", "hipaa", "gdpr", "iso 27001",
]


class AssessProposalRiskTool(AgentTool):
    name = "assess_proposal_risk"
    description = "Score proposal risk based on deal value, stage, and compliance type."

    async def execute(self, proposal_id: str, db: "Session", **_) -> ToolResult:
        if not proposal_id:
            return ToolResult(tool_name=self.name, success=False, error="proposal_id required")
        from models import Proposal
        from models.opportunity import Opportunity
        proposal = db.query(Proposal).filter(Proposal.id == proposal_id).first()
        if not proposal:
            return ToolResult(tool_name=self.name, success=False, error=f"Proposal {proposal_id} not found")
        opp = db.query(Opportunity).filter(Opportunity.id == proposal.opportunity_id).first()

        risk_flags: list[str] = []
        risk_score = 0.0

        if opp and opp.deal_value_cr:
            val = float(opp.deal_value_cr)
            if val >= 5:
                risk_flags.append("High deal value (≥5 Cr)")
                risk_score += 0.3
            elif val >= 1:
                risk_score += 0.1

        if opp and opp.rfp_type:
            rfp_lower = opp.rfp_type.lower()
            matched = [kw for kw in _HIGH_RISK_KEYWORDS if kw in rfp_lower]
            if matched:
                risk_flags.append(f"Regulated domain: {', '.join(matched)}")
                risk_score += 0.2

        content_text = " ".join(str(v) for v in (proposal.content or {}).values()).lower()
        penalty_keywords = ["penalty", "sla breach", "non-compliance", "fine"]
        if any(k in content_text for k in penalty_keywords):
            risk_flags.append("Penalty/SLA clauses detected in content")
            risk_score += 0.2

        risk_score = min(1.0, risk_score)
        level = "high" if risk_score >= 0.5 else "medium" if risk_score >= 0.2 else "low"

        return ToolResult(
            tool_name=self.name,
            success=True,
            data={"risk_score": round(risk_score, 2), "risk_level": level, "flags": risk_flags},
        )


class FetchComplianceRequirementsTool(AgentTool):
    name = "fetch_compliance_requirements"
    description = "Return known compliance requirements for a given framework type."

    _REQUIREMENTS: dict[str, list[str]] = {
        "pci dss": [
            "Cardholder data environment scoping",
            "Network segmentation",
            "Encryption of data in transit and at rest",
            "Vulnerability management programme",
            "Access control and least privilege",
        ],
        "iso 27001": [
            "Information security risk assessment",
            "Statement of Applicability (SoA)",
            "Asset management controls",
            "Incident management procedure",
            "Internal audit programme",
        ],
        "hipaa": [
            "Protected Health Information (PHI) safeguards",
            "Business Associate Agreements",
            "Breach notification procedures",
            "Minimum necessary standard",
        ],
        "soc 2": [
            "Trust Service Criteria mapping",
            "Change management controls",
            "Logical access controls",
            "System monitoring",
        ],
    }

    async def execute(self, rfp_type: str, **_) -> ToolResult:
        key = rfp_type.lower().strip()
        for framework, reqs in self._REQUIREMENTS.items():
            if framework in key or key in framework:
                return ToolResult(
                    tool_name=self.name,
                    success=True,
                    data={"framework": framework, "requirements": reqs},
                )
        return ToolResult(
            tool_name=self.name,
            success=True,
            data={"framework": rfp_type, "requirements": []},
        )
