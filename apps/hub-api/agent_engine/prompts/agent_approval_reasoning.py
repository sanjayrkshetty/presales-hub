"""Agent prompt: approval reasoning and decision support."""
from copilot_engine.prompts.registry import PromptTemplate, registry

_SYSTEM = """\
You are an approval reasoning agent. Analyse approval history and proposal state
to recommend an approval decision with clear rationale.

AUTHORITY: recommend — you inform the approver, you do not approve on their behalf.

Approval history:
{approval_history}

Institutional memory:
{memory_context}
"""

_USER = """\
Approval ID: {approval_id} | Stage: {approval_stage} | Status: {approval_status}
Proposal stage: {proposal_stage}
Notes on record: {approval_notes}

Produce a JSON response with keys:
- recommendation ("approve"|"reject"|"escalate"|"defer")
- rationale (string — reasoning grounded in the approval history)
- conditions (list of strings — conditions if recommending approval)
- risk_summary (string)
- precedent_note (string — relevant past approvals from memory, if any)
"""

registry.register(PromptTemplate(
    name="agent_approval_reasoning_v1",
    version="1.0",
    system_template=_SYSTEM,
    user_template=_USER,
    description="Agent-level approval decision reasoning",
    input_vars=[
        "approval_id", "approval_stage", "approval_status", "proposal_stage",
        "approval_notes", "approval_history", "memory_context",
    ],
    copilot_type="approval",
))
