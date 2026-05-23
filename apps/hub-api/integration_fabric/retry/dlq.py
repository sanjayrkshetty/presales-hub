"""Dead-letter queue — summary and management helpers."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def dlq_summary(db: "Session", tenant_id: str) -> dict:
    from integration_fabric.retry.queue import get_dlq
    jobs = get_dlq(db, tenant_id)
    by_operation: dict[str, int] = {}
    for job in jobs:
        by_operation[job.operation] = by_operation.get(job.operation, 0) + 1
    return {
        "total": len(jobs),
        "by_operation": by_operation,
        "oldest": jobs[-1].next_retry_at.isoformat() if jobs else None,
    }


def purge_dlq(db: "Session", tenant_id: str) -> int:
    from sqlalchemy import delete
    from models.integration import RetryJob
    result = db.execute(
        delete(RetryJob)
        .where(RetryJob.tenant_id == tenant_id)
        .where(RetryJob.status == "dlq")
    )
    db.flush()
    return result.rowcount
