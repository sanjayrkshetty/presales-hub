"""
B13 — Parallel Review Workflow HTTP 500 regression tests.

Root cause: parallel review creation used Assignment records with nullable
stakeholder_id, causing integrity errors. Fix: use Approval records with
role-based routing for all 3 parallel review stages on drafting → review transition.
"""
from models import Stakeholder, Client, Opportunity, Proposal, SlaConfig
from models.proposal import PARALLEL_REVIEW_GROUP


def _seed_proposal_in_drafting(db):
    """Seed minimal data: proposal in drafting stage, required reviewers, SLA configs."""
    architect = Stakeholder(name="Sneha Sharma", role="solution_architect", bu="Cloud", expertise=[], current_workload=0)
    reviewer  = Stakeholder(name="Vikram Mehta", role="security_reviewer",  bu="Cyber", expertise=[], current_workload=0)
    db.add_all([architect, reviewer])
    db.flush()

    # SLA configs so due_at can be calculated (not strictly required but realistic)
    for stage, hours in [("technical_review", 24), ("security_review", 24), ("delivery_review", 24)]:
        db.merge(SlaConfig(stage=stage, hours_allowed=hours, escalate_to_role="presales_lead"))

    client = Client(name="ParallelCo")
    db.add(client)
    db.flush()

    opp = Opportunity(client_id=client.id, title="Parallel Review RFP", stage="drafting")
    db.add(opp)
    db.flush()

    proposal = Proposal(opportunity_id=opp.id, stage="drafting")
    db.add(proposal)
    db.commit()

    return proposal.id


def test_b13_creates_three_approval_records(client, db):
    """Transitioning from drafting to a parallel review stage must create 3 Approvals."""
    proposal_id = _seed_proposal_in_drafting(db)

    resp = client.post(f"/api/proposals/{proposal_id}/transition", json={
        "to_stage": "technical_review",
    })

    assert resp.status_code == 200, resp.json()

    approvals_resp = client.get(f"/api/proposals/{proposal_id}/approvals")
    assert approvals_resp.status_code == 200

    approvals = approvals_resp.json()
    assert len(approvals) == 3, f"Expected 3 approvals, got {len(approvals)}: {approvals}"


def test_b13_all_three_review_stages_covered(client, db):
    """All 3 stages — technical, security, delivery — must be present."""
    proposal_id = _seed_proposal_in_drafting(db)

    client.post(f"/api/proposals/{proposal_id}/transition", json={
        "to_stage": "security_review",
    })

    approvals = client.get(f"/api/proposals/{proposal_id}/approvals").json()
    stages = {a["stage"] for a in approvals}

    assert stages == PARALLEL_REVIEW_GROUP


def test_b13_all_approvals_start_pending(client, db):
    """Newly created parallel review Approvals must have status='pending'."""
    proposal_id = _seed_proposal_in_drafting(db)

    client.post(f"/api/proposals/{proposal_id}/transition", json={
        "to_stage": "delivery_review",
    })

    approvals = client.get(f"/api/proposals/{proposal_id}/approvals").json()
    statuses = {a["status"] for a in approvals}

    assert statuses == {"pending"}


def test_b13_no_duplicate_approvals_on_reentry(client, db):
    """
    If a proposal returns to drafting and re-enters a parallel review stage,
    existing Approval records must not be duplicated.
    """
    proposal_id = _seed_proposal_in_drafting(db)

    # First entry into parallel review
    client.post(f"/api/proposals/{proposal_id}/transition", json={"to_stage": "technical_review"})

    # Return to drafting (allowed by TRANSITIONS)
    client.post(f"/api/proposals/{proposal_id}/transition", json={"to_stage": "drafting"})

    # Re-enter parallel review — existing stages must not generate duplicates
    client.post(f"/api/proposals/{proposal_id}/transition", json={"to_stage": "technical_review"})

    approvals = client.get(f"/api/proposals/{proposal_id}/approvals").json()
    # Still exactly 3, not 6
    assert len(approvals) == 3


def test_b13_approvals_not_assignments(client, db):
    """Fix explicitly uses Approval records — the GET approvals endpoint must return them."""
    proposal_id = _seed_proposal_in_drafting(db)

    client.post(f"/api/proposals/{proposal_id}/transition", json={"to_stage": "technical_review"})

    resp = client.get(f"/api/proposals/{proposal_id}/approvals")
    assert resp.status_code == 200

    # Each record must have approval-specific fields, not assignment-specific fields
    for approval in resp.json():
        assert "stage" in approval
        assert "status" in approval
        assert "parallel_group" in approval
        assert approval["parallel_group"] == "review_round_1"
