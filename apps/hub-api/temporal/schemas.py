"""
Dataclasses for Temporal workflow and activity I/O.

All types must be JSON-serializable (Temporal uses its default JSON codec).
Use dataclasses (not Pydantic) so temporalio can encode/decode them without
a custom codec.
"""
from dataclasses import dataclass, field
from typing import Optional

TASK_QUEUE = "presales-hub"

TERMINAL_STAGES = frozenset({"closed_won", "closed_lost"})
PARALLEL_REVIEW_STAGES = frozenset({"technical_review", "security_review", "delivery_review"})


# ── Workflow inputs ────────────────────────────────────────────────────────────

@dataclass
class ProposalWorkflowInput:
    proposal_id: str
    correlation_id: str = ""
    initial_stage: str = "intake"


@dataclass
class ParallelReviewInput:
    proposal_id: str
    timeout_hours: int = 72
    correlation_id: str = ""


@dataclass
class SlaInput:
    proposal_id: str
    opportunity_id: str
    stage: str
    sla_hours: int
    escalate_to_role: Optional[str] = None
    correlation_id: str = ""


# ── Activity inputs ────────────────────────────────────────────────────────────

@dataclass
class TransitionInput:
    proposal_id: str
    from_stage: str
    to_stage: str
    actor_id: Optional[str] = None
    note: Optional[str] = None
    correlation_id: str = ""


@dataclass
class TransitionResult:
    success: bool
    stage: str
    error: Optional[str] = None


@dataclass
class InitParallelApprovalsInput:
    proposal_id: str
    review_stages: list = field(default_factory=list)
    correlation_id: str = ""


@dataclass
class ApprovalActivityInput:
    approval_id: str
    proposal_id: str
    stage: Optional[str]
    status: str
    actor_id: Optional[str] = None
    decision_note: Optional[str] = None


@dataclass
class EventInput:
    event_type: str
    entity_id: str
    entity_type: str
    metadata: dict = field(default_factory=dict)
    actor_id: Optional[str] = None
    correlation_id: str = ""


@dataclass
class EscalationInput:
    proposal_id: str
    opportunity_id: str
    stage: str
    escalate_to_role: Optional[str]
    overdue_hours: float = 0.0
    correlation_id: str = ""


# ── Workflow intermediate types ────────────────────────────────────────────────

@dataclass
class ReviewDecision:
    stage: str
    status: str
    actor_id: Optional[str] = None
    note: Optional[str] = None


@dataclass
class ParallelReviewResult:
    all_approved: bool
    decisions: dict = field(default_factory=dict)
