from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class AgentMemoryEntry:
    task_id: str
    agent_type: str
    status: str
    output_summary: str
    grounding_score: float
    confidence: float
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: Optional[str] = None


class AgentMemoryStore:
    """In-process store for agent task history within a session."""

    def __init__(self) -> None:
        self._store: dict[str, AgentMemoryEntry] = {}

    def record(
        self,
        task_id: str,
        agent_type: str,
        status: str,
        output: dict,
        grounding_score: float,
        confidence: float,
        correlation_id: Optional[str] = None,
    ) -> None:
        summary = str(output)[:200]
        self._store[task_id] = AgentMemoryEntry(
            task_id=task_id,
            agent_type=agent_type,
            status=status,
            output_summary=summary,
            grounding_score=grounding_score,
            confidence=confidence,
            correlation_id=correlation_id,
        )

    def get(self, task_id: str) -> Optional[AgentMemoryEntry]:
        return self._store.get(task_id)

    def get_by_correlation(self, correlation_id: str) -> list[AgentMemoryEntry]:
        return [e for e in self._store.values() if e.correlation_id == correlation_id]

    def recent(self, limit: int = 10) -> list[AgentMemoryEntry]:
        entries = sorted(self._store.values(), key=lambda e: e.created_at, reverse=True)
        return entries[:limit]

    def clear(self) -> None:
        self._store.clear()


# Process-level singleton — replace with distributed store (Redis) for production
_agent_memory = AgentMemoryStore()


def get_agent_memory() -> AgentMemoryStore:
    return _agent_memory
