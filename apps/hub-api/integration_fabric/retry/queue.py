"""
Retry queue — wraps failed integration operations for re-execution.
Backed by RetryJob DB model for durability.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Optional, TYPE_CHECKING

from integration_fabric.retry.backoff import exponential_delay
from integration_fabric.config import RETRY_MAX_ATTEMPTS

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def enqueue(
    db: "Session",
    tenant_id: str,
    operation: str,
    payload: dict,
    max_attempts: int = RETRY_MAX_ATTEMPTS,
) -> str:
    from models.integration import RetryJob
    delay = exponential_delay(0)
    job = RetryJob(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        operation=operation,
        payload=payload,
        attempt=0,
        max_attempts=max_attempts,
        status="pending",
        next_retry_at=datetime.utcnow() + timedelta(seconds=delay),
    )
    db.add(job)
    db.flush()
    return job.id


def claim_due_jobs(db: "Session", tenant_id: str, limit: int = 50) -> list:
    from sqlalchemy import select
    from models.integration import RetryJob
    now = datetime.utcnow()
    jobs = db.scalars(
        select(RetryJob)
        .where(RetryJob.tenant_id == tenant_id)
        .where(RetryJob.status == "pending")
        .where(RetryJob.next_retry_at <= now)
        .order_by(RetryJob.next_retry_at)
        .limit(limit)
    ).all()
    for job in jobs:
        job.status = "running"
    db.flush()
    return list(jobs)


def mark_succeeded(db: "Session", job_id: str) -> None:
    from models.integration import RetryJob
    job = db.get(RetryJob, job_id)
    if job:
        job.status = "succeeded"
        db.flush()


def mark_failed(db: "Session", job_id: str, error: str) -> None:
    from models.integration import RetryJob
    job = db.get(RetryJob, job_id)
    if not job:
        return
    job.attempt += 1
    job.last_error = error
    if job.attempt >= job.max_attempts:
        job.status = "dlq"
    else:
        job.status = "pending"
        delay = exponential_delay(job.attempt)
        job.next_retry_at = datetime.utcnow() + timedelta(seconds=delay)
    db.flush()


def get_dlq(db: "Session", tenant_id: str, limit: int = 100) -> list:
    from sqlalchemy import select
    from models.integration import RetryJob
    return list(db.scalars(
        select(RetryJob)
        .where(RetryJob.tenant_id == tenant_id)
        .where(RetryJob.status == "dlq")
        .order_by(RetryJob.next_retry_at.desc())
        .limit(limit)
    ).all())


def requeue_dlq_job(db: "Session", job_id: str) -> bool:
    from models.integration import RetryJob
    job = db.get(RetryJob, job_id)
    if job and job.status == "dlq":
        job.status = "pending"
        job.attempt = 0
        job.next_retry_at = datetime.utcnow()
        db.flush()
        return True
    return False
