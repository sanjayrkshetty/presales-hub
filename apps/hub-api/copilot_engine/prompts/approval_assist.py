"""Approval assistant prompt — explain and analyze approval decisions."""
from copilot_engine.prompts.registry import PromptTemplate, registry

_SYSTEM = """\
You are a presales governance analyst reviewing approval decisions.
Explain rationale, surface anomalies, and compare against historical patterns.

RULE: Only state what is supported by the approval data below. Do not fabricate rationale.
RULE: Cite historical approvals as [Approval: approval-id] when making comparisons.

Approval data:
{approval_context}

Historical approval patterns from memory:
{memory_context}
"""

_USER = """\
Analyze approval {approval_id} and provide:

1. RATIONALE_SUMMARY — why was this approved/rejected based on decision notes
2. RISK_AREAS — risks identified or flagged in the decision
3. ANOMALY_FLAGS — anything unusual about timing, actor, or approval pattern
4. HISTORICAL_COMPARISON — how this compares to similar historical approvals
5. RECOMMENDED_FOLLOW_UP — what should happen next in the workflow

Respond in JSON: {{rationale_summary, risk_areas, anomaly_flags, historical_comparison, recommended_follow_up}}.
"""

registry.register(PromptTemplate(
    name="approval_assist_v1",
    version="1.0",
    system_template=_SYSTEM,
    user_template=_USER,
    description="Explain and analyze an approval decision with historical context",
    input_vars=["approval_context", "memory_context", "approval_id"],
    copilot_type="approval",
))
