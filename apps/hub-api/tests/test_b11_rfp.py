"""
B11 — Unknown RFP Routing Guard regression tests.

Before the fix, assign-sme with an unknown rfp_type silently assigned a random SME.
Fix: return HTTP 404 when no routing rules exist for the given rfp_type.
"""
from models import Stakeholder, Client, Opportunity, Proposal
from models.approval import SmeRoutingRule


def _seed_proposal(db):
    owner = Stakeholder(name="Lead", role="presales_lead")
    db.add(owner)
    db.flush()

    client = Client(name="RouteCo")
    db.add(client)
    db.flush()

    opp = Opportunity(client_id=client.id, title="Route Test RFP", stage="sme_assignment")
    db.add(opp)
    db.flush()

    proposal = Proposal(opportunity_id=opp.id, stage="sme_assignment")
    db.add(proposal)
    db.commit()

    return proposal.id


def test_b11_unknown_rfp_type_returns_404(client, db):
    """No routing rules for rfp_type and no required_skills → must be 404."""
    proposal_id = _seed_proposal(db)

    resp = client.post(f"/api/proposals/{proposal_id}/assign-sme", json={
        "rfp_type": "QuantumThreatAnalysis",
    })

    assert resp.status_code == 404
    body = resp.json()
    assert "No routing rules" in body["detail"]
    assert "QuantumThreatAnalysis" in body["detail"]


def test_b11_known_rfp_type_routes_correctly(client, db):
    """Known rfp_type with matching SME and routing rule must succeed."""
    proposal_id = _seed_proposal(db)

    sme = Stakeholder(
        name="Expert SME",
        role="sme",
        bu="Cybersecurity",
        expertise=["SOC"],
        current_workload=0,
    )
    db.add(sme)
    db.add(SmeRoutingRule(rfp_type="SOC Transformation", required_expertise="SOC", bu="Cybersecurity", priority=1))
    db.commit()

    resp = client.post(f"/api/proposals/{proposal_id}/assign-sme", json={
        "rfp_type": "SOC Transformation",
    })

    assert resp.status_code == 200
    assert resp.json()["assigned"]["name"] == "Expert SME"


def test_b11_required_skills_bypasses_routing_rule_check(client, db):
    """
    If required_skills is explicitly provided, the routing rule guard is bypassed —
    the caller takes responsibility for skill specification.
    """
    proposal_id = _seed_proposal(db)

    sme = Stakeholder(
        name="Skilled SME",
        role="sme",
        bu="Cloud",
        expertise=["Cloud Security"],
        current_workload=1,
    )
    db.add(sme)
    db.commit()

    resp = client.post(f"/api/proposals/{proposal_id}/assign-sme", json={
        "rfp_type": "UnknownType",
        "required_skills": ["Cloud Security"],
    })

    assert resp.status_code == 200
    assert resp.json()["assigned"]["name"] == "Skilled SME"


def test_b11_no_available_smes_returns_422(client, db):
    """All SMEs at max workload → 422, not a silent failure."""
    proposal_id = _seed_proposal(db)

    overloaded = Stakeholder(
        name="Maxed SME",
        role="sme",
        bu="Cybersecurity",
        expertise=["SOC"],
        current_workload=4,  # workload limit is < 4
    )
    db.add(overloaded)
    db.add(SmeRoutingRule(rfp_type="SOC Transformation", required_expertise="SOC", bu="Cybersecurity", priority=1))
    db.commit()

    resp = client.post(f"/api/proposals/{proposal_id}/assign-sme", json={
        "rfp_type": "SOC Transformation",
    })

    assert resp.status_code == 422
    assert "maximum workload" in resp.json()["detail"]
