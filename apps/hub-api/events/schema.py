import uuid
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field


class BaseEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    correlation_id: str | None = None
    actor_id: str | None = None
    entity_id: str
    entity_type: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_json(self) -> str:
        return self.model_dump_json()


class ProposalTransitionedEvent(BaseEvent):
    event_type: Literal["proposal.transitioned"] = "proposal.transitioned"
    entity_type: Literal["proposal"] = "proposal"
    from_stage: str
    to_stage: str


class ApprovalDecisionEvent(BaseEvent):
    event_type: Literal["approval.decision"] = "approval.decision"
    entity_type: Literal["approval"] = "approval"
    proposal_id: str
    stage: str | None = None
    status: str


class SlaBreachEvent(BaseEvent):
    event_type: Literal["sla.breach"] = "sla.breach"
    entity_type: Literal["opportunity"] = "opportunity"
    stage: str
    overdue_hours: float


class SmeAssignedEvent(BaseEvent):
    event_type: Literal["sme.assigned"] = "sme.assigned"
    entity_type: Literal["proposal"] = "proposal"
    sme_id: str
    sme_name: str
    rfp_type: str
