"""
In-process ephemeral session memory for multi-turn copilot interactions.

Sessions expire after SESSION_TTL_SECONDS of inactivity.
Not persisted to DB — restart clears all sessions.
For production, swap the in-memory dict for Redis with TTL.
"""
import time
from dataclasses import dataclass, field
from typing import Optional

SESSION_TTL_SECONDS = 1800  # 30 minutes


@dataclass
class SessionTurn:
    query: str
    response_summary: str
    copilot_type: str
    timestamp: float = field(default_factory=time.monotonic)


@dataclass
class CopilotSession:
    session_id: str
    copilot_type: str
    context_id: str              # proposal_id, approval_id, etc.
    turns: list[SessionTurn] = field(default_factory=list)
    created_at: float = field(default_factory=time.monotonic)
    last_active: float = field(default_factory=time.monotonic)

    def add_turn(self, query: str, response_summary: str) -> None:
        self.turns.append(SessionTurn(
            query=query,
            response_summary=response_summary,
            copilot_type=self.copilot_type,
        ))
        self.last_active = time.monotonic()

    def is_expired(self) -> bool:
        return (time.monotonic() - self.last_active) > SESSION_TTL_SECONDS

    def get_history_text(self, max_turns: int = 4) -> str:
        """Return last N turns as readable text for multi-turn context injection."""
        recent = self.turns[-max_turns:]
        if not recent:
            return ""
        lines = ["Previous conversation:"]
        for t in recent:
            lines.append(f"  Q: {t.query[:200]}")
            lines.append(f"  A: {t.response_summary[:300]}")
        return "\n".join(lines)


class SessionStore:
    def __init__(self):
        self._sessions: dict[str, CopilotSession] = {}

    def create(self, session_id: str, copilot_type: str, context_id: str) -> CopilotSession:
        session = CopilotSession(
            session_id=session_id,
            copilot_type=copilot_type,
            context_id=context_id,
        )
        self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> Optional[CopilotSession]:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        if session.is_expired():
            del self._sessions[session_id]
            return None
        return session

    def get_or_create(
        self,
        session_id: str,
        copilot_type: str,
        context_id: str,
    ) -> CopilotSession:
        session = self.get(session_id)
        if session is None:
            session = self.create(session_id, copilot_type, context_id)
        return session

    def purge_expired(self) -> int:
        expired_ids = [sid for sid, s in self._sessions.items() if s.is_expired()]
        for sid in expired_ids:
            del self._sessions[sid]
        return len(expired_ids)

    def count(self) -> int:
        return len(self._sessions)


# Process-level singleton
session_store = SessionStore()
