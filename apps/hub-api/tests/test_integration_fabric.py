"""
Integration Fabric test suite — Task #41.

Coverage:
- ConnectorRegistry + all 12 adapters
- OAuth2Client (PKCE auth URL, client_credentials stub, refresh stub)
- CredentialStore put/get/delete + TokenRotator.needs_rotation
- SSO providers: Google/Microsoft/Okta get_login_url, verify_token bad token
- SAMLProvider.generate_metadata
- RBACEnforcer: has_permission, PermissionDenied, effective_permissions, check_permission
- All 7 roles have non-empty permission sets
- AuditLog: log_access, get_user_history, get_denied
- Webhook signature: sign/verify/tamper
- WebhookRegistry: create/list/deactivate (DB)
- WebhookDispatcher: dispatch_event with mock http_post_fn (DB)
- All 7 ingestion pipelines: validate rejects bad input, run returns IngestionResult
- SyncEngine: upsert idempotent, conflict mark (DB)
- RetryQueue: enqueue/claim/DLQ promotion (DB)
- DLQ: summary/purge (DB)
- RateLimiter: initial True, exhausted False
- Normalizer: salesforce + hubspot opportunity
- ReconciliationEngine: detect_drift no-drift and drifted cases
- All 16 API endpoints via TestClient
"""
from __future__ import annotations

import uuid
import pytest
from decimal import Decimal
from datetime import date, timedelta

import integration_fabric.adapters  # noqa: F401 — populates ConnectorRegistry


# ── Seed helpers (self-contained, mirrors test_strategic_intelligence pattern) ──

def _make_client(db, name="Acme Corp"):
    from models.opportunity import Client
    c = Client(id=str(uuid.uuid4()), name=name)
    db.add(c)
    db.flush()
    return c


def _make_opportunity(db, client_id, stage="intake", deal_value_cr=5.0, win_prob=60):
    from models.opportunity import Opportunity
    o = Opportunity(
        id=str(uuid.uuid4()),
        client_id=client_id,
        title="Test RFP",
        rfp_type="ISO 27001",
        deal_value_cr=Decimal(str(deal_value_cr)),
        win_probability=win_prob,
        stage=stage,
        deadline=date.today() + timedelta(days=30),
    )
    db.add(o)
    db.flush()
    return o


def _make_proposal(db, opp_id, stage="intake"):
    from models import Proposal
    p = Proposal(
        id=str(uuid.uuid4()),
        opportunity_id=opp_id,
        stage=stage,
        content={"exec_summary": "Summary text here.", "scope": "Scope text here."},
    )
    db.add(p)
    db.flush()
    return p


# ── ConnectorRegistry ──────────────────────────────────────────────────────────

EXPECTED_PLATFORMS = [
    "salesforce", "hubspot", "jira", "servicenow",
    "slack", "teams", "outlook", "gmail",
    "sharepoint", "confluence", "gdrive", "webhook",
]


def test_registry_list_platforms():
    from integration_fabric.connectors.base import ConnectorRegistry
    platforms = ConnectorRegistry.list_platforms()
    for p in EXPECTED_PLATFORMS:
        assert p in platforms, f"Expected platform {p!r} in registry"


def test_registry_instantiate_salesforce():
    from integration_fabric.connectors.base import ConnectorRegistry, ConnectorConfig
    cfg = ConnectorConfig(
        platform="salesforce",
        tenant_id="t1",
        credentials={"client_id": "x", "client_secret": "y", "instance_url": "https://test.salesforce.com"},
    )
    connector = ConnectorRegistry.instantiate("salesforce", cfg)
    assert connector is not None
    assert hasattr(connector, "healthcheck")


# ── All 12 adapters: instantiate + healthcheck ─────────────────────────────────

_ADAPTER_CREDENTIALS = {
    "salesforce": {"client_id": "c", "client_secret": "s", "instance_url": "https://test.salesforce.com"},
    "hubspot": {"api_key": "hk"},
    "jira": {"base_url": "https://jira.test", "email": "a@b.com", "api_token": "tok"},
    "servicenow": {"instance_url": "https://sn.test", "username": "u", "password": "p"},
    "slack": {"bot_token": "xoxb-test"},
    "teams": {"tenant_id": "t1", "client_id": "c", "client_secret": "s"},
    "outlook": {"client_id": "c", "client_secret": "s", "tenant_id": "t1"},
    "gmail": {"credentials_json": "{}"},
    "sharepoint": {"tenant_id": "t1", "client_id": "c", "client_secret": "s", "site_url": "https://sp.test"},
    "confluence": {"base_url": "https://conf.test", "email": "a@b.com", "api_token": "tok"},
    "gdrive": {"credentials_json": "{}"},
    "webhook": {"signing_secret": "sec"},
}


@pytest.mark.parametrize("platform", EXPECTED_PLATFORMS)
def test_adapter_healthcheck(platform):
    from integration_fabric.connectors.base import ConnectorRegistry, ConnectorConfig
    creds = _ADAPTER_CREDENTIALS[platform]
    cfg = ConnectorConfig(platform=platform, tenant_id="t1", credentials=creds)
    connector = ConnectorRegistry.instantiate(platform, cfg)
    result = connector.healthcheck()
    assert isinstance(result.healthy, bool)
    assert result.latency_ms >= 0


# ── OAuth2Client ───────────────────────────────────────────────────────────────

def test_oauth2_build_auth_url_pkce():
    from integration_fabric.auth.oauth2 import OAuth2Client, OAuth2Config
    cfg = OAuth2Config(
        client_id="cid",
        client_secret="sec",
        token_url="https://example.com/token",
        auth_url="https://example.com/auth",
        scopes=["openid"],
        redirect_uri="https://app/callback",
        use_pkce=True,
    )
    client = OAuth2Client(cfg)
    url = client.build_auth_url(state="xyz")
    assert "code_challenge" in url
    assert "client_id=cid" in url


def test_oauth2_client_credentials_no_http():
    """client_credentials raises or returns TokenResponse — both are valid without real HTTP."""
    from integration_fabric.auth.oauth2 import OAuth2Client, OAuth2Config, TokenResponse
    cfg = OAuth2Config(
        client_id="cid",
        client_secret="sec",
        token_url="https://example.com/token",
    )
    client = OAuth2Client(cfg)

    def stub_post(url, data):
        return {"access_token": "tok123", "token_type": "Bearer", "expires_in": 3600}

    result = client.client_credentials(http_post_fn=stub_post)
    assert isinstance(result, TokenResponse)
    assert result.access_token == "tok123"


def test_oauth2_refresh():
    from integration_fabric.auth.oauth2 import OAuth2Client, OAuth2Config, TokenResponse
    cfg = OAuth2Config(
        client_id="cid",
        client_secret="sec",
        token_url="https://example.com/token",
    )
    client = OAuth2Client(cfg)

    def stub_post(url, data):
        return {"access_token": "refreshed", "token_type": "Bearer", "expires_in": 3600}

    result = client.refresh("old-refresh-token", http_post_fn=stub_post)
    assert isinstance(result, TokenResponse)
    assert result.access_token == "refreshed"


# ── CredentialStore ────────────────────────────────────────────────────────────

def test_credential_store_put_get():
    from integration_fabric.auth.credential_store import CredentialStore
    CredentialStore.clear()
    CredentialStore.put("tenant1", "salesforce", {"api_key": "abc"})
    creds = CredentialStore.get("tenant1", "salesforce")
    assert creds == {"api_key": "abc"}


def test_credential_store_delete():
    from integration_fabric.auth.credential_store import CredentialStore
    CredentialStore.clear()
    CredentialStore.put("tenant1", "hubspot", {"token": "tok"})
    deleted = CredentialStore.delete("tenant1", "hubspot")
    assert deleted is True
    assert CredentialStore.get("tenant1", "hubspot") is None


def test_credential_store_get_missing():
    from integration_fabric.auth.credential_store import CredentialStore
    CredentialStore.clear()
    assert CredentialStore.get("no-such-tenant", "jira") is None


# ── TokenRotator ───────────────────────────────────────────────────────────────

def test_token_rotator_needs_rotation_fresh():
    from integration_fabric.auth.credential_store import TokenRotator
    TokenRotator.mark_rotated("t1", "salesforce")
    assert TokenRotator.needs_rotation("t1", "salesforce") is False


def test_token_rotator_needs_rotation_never_rotated():
    from integration_fabric.auth.credential_store import TokenRotator
    # Key that was never rotated should need rotation
    result = TokenRotator.needs_rotation("never-tenant", "jira")
    assert result is True


# ── SSO providers ──────────────────────────────────────────────────────────────

def test_google_sso_get_login_url():
    from integration_fabric.auth.sso.google import GoogleSSO
    sso = GoogleSSO(client_id="cid", client_secret="sec", redirect_uri="https://app/cb")
    url = sso.get_login_url(state="state1")
    assert url and "accounts.google.com" in url


def test_microsoft_sso_get_login_url():
    from integration_fabric.auth.sso.microsoft import MicrosoftSSO
    sso = MicrosoftSSO(client_id="cid", client_secret="sec", tenant_id="tid", redirect_uri="https://app/cb")
    url = sso.get_login_url(state="state1")
    assert url and len(url) > 10


def test_okta_sso_get_login_url():
    from integration_fabric.auth.sso.okta import OktaSSO
    sso = OktaSSO(domain="company.okta.com", client_id="cid", client_secret="sec", redirect_uri="https://app/cb")
    url = sso.get_login_url(state="state1")
    assert url and "okta.com" in url


def test_google_sso_verify_bad_token():
    from integration_fabric.auth.sso.google import GoogleSSO
    sso = GoogleSSO(client_id="cid", client_secret="sec", redirect_uri="https://app/cb")
    result = sso.verify_token("invalid-token-xyz")
    assert result.valid is False


# ── SAMLProvider ───────────────────────────────────────────────────────────────

def test_saml_generate_metadata():
    from integration_fabric.auth.sso.saml import SAMLProvider, SAMLConfig
    cfg = SAMLConfig(
        idp_metadata_url="https://idp.example.com/metadata",
        sp_entity_id="https://myapp.example.com",
        sp_acs_url="https://myapp.example.com/saml/acs",
    )
    saml = SAMLProvider(cfg)
    metadata = saml.generate_metadata()
    assert "entityID" in metadata


# ── RBACEnforcer ───────────────────────────────────────────────────────────────

def _make_ctx(roles, user_id="user1", tenant_id="t1"):
    from integration_fabric.rbac.enforcer import AccessContext
    return AccessContext(user_id=user_id, roles=roles, tenant_id=tenant_id)


def test_rbac_has_permission_admin():
    from integration_fabric.rbac.enforcer import RBACEnforcer
    enforcer = RBACEnforcer()
    ctx = _make_ctx(["admin"])
    assert enforcer.has_permission(ctx, "proposal:read") is True
    assert enforcer.has_permission(ctx, "integration:admin") is True


def test_rbac_check_raises_permission_denied():
    from integration_fabric.rbac.enforcer import RBACEnforcer, PermissionDenied
    enforcer = RBACEnforcer()
    ctx = _make_ctx(["readonly"])
    with pytest.raises(PermissionDenied):
        enforcer.check(ctx, "integration:admin")


def test_rbac_effective_permissions_presales_lead():
    from integration_fabric.rbac.enforcer import RBACEnforcer
    enforcer = RBACEnforcer()
    ctx = _make_ctx(["presales_lead"])
    perms = enforcer.effective_permissions(ctx)
    assert isinstance(perms, (set, frozenset))
    assert "proposal:read" in perms
    assert "proposal:write" in perms


def test_check_permission_admin_no_raise():
    from integration_fabric.rbac.enforcer import check_permission
    # Should not raise
    check_permission("u1", ["admin"], "integration:admin", "t1")


def test_check_permission_readonly_raises():
    from integration_fabric.rbac.enforcer import check_permission, PermissionDenied
    with pytest.raises(PermissionDenied):
        check_permission("u1", ["readonly"], "integration:admin", "t1")


# ── All 7 roles have non-empty permission sets ─────────────────────────────────

@pytest.mark.parametrize("role", ["admin", "presales_lead", "sme", "executive", "approver", "analyst", "readonly"])
def test_role_has_permissions(role):
    from integration_fabric.rbac.permissions import ROLE_PERMISSIONS
    perms = ROLE_PERMISSIONS.get(role)
    assert perms, f"Role {role!r} has no permissions defined"


# ── AuditLog ───────────────────────────────────────────────────────────────────

def test_audit_log_access_and_history():
    from integration_fabric.rbac.audit import AuditLog
    uid = f"audit-user-{uuid.uuid4().hex[:6]}"
    AuditLog.log_access(uid, "proposal:read", allowed=True, roles=["sme"])
    history = AuditLog.get_user_history(uid)
    assert len(history) >= 1
    assert history[0].user_id == uid
    assert history[0].permission == "proposal:read"
    assert history[0].allowed is True


def test_audit_log_denied():
    from integration_fabric.rbac.audit import AuditLog
    uid = f"denied-user-{uuid.uuid4().hex[:6]}"
    AuditLog.log_access(uid, "integration:admin", allowed=False, roles=["readonly"])
    denied = AuditLog.get_denied()
    denied_ids = [e.user_id for e in denied]
    assert uid in denied_ids


def test_audit_log_limit():
    from integration_fabric.rbac.audit import AuditLog
    uid = f"limit-user-{uuid.uuid4().hex[:6]}"
    for i in range(5):
        AuditLog.log_access(uid, f"perm:{i}", allowed=True, roles=["admin"])
    history = AuditLog.get_user_history(uid, limit=2)
    assert len(history) <= 2


# ── Webhook signature ──────────────────────────────────────────────────────────

def test_sign_payload_prefix():
    from integration_fabric.webhooks.signature import sign_payload
    sig = sign_payload(b"hello", "secret")
    assert sig.startswith("sha256=")


def test_verify_signature_valid():
    from integration_fabric.webhooks.signature import sign_payload, verify_signature
    body = b'{"event": "test"}'
    secret = "super-secret"
    sig = sign_payload(body, secret)
    assert verify_signature(body, secret, sig) is True


def test_verify_signature_tampered():
    from integration_fabric.webhooks.signature import sign_payload, verify_signature
    body = b'{"event": "test"}'
    sig = sign_payload(body, "secret")
    assert verify_signature(b'{"event": "tampered"}', "secret", sig) is False


# ── WebhookRegistry (uses db fixture) ─────────────────────────────────────────

def test_webhook_registry_create(db):
    from integration_fabric.webhooks.registry import create_subscription
    sub = create_subscription(db, "t1", "https://example.com/hook", ["proposal.created"])
    db.commit()
    assert sub.id is not None
    assert sub.tenant_id == "t1"
    assert sub.target_url == "https://example.com/hook"
    assert sub.active is True


def test_webhook_registry_list(db):
    from integration_fabric.webhooks.registry import create_subscription, list_subscriptions
    create_subscription(db, "t1", "https://example.com/h1", ["a"])
    create_subscription(db, "t1", "https://example.com/h2", ["b"])
    db.commit()
    subs = list_subscriptions(db, "t1")
    assert len(subs) >= 2


def test_webhook_registry_deactivate(db):
    from integration_fabric.webhooks.registry import create_subscription, deactivate_subscription, list_subscriptions
    sub = create_subscription(db, "t1", "https://example.com/h3", ["c"])
    db.commit()
    ok = deactivate_subscription(db, sub.id)
    db.commit()
    assert ok is True
    active_subs = list_subscriptions(db, "t1", active_only=True)
    ids = [s.id for s in active_subs]
    assert sub.id not in ids


# ── WebhookDispatcher (uses db fixture) ───────────────────────────────────────

def test_webhook_dispatcher_dispatch(db):
    from integration_fabric.webhooks.registry import create_subscription
    from integration_fabric.webhooks.dispatcher import dispatch_event

    sub = create_subscription(db, "t1", "https://example.com/hook", ["order.created"], secret="sec")
    db.commit()

    received = []

    def mock_post(url, data, headers, timeout):
        received.append(url)
        return type("R", (), {"status_code": 200, "text": "ok"})()

    results = dispatch_event(db, "t1", "order.created", {"order_id": "123"}, http_post_fn=mock_post)
    assert isinstance(results, list)
    assert len(results) >= 1
    assert results[0]["subscription_id"] == sub.id


# ── Ingestion pipelines ────────────────────────────────────────────────────────

# RFP
def test_rfp_ingest_validate_rejects_empty():
    from integration_fabric.ingestion.rfp_ingest import RFPIngestionPipeline
    valid, errors = RFPIngestionPipeline().validate({})
    assert valid is False
    assert len(errors) > 0


def test_rfp_ingest_run_success():
    from integration_fabric.ingestion.rfp_ingest import RFPIngestionPipeline
    raw = {"content": "Security audit requirements must be met.", "filename": "rfp.pdf", "mime_type": "application/pdf"}
    result = RFPIngestionPipeline().run(raw)
    assert result.success is True
    assert result.records_ingested >= 1


# Email attachment
def test_email_attachment_validate_rejects():
    from integration_fabric.ingestion.email_attachment import EmailAttachmentPipeline
    valid, errors = EmailAttachmentPipeline().validate({})
    assert valid is False


def test_email_attachment_run_success():
    from integration_fabric.ingestion.email_attachment import EmailAttachmentPipeline
    raw = {
        "email_id": "email-001",
        "subject": "RFP attached",
        "attachments": [{"filename": "brief.pdf", "content": "content here", "mime_type": "application/pdf"}],
    }
    result = EmailAttachmentPipeline().run(raw)
    assert result.success is True


# CRM opportunity
def test_crm_opportunity_validate_rejects():
    from integration_fabric.ingestion.crm_opportunity import CRMOpportunityPipeline
    valid, errors = CRMOpportunityPipeline().validate({})
    assert valid is False


def test_crm_opportunity_run_success():
    from integration_fabric.ingestion.crm_opportunity import CRMOpportunityPipeline
    raw = {
        "source": "salesforce",
        "records": [{"Id": "SF001", "Name": "ACME Deal", "StageName": "Prospecting", "Amount": 50000}],
    }
    result = CRMOpportunityPipeline().run(raw)
    assert result.success is True


# Jira ticket
def test_jira_ticket_validate_rejects():
    from integration_fabric.ingestion.jira_ticket import JiraTicketPipeline
    valid, errors = JiraTicketPipeline().validate({})
    assert valid is False


def test_jira_ticket_run_success():
    from integration_fabric.ingestion.jira_ticket import JiraTicketPipeline
    raw = {"issues": [{"key": "PROJ-1", "summary": "Fix bug", "status": "Open", "priority": "High"}]}
    result = JiraTicketPipeline().run(raw)
    assert result.success is True


# Slack escalation
def test_slack_escalation_validate_rejects():
    from integration_fabric.ingestion.slack_escalation import SlackEscalationPipeline
    valid, errors = SlackEscalationPipeline().validate({})
    assert valid is False


def test_slack_escalation_run_success():
    from integration_fabric.ingestion.slack_escalation import SlackEscalationPipeline
    raw = {"text": "Critical outage on production server!", "channel": "incidents", "user": "alice"}
    result = SlackEscalationPipeline().run(raw)
    assert result.success is True


# Meeting notes
def test_meeting_notes_validate_rejects():
    from integration_fabric.ingestion.meeting_notes import MeetingNotesPipeline
    valid, errors = MeetingNotesPipeline().validate({})
    assert valid is False


def test_meeting_notes_run_success():
    from integration_fabric.ingestion.meeting_notes import MeetingNotesPipeline
    raw = {"title": "Q1 Review", "content": "Discussed roadmap and deliverables for next quarter."}
    result = MeetingNotesPipeline().run(raw)
    assert result.success is True


# Proposal doc
def test_proposal_doc_validate_rejects():
    from integration_fabric.ingestion.proposal_doc import ProposalDocPipeline
    valid, errors = ProposalDocPipeline().validate({})
    assert valid is False


def test_proposal_doc_run_success():
    from integration_fabric.ingestion.proposal_doc import ProposalDocPipeline
    raw = {"content": "This proposal outlines the scope of ISO 27001 engagement.", "title": "ISO Proposal"}
    result = ProposalDocPipeline().run(raw)
    assert result.success is True


# ── SyncEngine (uses db fixture) ──────────────────────────────────────────────

def test_sync_engine_upsert_creates(db):
    from integration_fabric.sync.engine import upsert_sync_record
    rec = upsert_sync_record(db, "t1", "salesforce", "local-001", "remote-001", "proposal", {"stage": "intake"})
    db.commit()
    assert rec.id is not None
    assert rec.local_id == "local-001"
    assert rec.sync_status == "synced"


def test_sync_engine_upsert_idempotent(db):
    from integration_fabric.sync.engine import upsert_sync_record
    data = {"stage": "intake"}
    rec1 = upsert_sync_record(db, "t1", "salesforce", "local-002", "remote-002", "proposal", data)
    db.commit()
    rec2 = upsert_sync_record(db, "t1", "salesforce", "local-002", "remote-002", "proposal", data)
    db.commit()
    assert rec1.id == rec2.id
    assert rec2.checksum == rec1.checksum


def test_sync_engine_mark_conflict(db):
    from integration_fabric.sync.engine import upsert_sync_record, mark_conflict, get_sync_record
    upsert_sync_record(db, "t1", "salesforce", "local-003", "remote-003", "proposal", {"stage": "intake"})
    db.commit()
    rec = get_sync_record(db, "t1", "salesforce", "local-003", "proposal")
    mark_conflict(db, rec.id, {"field": "stage", "local": "intake", "remote": "closed"})
    db.commit()
    updated = get_sync_record(db, "t1", "salesforce", "local-003", "proposal")
    assert updated.sync_status == "conflict"


# ── RetryQueue (uses db fixture) ──────────────────────────────────────────────

def test_retry_queue_enqueue(db):
    from integration_fabric.retry.queue import enqueue
    job_id = enqueue(db, "t1", "sync_crm", {"proposal_id": "p1"}, max_attempts=3)
    db.commit()
    assert isinstance(job_id, str)
    assert len(job_id) > 0


def test_retry_queue_claim_due_jobs(db):
    from integration_fabric.retry.queue import enqueue, claim_due_jobs
    from datetime import datetime
    enqueue(db, "t1", "sync_crm_claim", {"x": 1}, max_attempts=3)
    db.commit()
    # Force next_retry_at to past so job is claimable
    from models.integration import RetryJob
    from sqlalchemy import select
    job = db.scalars(select(RetryJob).where(RetryJob.operation == "sync_crm_claim")).first()
    if job:
        job.next_retry_at = datetime(2000, 1, 1)
        db.commit()
    jobs = claim_due_jobs(db, "t1")
    assert len(jobs) >= 1


def test_retry_queue_dlq_promotion(db):
    from integration_fabric.retry.queue import enqueue, mark_failed, get_dlq
    from datetime import datetime
    from models.integration import RetryJob
    from sqlalchemy import select

    job_id = enqueue(db, "t1", "failing_op", {"x": 1}, max_attempts=1)
    db.commit()

    # Force next_retry_at to past
    job = db.get(RetryJob, job_id)
    job.next_retry_at = datetime(2000, 1, 1)
    db.commit()

    mark_failed(db, job_id, "permanent failure")
    db.commit()

    dlq = get_dlq(db, "t1")
    dlq_ids = [j.id for j in dlq]
    assert job_id in dlq_ids


# ── DLQ (uses db fixture) ─────────────────────────────────────────────────────

def test_dlq_summary(db):
    from integration_fabric.retry.queue import enqueue, mark_failed
    from integration_fabric.retry.dlq import dlq_summary
    from models.integration import RetryJob
    from datetime import datetime

    job_id = enqueue(db, "t2", "dlq_op", {}, max_attempts=1)
    job = db.get(RetryJob, job_id)
    job.next_retry_at = datetime(2000, 1, 1)
    db.commit()

    mark_failed(db, job_id, "err")
    db.commit()

    summary = dlq_summary(db, "t2")
    assert "total" in summary
    assert summary["total"] >= 1


def test_dlq_purge(db):
    from integration_fabric.retry.queue import enqueue, mark_failed
    from integration_fabric.retry.dlq import purge_dlq
    from models.integration import RetryJob
    from datetime import datetime

    job_id = enqueue(db, "t3", "purge_op", {}, max_attempts=1)
    job = db.get(RetryJob, job_id)
    job.next_retry_at = datetime(2000, 1, 1)
    db.commit()

    mark_failed(db, job_id, "err")
    db.commit()

    count = purge_dlq(db, "t3")
    db.commit()
    assert count >= 1


# ── RateLimiter ───────────────────────────────────────────────────────────────

def test_rate_limiter_initial_true():
    from integration_fabric.rate_limits.limiter import RateLimiter
    RateLimiter.reset("rl-tenant", "slack")
    result = RateLimiter.check("rl-tenant", "slack")
    assert result is True


def test_rate_limiter_exhausted_false():
    from integration_fabric.rate_limits.limiter import RateLimiter
    from integration_fabric import config as cfg
    platform = "servicenow"
    tenant = "rl-exhaust-tenant"
    RateLimiter.reset(tenant, platform)
    capacity = cfg.SERVICENOW_RATE_LIMIT_RPM
    # Consume all tokens
    for _ in range(capacity):
        RateLimiter.check(tenant, platform)
    # Next call should fail
    result = RateLimiter.check(tenant, platform)
    assert result is False


# ── Normalizer ────────────────────────────────────────────────────────────────

def test_normalizer_salesforce_opportunity():
    from integration_fabric.transforms.normalizer import normalize_opportunity
    rec = {"Id": "SF001", "Name": "Acme Deal", "StageName": "Prospecting", "Amount": 50000.0, "CloseDate": "2026-06-30"}
    norm = normalize_opportunity(rec, "salesforce")
    assert "title" in norm or "name" in norm or "id" in norm


def test_normalizer_hubspot_opportunity():
    from integration_fabric.transforms.normalizer import normalize_opportunity
    rec = {"id": "HS001", "properties": {"dealname": "HubSpot Deal", "dealstage": "presentationscheduled", "amount": "30000"}}
    norm = normalize_opportunity(rec, "hubspot")
    assert isinstance(norm, dict)
    assert len(norm) > 0


# ── ReconciliationEngine: detect_drift ────────────────────────────────────────

def test_detect_drift_no_drift():
    from integration_fabric.reconciliation.drift_detector import detect_drift
    local = [{"id": "r1", "stage": "intake", "title": "Deal"}]
    remote = [{"id": "r1", "stage": "intake", "title": "Deal"}]
    report = detect_drift(local, remote)
    assert report.drifted_count == 0
    assert report.matching_count == 1
    assert report.field_deltas == []


def test_detect_drift_with_drift():
    from integration_fabric.reconciliation.drift_detector import detect_drift
    local = [{"id": "r2", "stage": "intake", "title": "Old Title"}]
    remote = [{"id": "r2", "stage": "qualification", "title": "New Title"}]
    report = detect_drift(local, remote)
    assert report.drifted_count == 1
    assert len(report.field_deltas) >= 1
    fields_changed = {d["field"] for d in report.field_deltas}
    assert "stage" in fields_changed or "title" in fields_changed


# ── API endpoints (uses client fixture) ───────────────────────────────────────

def test_api_connectors_list(client):
    r = client.get("/api/integration/connectors?tenant_id=t1")
    assert r.status_code == 200
    data = r.json()
    assert "platforms" in data
    assert "registered_count" in data
    assert data["registered_count"] == 12


def test_api_connector_health(client):
    r = client.get("/api/integration/connectors/salesforce/health?tenant_id=t1")
    assert r.status_code == 200
    data = r.json()
    assert "healthy" in data
    assert "latency_ms" in data


def test_api_connector_health_unknown(client):
    r = client.get("/api/integration/connectors/unknown_platform/health")
    assert r.status_code == 404


def test_api_sync_status(client):
    r = client.get("/api/integration/sync/status?tenant_id=t1")
    assert r.status_code == 200
    data = r.json()
    assert "total" in data
    assert "by_status" in data


def test_api_sync_run(client):
    r = client.post("/api/integration/sync/run", json={"channel": "proposal_crm", "tenant_id": "t1"})
    assert r.status_code == 200
    data = r.json()
    assert data["channel"] == "proposal_crm"


def test_api_sync_run_invalid_channel(client):
    r = client.post("/api/integration/sync/run", json={"channel": "nonexistent", "tenant_id": "t1"})
    assert r.status_code == 400


def test_api_webhooks_list(client):
    r = client.get("/api/integration/webhooks?tenant_id=t1")
    assert r.status_code == 200
    data = r.json()
    assert "subscriptions" in data


def test_api_webhooks_create(client):
    r = client.post("/api/integration/webhooks", json={
        "tenant_id": "t1",
        "target_url": "https://example.com/hook",
        "event_types": ["proposal.created"],
    })
    assert r.status_code == 201
    data = r.json()
    assert "id" in data


def test_api_webhooks_delete(client):
    create_r = client.post("/api/integration/webhooks", json={
        "tenant_id": "t1",
        "target_url": "https://example.com/delete-test",
        "event_types": [],
    })
    assert create_r.status_code == 201
    sub_id = create_r.json()["id"]
    del_r = client.delete(f"/api/integration/webhooks/{sub_id}")
    assert del_r.status_code == 200
    assert del_r.json()["deactivated"] is True


def test_api_retry_queue(client):
    r = client.get("/api/integration/retry/queue?tenant_id=t1")
    assert r.status_code == 200
    data = r.json()
    assert "jobs" in data


def test_api_retry_dlq(client):
    r = client.get("/api/integration/retry/dlq?tenant_id=t1")
    assert r.status_code == 200
    data = r.json()
    assert "jobs" in data


def test_api_rate_limits(client):
    r = client.get("/api/integration/rate-limits?tenant_id=t1")
    assert r.status_code == 200
    data = r.json()
    assert "limits" in data


def test_api_dashboard(client):
    r = client.get("/api/integration/dashboard?tenant_id=t1")
    assert r.status_code == 200
    data = r.json()
    assert "sync_health" in data
    assert "dlq_summary" in data
    assert "webhook_delivery" in data


def test_api_ingest_rfp(client):
    r = client.post("/api/integration/ingest/rfp_ingest", json={
        "data": {"content": "Security requirements shall be met.", "filename": "rfp.pdf", "mime_type": "application/pdf"}
    })
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["pipeline"] == "rfp_ingest"


def test_api_ingest_unknown_pipeline(client):
    r = client.post("/api/integration/ingest/nonexistent", json={"data": {}})
    assert r.status_code == 400


def test_api_rbac_permissions_admin(client):
    r = client.get("/api/integration/rbac/permissions?role=admin")
    assert r.status_code == 200
    data = r.json()
    assert "permissions" in data
    assert len(data["permissions"]) > 0


def test_api_rbac_permissions_unknown_role(client):
    r = client.get("/api/integration/rbac/permissions?role=not_a_role")
    assert r.status_code == 404


def test_api_integration_health(client):
    r = client.get("/api/integration/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["registered_connectors"] == 12
