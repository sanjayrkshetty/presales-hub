"""
Admin API — internal platform operations.

All endpoints require the X-Admin-Key header matching PLATFORM_ADMIN_KEY.
Not exposed publicly via nginx — intended for ops tooling and the system health UI.
"""
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select

from core.config import settings
from db.database import get_db
from events.dead_letter import DeadLetterEvent

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _require_admin_key(x_admin_key: str = Header(default="")) -> None:
    if x_admin_key != settings.PLATFORM_ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Forbidden")


@router.get("/dlq")
def list_dlq_events(
    resolved: bool | None = Query(None, description="Filter by resolved status"),
    limit:    int          = Query(50, le=200),
    offset:   int          = Query(0, ge=0),
    _:        None         = Depends(_require_admin_key),
    db:       Session      = Depends(get_db),
):
    """List dead-letter queue events for ops review."""
    stmt = select(DeadLetterEvent).order_by(DeadLetterEvent.created_at.desc())
    if resolved is not None:
        stmt = stmt.where(DeadLetterEvent.resolved == resolved)
    stmt = stmt.offset(offset).limit(limit)

    events = db.scalars(stmt).all()
    return {
        "total": db.query(DeadLetterEvent).count(),
        "items": [
            {
                "id":           e.id,
                "channel":      e.channel,
                "payload":      e.payload,
                "error":        e.error,
                "retry_count":  e.retry_count,
                "next_retry_at": e.next_retry_at.isoformat() if e.next_retry_at else None,
                "resolved":     e.resolved,
                "created_at":   e.created_at.isoformat(),
                "resolved_at":  e.resolved_at.isoformat() if e.resolved_at else None,
            }
            for e in events
        ],
    }


@router.post("/dlq/{event_id}/resolve")
def resolve_dlq_event(
    event_id: str,
    _:        None    = Depends(_require_admin_key),
    db:       Session = Depends(get_db),
):
    """Mark a dead-letter event as manually resolved."""
    from datetime import datetime
    event = db.get(DeadLetterEvent, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    event.resolved = True
    event.resolved_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "id": event_id}


@router.get("/dlq/stats")
def dlq_stats(
    _:  None    = Depends(_require_admin_key),
    db: Session = Depends(get_db),
):
    """Summary stats for the dead-letter queue."""
    total    = db.query(DeadLetterEvent).count()
    pending  = db.query(DeadLetterEvent).filter_by(resolved=False).count()
    resolved = db.query(DeadLetterEvent).filter_by(resolved=True).count()
    return {"total": total, "pending": pending, "resolved": resolved}
