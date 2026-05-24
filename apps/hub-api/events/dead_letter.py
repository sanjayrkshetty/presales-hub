"""Dead-letter queue for failed event publishes.

When Redis publish fails, events are persisted to PostgreSQL so they can be
replayed or audited. The DLQ runner retries failed events on a schedule.
"""
import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, Session

from db.database import Base, SessionLocal

logger = logging.getLogger("events.dead_letter")

_MAX_RETRIES = 5
_RETRY_BACKOFF_MINUTES = [1, 5, 15, 60, 240]  # per attempt


class DeadLetterEvent(Base):
    """Failed event pending retry or manual replay."""
    __tablename__ = "dead_letter_events"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    channel: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
    error: Mapped[str] = mapped_column(String, default="")
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


def persist_failed_event(channel: str, payload: str, error: str) -> None:
    """Synchronously persist a failed event to the DLQ.

    Called from the event bus when Redis publish fails. Uses a fresh DB session
    so it doesn't depend on the request-scoped session.
    """
    try:
        db = SessionLocal()
        try:
            event = DeadLetterEvent(
                channel=channel,
                payload=payload,
                error=str(error)[:500],
                retry_count=0,
                next_retry_at=datetime.utcnow() + timedelta(minutes=_RETRY_BACKOFF_MINUTES[0]),
            )
            db.add(event)
            db.commit()
            logger.info("Event persisted to DLQ (id=%s)", event.id)
        finally:
            db.close()
    except Exception as exc:
        # If DB also fails, log and move on — don't cascade failure
        logger.error("DLQ persist failed: %s. Original error: %s", exc, error)


def retry_pending_events(redis_client) -> int:
    """Attempt to replay DLQ events that are due for retry.

    Returns the number of events successfully replayed.
    Call this from a periodic background task.
    """
    replayed = 0
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        pending = (
            db.query(DeadLetterEvent)
            .filter(
                DeadLetterEvent.resolved.is_(False),
                DeadLetterEvent.retry_count < _MAX_RETRIES,
                DeadLetterEvent.next_retry_at <= now,
            )
            .limit(50)
            .all()
        )

        for event in pending:
            try:
                redis_client.publish(event.channel, event.payload)
                event.resolved = True
                event.resolved_at = now
                replayed += 1
                logger.info("DLQ event %s replayed successfully", event.id)
            except Exception as exc:
                event.retry_count += 1
                if event.retry_count < len(_RETRY_BACKOFF_MINUTES):
                    delay = _RETRY_BACKOFF_MINUTES[event.retry_count]
                else:
                    delay = _RETRY_BACKOFF_MINUTES[-1]
                event.next_retry_at = now + timedelta(minutes=delay)
                event.error = str(exc)[:500]
                logger.warning("DLQ retry %d failed for %s: %s", event.retry_count, event.id, exc)

        db.commit()
    finally:
        db.close()
    return replayed
