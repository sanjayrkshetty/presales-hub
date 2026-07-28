"""
Integration Fabric API router.
All endpoints are synchronous — no async needed since the fabric layer is sync.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.database import get_db
from lib.dependencies import require_permission
import integration_fabric.adapters  # noqa: F401 — triggers @ConnectorRegistry.register for all 12 adapters

router = APIRouter(prefix="/api/integration", tags=["integration"])


# ── Request / Response models ──────────────────────────────────────────────────

class WebhookCreateRequest(BaseModel):
    tenant_id: str
    target_url: str
    event_types: list[str] = []
    secret: Optional[str] = None


class SyncRunRequest(BaseModel):
    channel: str
    tenant_id: str
    connector_config: Optional[dict] = None


class IngestBody(BaseModel):
    data: dict = {}


# ── Connector endpoints ────────────────────────────────────────────────────────

@router.get("/connectors")
def list_connectors(tenant_id: str = "default", db: Session = Depends(get_db)):
    from sqlalchemy import select
    from integration_fabric.connectors.base import ConnectorRegistry
    from models.integration import IntegrationConnector

    platforms = ConnectorRegistry.list_platforms()
    db_connectors = {
        c.platform: c.health_status
        for c in db.scalars(
            select(IntegrationConnector).where(
                IntegrationConnector.tenant_id == tenant_id
            )
        ).all()
    }
    return {
        "platforms": platforms,
        "registered_count": len(platforms),
        "health": {p: db_connectors.get(p, "unknown") for p in platforms},
    }


@router.get("/connectors/{platform}/health")
def connector_health(platform: str, tenant_id: str = "default", db: Session = Depends(get_db)):
    from integration_fabric.connectors.base import ConnectorRegistry, ConnectorConfig

    try:
        cls = ConnectorRegistry.get(platform)
    except (KeyError, ValueError):
        raise HTTPException(status_code=404, detail=f"Platform {platform!r} not registered")

    cfg = ConnectorConfig(platform=platform, tenant_id=tenant_id, credentials={})
    connector = cls(cfg)
    result = connector.healthcheck()
    return {
        "platform": platform,
        "healthy": result.healthy,
        "latency_ms": result.latency_ms,
        "message": result.message,
        "checked_at": result.checked_at,
    }


# ── Sync endpoints ─────────────────────────────────────────────────────────────

@router.get("/sync/status")
def sync_status(tenant_id: str = "default", db: Session = Depends(get_db)):
    from sqlalchemy import select
    from models.integration import SyncRecord

    rows = list(
        db.scalars(
            select(SyncRecord).where(SyncRecord.tenant_id == tenant_id)
        ).all()
    )
    by_status: dict[str, int] = {}
    for r in rows:
        by_status[r.sync_status] = by_status.get(r.sync_status, 0) + 1
    return {
        "tenant_id": tenant_id,
        "total": len(rows),
        "by_status": by_status,
    }


@router.post("/sync/run")
def run_sync(req: SyncRunRequest, db: Session = Depends(get_db), _authz=require_permission("integration:write")):
    from integration_fabric.sync.proposal_crm import sync_proposals_to_crm
    from integration_fabric.sync.sla_slack import push_sla_breaches_to_slack
    from integration_fabric.sync.escalation_teams import push_escalations_to_teams
    from integration_fabric.sync.approval_jira import sync_approvals_to_jira
    from integration_fabric.sync.executive_email import send_executive_digest

    _VALID = {"proposal_crm", "sla_slack", "escalation_teams", "approval_jira", "executive_email"}
    if req.channel not in _VALID:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown channel {req.channel!r}. Valid: {sorted(_VALID)}",
        )

    # All sync functions support dry_run=True which skips real connector calls,
    # so we pass None for connectors — suitable for on-demand API triggering.
    try:
        if req.channel == "proposal_crm":
            result = sync_proposals_to_crm(db, req.tenant_id, connector=None, dry_run=True)
        elif req.channel == "sla_slack":
            result = push_sla_breaches_to_slack(db, slack_connector=None, channel="general", dry_run=True)
        elif req.channel == "escalation_teams":
            result = push_escalations_to_teams(db, teams_connector=None, team_id="default", channel_id="general", dry_run=True)
        elif req.channel == "approval_jira":
            result = sync_approvals_to_jira(db, jira_connector=None, dry_run=True)
        else:  # executive_email
            result = send_executive_digest(db, email_connector=None, recipients=[], dry_run=True)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {"channel": req.channel, "tenant_id": req.tenant_id, "result": str(result)}


# ── Webhook endpoints ──────────────────────────────────────────────────────────

@router.get("/webhooks")
def list_webhooks(tenant_id: str = "default", db: Session = Depends(get_db)):
    from integration_fabric.webhooks.registry import list_subscriptions

    subs = list_subscriptions(db, tenant_id)
    return {
        "tenant_id": tenant_id,
        "count": len(subs),
        "subscriptions": [
            {
                "id": s.id,
                "target_url": s.target_url,
                "event_types": s.event_types,
                "active": s.active,
            }
            for s in subs
        ],
    }


@router.post("/webhooks", status_code=201)
def create_webhook(req: WebhookCreateRequest, db: Session = Depends(get_db), _authz=require_permission("webhook:write")):
    from integration_fabric.webhooks.registry import create_subscription

    sub = create_subscription(
        db,
        tenant_id=req.tenant_id,
        target_url=req.target_url,
        event_types=req.event_types,
        secret=req.secret,
    )
    db.commit()
    return {"id": sub.id, "tenant_id": sub.tenant_id, "target_url": sub.target_url}


@router.delete("/webhooks/{subscription_id}")
def delete_webhook(subscription_id: str, db: Session = Depends(get_db), _authz=require_permission("webhook:delete")):
    from integration_fabric.webhooks.registry import deactivate_subscription

    ok = deactivate_subscription(db, subscription_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Subscription not found")
    db.commit()
    return {"deactivated": True, "id": subscription_id}


@router.post("/webhooks/inbound")
async def inbound_webhook(request: Request, db: Session = Depends(get_db)):
    from integration_fabric.webhooks.signature import verify_signature
    from integration_fabric.webhooks.dispatcher import dispatch_event
    from integration_fabric.config import WEBHOOK_SIGNATURE_HEADER

    body = await request.body()
    sig_header = request.headers.get(WEBHOOK_SIGNATURE_HEADER, "")
    event_type = request.headers.get("X-Event-Type", "webhook.inbound")
    tenant_id = request.headers.get("X-Tenant-Id", "default")
    secret = request.headers.get("X-Webhook-Secret", "")

    if sig_header and secret:
        if not verify_signature(body, secret, sig_header):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    import json
    try:
        payload = json.loads(body) if body else {}
    except Exception:
        payload = {"raw": body.decode(errors="replace")}

    results = dispatch_event(db, tenant_id=tenant_id, event_type=event_type, payload=payload)
    return {"received": True, "deliveries": len(results)}


# ── Retry / DLQ endpoints ──────────────────────────────────────────────────────

@router.get("/retry/queue")
def retry_queue(tenant_id: str = "default", db: Session = Depends(get_db)):
    from integration_fabric.retry.queue import claim_due_jobs

    jobs = claim_due_jobs(db, tenant_id)
    return {
        "tenant_id": tenant_id,
        "count": len(jobs),
        "jobs": [
            {
                "id": j.id,
                "operation": j.operation,
                "attempt": j.attempt,
                "max_attempts": j.max_attempts,
                "status": j.status,
                "next_retry_at": j.next_retry_at.isoformat() if j.next_retry_at else None,
            }
            for j in jobs
        ],
    }


@router.get("/retry/dlq")
def retry_dlq(tenant_id: str = "default", limit: int = 100, db: Session = Depends(get_db)):
    from integration_fabric.retry.queue import get_dlq

    jobs = get_dlq(db, tenant_id, limit=limit)
    return {
        "tenant_id": tenant_id,
        "count": len(jobs),
        "jobs": [
            {
                "id": j.id,
                "operation": j.operation,
                "attempt": j.attempt,
                "last_error": j.last_error,
                "status": j.status,
            }
            for j in jobs
        ],
    }


@router.post("/retry/dlq/{job_id}/requeue")
def requeue_job(job_id: str, db: Session = Depends(get_db), _authz=require_permission("integration:admin")):
    from integration_fabric.retry.queue import requeue_dlq_job

    ok = requeue_dlq_job(db, job_id)
    if not ok:
        raise HTTPException(status_code=404, detail="DLQ job not found")
    db.commit()
    return {"requeued": True, "id": job_id}


# ── Rate limit endpoint ────────────────────────────────────────────────────────

@router.get("/rate-limits")
def rate_limits(tenant_id: str = "default"):
    from integration_fabric.rate_limits.limiter import RateLimiter

    return {
        "tenant_id": tenant_id,
        "limits": RateLimiter.status(tenant_id),
    }


# ── Dashboard endpoint ─────────────────────────────────────────────────────────

@router.get("/dashboard")
def dashboard(tenant_id: str = "default", db: Session = Depends(get_db)):
    from integration_fabric.observability.dashboard import build_dashboard

    return build_dashboard(db, tenant_id)


# ── Ingestion endpoint ─────────────────────────────────────────────────────────

@router.post("/ingest/{pipeline_name}")
def run_ingest(pipeline_name: str, req: IngestBody, db: Session = Depends(get_db), _authz=require_permission("integration:write")):
    from integration_fabric.ingestion.rfp_ingest import RFPIngestionPipeline
    from integration_fabric.ingestion.email_attachment import EmailAttachmentPipeline
    from integration_fabric.ingestion.crm_opportunity import CRMOpportunityPipeline
    from integration_fabric.ingestion.jira_ticket import JiraTicketPipeline
    from integration_fabric.ingestion.slack_escalation import SlackEscalationPipeline
    from integration_fabric.ingestion.meeting_notes import MeetingNotesPipeline
    from integration_fabric.ingestion.proposal_doc import ProposalDocPipeline

    _PIPELINES = {
        "rfp_ingest": RFPIngestionPipeline,
        "email_attachment": EmailAttachmentPipeline,
        "crm_opportunity": CRMOpportunityPipeline,
        "jira_ticket": JiraTicketPipeline,
        "slack_escalation": SlackEscalationPipeline,
        "meeting_notes": MeetingNotesPipeline,
        "proposal_doc": ProposalDocPipeline,
    }

    cls = _PIPELINES.get(pipeline_name)
    if cls is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown pipeline {pipeline_name!r}. Valid: {list(_PIPELINES)}",
        )

    pipeline = cls()
    result = pipeline.run(req.data, db=db)
    return {
        "pipeline": result.pipeline,
        "success": result.success,
        "records_ingested": result.records_ingested,
        "artifact_ids": result.artifact_ids,
        "error": result.error,
    }


# ── RBAC endpoint ──────────────────────────────────────────────────────────────

@router.get("/rbac/permissions")
def rbac_permissions(role: str = "readonly"):
    from integration_fabric.rbac.permissions import ROLE_PERMISSIONS

    perms = ROLE_PERMISSIONS.get(role)
    if perms is None:
        raise HTTPException(status_code=404, detail=f"Role {role!r} not found")
    return {"role": role, "permissions": sorted(perms)}


# ── Integration layer health ───────────────────────────────────────────────────

@router.get("/health")
def integration_health():
    from integration_fabric.connectors.base import ConnectorRegistry

    platforms = ConnectorRegistry.list_platforms()
    return {
        "status": "ok",
        "layer": "integration_fabric",
        "registered_connectors": len(platforms),
        "platforms": platforms,
    }
