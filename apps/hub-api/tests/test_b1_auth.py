"""
B1 — Approval Authorization Bypass regression tests.

Any actor could previously approve any approval request.
Fix: enforce actor_id == approver_id when both are set; log unauthorized attempts.
"""
from sqlalchemy import select

from models import Stakeholder, Client, Opportunity, Proposal, AuditLog
from models.approval import Approval


def _seed(db):
    """Seed two stakeholders, one opportunity, one proposal, one approval."""
    approver = Stakeholder(name="Alice", role="presales_lead")
    intruder = Stakeholder(name="Bob", role="presales_lead")
    db.add_all([approver, intruder])
    db.flush()

    client = Client(name="TestCo")
    db.add(client)
    db.flush()

    opp = Opportunity(client_id=client.id, title="Test RFP", stage="approval")
    db.add(opp)
    db.flush()

    proposal = Proposal(opportunity_id=opp.id, stage="approval")
    db.add(proposal)
    db.flush()

    approval = Approval(
        proposal_id=proposal.id,
        approver_id=approver.id,
        stage="approval",
        status="pending",
    )
    db.add(approval)
    db.commit()

    return approval.id, approver.id, intruder.id


def test_b1_wrong_actor_returns_403(client, db):
    approval_id, approver_id, intruder_id = _seed(db)

    resp = client.post(f"/api/approvals/{approval_id}/decide", json={
        "status": "approved",
        "actor_id": intruder_id,
    })

    assert resp.status_code == 403
    body = resp.json()
    assert "Not authorized" in body["detail"]


def test_b1_correct_actor_returns_200(client, db):
    approval_id, approver_id, _ = _seed(db)

    resp = client.post(f"/api/approvals/{approval_id}/decide", json={
        "status": "approved",
        "actor_id": approver_id,
    })

    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


def test_b1_unauthorized_attempt_is_logged(client, db):
    approval_id, approver_id, intruder_id = _seed(db)

    client.post(f"/api/approvals/{approval_id}/decide", json={
        "status": "approved",
        "actor_id": intruder_id,
    })

    # Audit log entry must be written even though the request was rejected
    session = db.get_bind()
    from sqlalchemy.orm import Session
    audit_session = Session(bind=session)
    logs = audit_session.scalars(
        select(AuditLog).where(AuditLog.action == "unauthorized_approval_attempt")
    ).all()
    audit_session.close()

    assert len(logs) == 1
    assert logs[0].actor_id == intruder_id


def test_b1_no_actor_id_bypasses_auth_check(client, db):
    """System-driven decisions (actor_id omitted) must be allowed through."""
    approval_id, _, _ = _seed(db)

    resp = client.post(f"/api/approvals/{approval_id}/decide", json={
        "status": "approved",
    })

    assert resp.status_code == 200


def test_b1_unassigned_approval_allows_any_actor(client, db):
    """Approvals with no assigned approver_id must not block any actor."""
    client_obj = Client(name="OpenCo")
    db.add(client_obj)
    db.flush()

    opp = Opportunity(client_id=client_obj.id, title="Open RFP", stage="approval")
    db.add(opp)
    db.flush()

    proposal = Proposal(opportunity_id=opp.id, stage="approval")
    db.add(proposal)
    db.flush()

    unassigned = Approval(
        proposal_id=proposal.id,
        approver_id=None,
        stage="approval",
        status="pending",
    )
    db.add(unassigned)

    actor = Stakeholder(name="Random Actor", role="presales_lead")
    db.add(actor)
    db.commit()

    resp = client.post(f"/api/approvals/{unassigned.id}/decide", json={
        "status": "approved",
        "actor_id": actor.id,
    })

    assert resp.status_code == 200
