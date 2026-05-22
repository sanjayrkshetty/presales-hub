"""
B2 — Parallel Review Gate Enforcement regression tests.

Before the fix, a proposal in any parallel review stage could skip directly to
finance_review without all three reviews (technical, security, delivery) being approved.
Fix: gate the transition until all 3 Approval records exist and have status='approved'.
"""
from models import Stakeholder, Client, Opportunity, Proposal
from models.approval import Approval
from models.proposal import PARALLEL_REVIEW_GROUP


def _seed_proposal_in_review(db, stage="security_review"):
    """Create a proposal in the given parallel review stage."""
    owner = Stakeholder(name="Presales Lead", role="presales_lead")
    db.add(owner)
    db.flush()

    client = Client(name="GateCo")
    db.add(client)
    db.flush()

    opp = Opportunity(client_id=client.id, title="Gate Test RFP", stage=stage, owner_id=owner.id)
    db.add(opp)
    db.flush()

    proposal = Proposal(opportunity_id=opp.id, stage=stage)
    db.add(proposal)
    db.flush()
    db.commit()

    return proposal.id


def _add_parallel_approvals(db, proposal_id, statuses: dict[str, str]):
    """
    Add Approval records for the parallel review stages with given statuses.
    statuses: {"technical_review": "approved", "security_review": "pending", ...}
    """
    for stage, status in statuses.items():
        db.add(Approval(
            proposal_id=proposal_id,
            stage=stage,
            parallel_group="review_round_1",
            order_index=0,
            status=status,
        ))
    db.commit()


def test_b2_no_parallel_approvals_blocks_finance(client, db):
    """Zero approval records → finance_review must be rejected with 422."""
    proposal_id = _seed_proposal_in_review(db)

    resp = client.post(f"/api/proposals/{proposal_id}/transition", json={
        "to_stage": "finance_review",
    })

    assert resp.status_code == 422
    assert "not yet initialized" in resp.json()["detail"]


def test_b2_partial_approvals_blocks_finance(client, db):
    """Only 1 of 3 parallel approvals approved → must still be blocked."""
    proposal_id = _seed_proposal_in_review(db)
    _add_parallel_approvals(db, proposal_id, {
        "technical_review": "approved",
        "security_review":  "pending",
        "delivery_review":  "pending",
    })

    resp = client.post(f"/api/proposals/{proposal_id}/transition", json={
        "to_stage": "finance_review",
    })

    assert resp.status_code == 422
    assert "pending" in resp.json()["detail"].lower()


def test_b2_two_of_three_approved_blocks_finance(client, db):
    """2 of 3 approved → still blocked."""
    proposal_id = _seed_proposal_in_review(db)
    _add_parallel_approvals(db, proposal_id, {
        "technical_review": "approved",
        "security_review":  "approved",
        "delivery_review":  "pending",
    })

    resp = client.post(f"/api/proposals/{proposal_id}/transition", json={
        "to_stage": "finance_review",
    })

    assert resp.status_code == 422


def test_b2_all_three_approved_allows_finance(client, db):
    """All 3 parallel reviews approved → finance_review transition must succeed."""
    proposal_id = _seed_proposal_in_review(db)
    _add_parallel_approvals(db, proposal_id, {
        "technical_review": "approved",
        "security_review":  "approved",
        "delivery_review":  "approved",
    })

    resp = client.post(f"/api/proposals/{proposal_id}/transition", json={
        "to_stage": "finance_review",
    })

    assert resp.status_code == 200
    assert resp.json()["to_stage"] == "finance_review"


def test_b2_gate_only_applies_to_parallel_review_stages(client, db):
    """Gate must not fire for proposals outside the parallel review group."""
    owner = Stakeholder(name="Lead", role="presales_lead")
    db.add(owner)
    db.flush()

    client_obj = Client(name="OtherCo")
    db.add(client_obj)
    db.flush()

    # finance_review → legal_review is a valid transition that should not be gated
    opp = Opportunity(client_id=client_obj.id, title="Finance RFP", stage="finance_review")
    db.add(opp)
    db.flush()

    proposal = Proposal(opportunity_id=opp.id, stage="finance_review")
    db.add(proposal)
    db.commit()

    resp = client.post(f"/api/proposals/{proposal.id}/transition", json={
        "to_stage": "legal_review",
    })

    assert resp.status_code == 200
