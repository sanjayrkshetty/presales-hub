"""Deterministic mock LLM provider for tests and dev-without-API."""
import json
from copilot_engine.providers.base import LLMProvider, LLMResponse

# Canned JSON stubs keyed by prompt name prefix (first word)
_STUBS: dict[str, dict] = {
    "rfp": {
        "requirements": ["Deliver SOC 2 Type II audit"],
        "compliance": ["SOC 2", "ISO 27001"],
        "risks": ["Tight 90-day timeline"],
        "deliverables": ["Audit report", "Remediation roadmap"],
        "stakeholders": ["CISO", "Procurement"],
        "scope_summary": "Security audit and compliance assessment.",
    },
    "proposal": (
        "## Executive Summary\n\nThis proposal addresses the client's requirements. "
        "[Source: proposal-mock-001] Similar historical proposal referenced for scope.\n\n"
        "[NEEDS_INPUT: Confirm headcount for delivery team]"
    ),
    "executive": {
        "status_summary": "Proposal in technical_review, 5 days active.",
        "risks": [{"factor": "Timeline", "severity": "HIGH"}],
        "blockers": ["Pending security review approval"],
        "recommended_actions": ["Escalate to CISO", "Assign SME"],
        "approval_status": {"pending": 2, "approved": 1},
    },
    "approval": {
        "rationale_summary": "Approved based on risk coverage and timeline feasibility.",
        "risk_areas": ["Scope definition"],
        "anomaly_flags": [],
        "historical_comparison": "Consistent with similar SOC 2 approvals.",
        "recommended_follow_up": "Proceed to finance review.",
    },
    "compliance": {
        "requirements_coverage": [],
        "critical_gaps": [],
        "compliance_score": 85,
        "recommendations": ["Add HIPAA section"],
    },
    "risk": {
        "risks": [{"factor": "timeline", "explanation": "Short window", "severity": "HIGH", "mitigation": "Add buffer"}],
        "overall_risk_level": "MEDIUM",
        "top_priority_action": "Confirm delivery capacity",
    },
    "sme": {
        "recommendations": [{"sme_id": "s1", "name": "Mock SME", "rationale": "PCI expertise", "availability_note": "Available", "gaps": []}],
        "coverage_analysis": "All requirements covered",
        "staffing_risk": "LOW",
    },
    "solution": {
        "recommended_approach": "Zero-trust architecture with layered controls. [Pattern: mock-pattern-001]",
        "key_components": ["IAM", "SIEM", "EDR"],
        "reusable_patterns": ["Zero-trust baseline"],
        "gaps_to_discover": ["Cloud footprint scope"],
        "risks": ["Integration complexity"],
    },
    "workflow": {
        "current_status": "In technical_review",
        "next_steps": ["Complete parallel approvals", "Schedule finance review"],
        "blockers": [],
        "risk_factors": ["SLA approaching 80%"],
        "timeline_assessment": "On track",
    },
}


class MockLLMProvider(LLMProvider):
    """Returns deterministic JSON stubs. No API calls."""

    def __init__(self, fixed_response: str = ""):
        self._fixed = fixed_response

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return "mock-v1"

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        if self._fixed:
            content = self._fixed
        else:
            # Pick stub by matching first keyword in system prompt
            content = self._pick_stub(system_prompt + " " + user_prompt)

        word_count = len((system_prompt + user_prompt).split())
        return LLMResponse(
            content=content,
            model="mock-v1",
            provider="mock",
            input_tokens=word_count,
            output_tokens=len(content.split()),
            latency_ms=1.0,
        )

    @staticmethod
    def _pick_stub(text: str) -> str:
        lower = text.lower()
        for key, stub in _STUBS.items():
            if key in lower:
                if isinstance(stub, str):
                    return stub
                return json.dumps(stub)
        return json.dumps({"result": "Mock copilot response.", "status": "ok"})
