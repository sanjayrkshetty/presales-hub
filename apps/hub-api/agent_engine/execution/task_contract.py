from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from agent_engine.config import AGENT_DEFAULT_TIMEOUT_SECONDS, AGENT_MAX_RETRIES


@dataclass
class TaskContract:
    agent_type: str
    input_data: dict
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    proposal_id: Optional[str] = None
    opportunity_id: Optional[str] = None
    requires_approval: bool = False
    authority_level: str = "recommend"
    timeout_seconds: int = AGENT_DEFAULT_TIMEOUT_SECONDS
    retry_limit: int = AGENT_MAX_RETRIES
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "agent_type": self.agent_type,
            "proposal_id": self.proposal_id,
            "opportunity_id": self.opportunity_id,
            "input_data": self.input_data,
            "requires_approval": self.requires_approval,
            "authority_level": self.authority_level,
            "timeout_seconds": self.timeout_seconds,
            "retry_limit": self.retry_limit,
            "correlation_id": self.correlation_id,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TaskContract":
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        return cls(
            task_id=data.get("task_id", str(uuid.uuid4())),
            agent_type=data["agent_type"],
            proposal_id=data.get("proposal_id"),
            opportunity_id=data.get("opportunity_id"),
            input_data=data.get("input_data", {}),
            requires_approval=data.get("requires_approval", False),
            authority_level=data.get("authority_level", "recommend"),
            timeout_seconds=data.get("timeout_seconds", AGENT_DEFAULT_TIMEOUT_SECONDS),
            retry_limit=data.get("retry_limit", AGENT_MAX_RETRIES),
            correlation_id=data.get("correlation_id", str(uuid.uuid4())),
            created_at=created_at or datetime.now(timezone.utc),
        )


@dataclass
class AgentResult:
    task_id: str
    agent_type: str
    status: str  # completed | failed | pending_approval | timeout
    output: dict
    confidence: float = 0.0
    grounding_score: float = 0.0
    tools_used: list[str] = field(default_factory=list)
    tokens_used: int = 0
    latency_ms: float = 0.0
    requires_human_review: bool = False
    audit_trail: list[dict] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "agent_type": self.agent_type,
            "status": self.status,
            "output": self.output,
            "confidence": self.confidence,
            "grounding_score": self.grounding_score,
            "tools_used": self.tools_used,
            "tokens_used": self.tokens_used,
            "latency_ms": self.latency_ms,
            "requires_human_review": self.requires_human_review,
            "audit_trail": self.audit_trail,
            "error": self.error,
        }
