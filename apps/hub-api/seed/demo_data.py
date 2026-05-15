"""
Run: python -m seed.demo_data
Seeds 6 RFPs, 6 clients, 8 stakeholders, approvals, and SLA configs.
Safe to re-run — checks for existing data first.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from datetime import datetime, timedelta
from sqlalchemy import select
from db.database import SessionLocal, init_db
from models import (
    Client, Opportunity, Stakeholder, Proposal,
    Assignment, SlaConfig, ActivityFeed, AuditLog,
)
from models.approval import Approval, SmeRoutingRule


SLA_DEFAULTS = [
    ("intake",            4,  "presales_lead"),
    ("qualification",    24,  "presales_lead"),
    ("sme_assignment",    8,  "presales_lead"),
    ("drafting",         72,  "solution_architect"),
    ("technical_review", 24,  "solution_architect"),
    ("security_review",  24,  "security_reviewer"),
    ("finance_review",   16,  "finance"),
    ("legal_review",     24,  "legal"),
    ("approval",          4,  "presales_lead"),
    ("submission",        2,  "presales_lead"),
]

ROUTING_RULES = [
    ("SOC Transformation",  "SOC",              "Cybersecurity", 1),
    ("SOC Transformation",  "SIEM",             "Cybersecurity", 2),
    ("SOC Transformation",  "Threat Detection", "Cybersecurity", 3),
    ("Zero Trust",          "Zero Trust",       "Cybersecurity", 1),
    ("Zero Trust",          "IAM",              "Cybersecurity", 2),
    ("Zero Trust",          "Network Security", "Infrastructure", 3),
    ("AI Governance",       "AI Security",      "AI",            1),
    ("AI Governance",       "Compliance",       "Compliance",    2),
    ("AI Governance",       "Risk",             "Compliance",    3),
    ("SIEM Migration",      "SIEM",             "Cybersecurity", 1),
    ("SIEM Migration",      "Log Management",   "Cybersecurity", 2),
    ("SIEM Migration",      "SOC",              "Cybersecurity", 3),
    ("Cloud Modernization", "Cloud Security",   "Cloud",         1),
    ("Cloud Modernization", "DevSecOps",        "Cloud",         2),
    ("Compliance Automation","Compliance",      "Compliance",    1),
    ("Compliance Automation","Risk",            "Compliance",    2),
]

STAKEHOLDERS_DATA = [
    {
        "name": "Arjun Kumar",
        "role": "presales_lead",
        "bu": "Cybersecurity",
        "expertise": ["SOC", "SIEM", "Zero Trust", "Threat Detection"],
        "email": "arjun.kumar@sisa.com",
        "current_workload": 3,
    },
    {
        "name": "Sneha Sharma",
        "role": "solution_architect",
        "bu": "Cloud",
        "expertise": ["Cloud Security", "DevSecOps", "IAM", "Network Security"],
        "email": "sneha.sharma@sisa.com",
        "current_workload": 2,
    },
    {
        "name": "Rajiv Nair",
        "role": "sme",
        "bu": "Cybersecurity",
        "expertise": ["SOC", "Threat Detection", "SIEM", "DFIR"],
        "email": "rajiv.nair@sisa.com",
        "current_workload": 2,
    },
    {
        "name": "Priya Singh",
        "role": "sme",
        "bu": "Compliance",
        "expertise": ["Compliance", "Risk", "AI Security", "ISO 27001"],
        "email": "priya.singh@sisa.com",
        "current_workload": 1,
    },
    {
        "name": "Vikram Mehta",
        "role": "security_reviewer",
        "bu": "Cybersecurity",
        "expertise": ["Zero Trust", "IAM", "Network Security", "Pen Testing"],
        "email": "vikram.mehta@sisa.com",
        "current_workload": 1,
    },
    {
        "name": "Deepa Rao",
        "role": "finance",
        "bu": "Finance",
        "expertise": ["Pricing", "Commercial Review"],
        "email": "deepa.rao@sisa.com",
        "current_workload": 0,
    },
    {
        "name": "Karan Joshi",
        "role": "legal",
        "bu": "Legal",
        "expertise": ["Contract Review", "Compliance", "Risk"],
        "email": "karan.joshi@sisa.com",
        "current_workload": 0,
    },
    {
        "name": "Anika Reddy",
        "role": "sme",
        "bu": "AI",
        "expertise": ["AI Security", "LLM Security", "Compliance"],
        "email": "anika.reddy@sisa.com",
        "current_workload": 1,
    },
]

CLIENTS_DATA = [
    {"name": "HDFC Bank",       "sector": "Banking",       "region": "Mumbai",    "tier": "Enterprise"},
    {"name": "Infosys",         "sector": "IT",            "region": "Bengaluru", "tier": "Enterprise"},
    {"name": "Apollo Hospitals","sector": "Healthcare",    "region": "Hyderabad", "tier": "Enterprise"},
    {"name": "DRDO",            "sector": "Government",    "region": "Delhi",     "tier": "Enterprise"},
    {"name": "Titan Industries","sector": "Manufacturing", "region": "Bengaluru", "tier": "Mid-Market"},
    {"name": "Flipkart",        "sector": "Retail",        "region": "Bengaluru", "tier": "Enterprise"},
]

# (title, client_idx, rfp_type, value, win_prob, stage, health, days_in_stage, deadline_days)
OPPORTUNITIES_DATA = [
    ("SOC Transformation",      0, "SOC Transformation",  2.4, 75, "security_review",  87, 18,  45),
    ("Zero Trust Rollout",      1, "Zero Trust",          1.8, 85, "approval",          92, 6,   30),
    ("SIEM Migration",          2, "SIEM Migration",      1.1, 60, "drafting",          71, 40,  60),
    ("AI Governance Platform",  3, "AI Governance",       3.2, 50, "sme_assignment",    55, 5,   90),
    ("Cloud Modernization",     4, "Cloud Modernization", 0.9, 65, "qualification",     68, 20,  75),
    ("Compliance Automation",   5, "Compliance Automation",1.4, 70, "technical_review", 79, 22,  50),
]

# activity entries per opportunity (actor, action_type, description, is_alert, hours_ago)
ACTIVITY_SEED = {
    0: [  # HDFC SOC Transformation
        ("Rajiv Nair",   "stage_transition",  "Moved to Security Review",          False, 18*24),
        ("Arjun Kumar",  "sme_assigned",      "SME auto-assigned: SOC → Rajiv Nair",False, 19*24),
        ("Sneha Sharma", "stage_transition",  "Draft submitted for review",         False, 20*24),
        ("SLA Monitor",  "sla_breach",        "⚠ Security Review approaching SLA", True,  2),
    ],
    1: [  # Infosys Zero Trust (OVERDUE)
        ("SLA Monitor",  "sla_breach",        "SLA breached: Approval overdue by 2h", True, 2),
        ("Arjun Kumar",  "stage_transition",  "Moved to Approval",                  False, 6*24),
        ("Vikram Mehta", "approval_decision", "Vikram approved Legal Review",        False, 7*24),
        ("Deepa Rao",    "approval_decision", "Deepa approved Finance Review",       False, 8*24),
    ],
    2: [  # Apollo SIEM Migration
        ("Rajiv Nair",   "stage_transition",  "Drafting in progress",               False, 40*24),
        ("Arjun Kumar",  "sme_assigned",      "SME assigned: SIEM → Rajiv Nair",    False, 42*24),
    ],
    3: [  # DRDO AI Governance
        ("System",       "sme_assigned",      "Auto-routing SME for AI Governance", False, 5*24),
        ("Arjun Kumar",  "stage_transition",  "Moved to SME Assignment",            False, 6*24),
    ],
    4: [  # Titan Cloud
        ("Sneha Sharma", "stage_transition",  "Qualification call completed",       False, 3*24),
    ],
    5: [  # Flipkart Compliance
        ("Priya Singh",  "stage_transition",  "Technical review in progress",       False, 22*24),
        ("Arjun Kumar",  "sme_assigned",      "SME assigned: Compliance → Priya",   False, 23*24),
    ],
}


def seed():
    init_db()
    db = SessionLocal()
    try:
        # Idempotency: skip if data exists
        if db.scalar(select(Client)) is not None:
            print("Demo data already exists — skipping seed.")
            return

        print("Seeding SLA configs...")
        for stage, hours, role in SLA_DEFAULTS:
            db.merge(SlaConfig(stage=stage, hours_allowed=hours, escalate_to_role=role))

        print("Seeding routing rules...")
        for rfp, skill, bu, priority in ROUTING_RULES:
            db.add(SmeRoutingRule(rfp_type=rfp, required_expertise=skill, bu=bu, priority=priority))

        print("Seeding stakeholders...")
        stakeholders = []
        for sd in STAKEHOLDERS_DATA:
            s = Stakeholder(**sd)
            db.add(s)
            stakeholders.append(s)
        db.flush()

        print("Seeding clients and opportunities...")
        clients = []
        for cd in CLIENTS_DATA:
            c = Client(**cd)
            db.add(c)
            clients.append(c)
        db.flush()

        presales_lead = next(s for s in stakeholders if s.role == "presales_lead")
        finance_reviewer = next(s for s in stakeholders if s.role == "finance")
        legal_reviewer = next(s for s in stakeholders if s.role == "legal")
        security_reviewer = next(s for s in stakeholders if s.role == "security_reviewer")

        opportunities = []
        proposals = []

        for i, (title, client_idx, rfp_type, value, win_prob, stage, health, days_old, deadline_days) in enumerate(OPPORTUNITIES_DATA):
            created = datetime.utcnow() - timedelta(days=days_old + 5)
            updated = datetime.utcnow() - timedelta(days=days_old)

            opp = Opportunity(
                client_id=clients[client_idx].id,
                title=title,
                rfp_type=rfp_type,
                deal_value_cr=value,
                win_probability=win_prob,
                stage=stage,
                owner_id=presales_lead.id,
                deadline=(datetime.utcnow() + timedelta(days=deadline_days)).date(),
                created_at=created,
                updated_at=updated,
            )
            db.add(opp)
            opportunities.append(opp)

        db.flush()

        for i, opp in enumerate(opportunities):
            _, _, _, _, _, stage, health, days_old, _ = OPPORTUNITIES_DATA[i]
            created = datetime.utcnow() - timedelta(days=days_old + 5)
            updated = datetime.utcnow() - timedelta(days=days_old)

            proposal = Proposal(
                opportunity_id=opp.id,
                stage=stage,
                health_score=health,
                content={
                    "exec_summary": f"Executive summary for {opp.title}",
                    "scope": "TBD",
                    "pricing": {"total_cr": float(opp.deal_value_cr or 0)},
                },
                created_at=created,
                updated_at=updated,
            )
            db.add(proposal)
            proposals.append(proposal)

        db.flush()

        # Approvals for Infosys Zero Trust (OVERDUE — in approval stage)
        infosys_proposal = proposals[1]
        sla_approval = next((s for s in SLA_DEFAULTS if s[0] == "approval"), None)
        approval_due = datetime.utcnow() - timedelta(hours=2)  # already overdue

        for order, (approver, stg) in enumerate([
            (security_reviewer, "security_review"),
            (finance_reviewer, "finance_review"),
            (legal_reviewer, "legal_review"),
        ]):
            db.add(Approval(
                proposal_id=infosys_proposal.id,
                approver_id=approver.id,
                stage=stg,
                order_index=order,
                status="approved",
                decided_at=datetime.utcnow() - timedelta(hours=8 - order),
                due_at=datetime.utcnow() - timedelta(hours=5),
            ))

        # Final approval still pending (overdue)
        db.add(Approval(
            proposal_id=infosys_proposal.id,
            approver_id=presales_lead.id,
            stage="approval",
            order_index=3,
            status="pending",
            due_at=approval_due,
        ))

        # Assignments
        sme_map = {
            0: next(s for s in stakeholders if s.name == "Rajiv Nair"),
            1: next(s for s in stakeholders if s.name == "Vikram Mehta"),
            2: next(s for s in stakeholders if s.name == "Rajiv Nair"),
            3: next(s for s in stakeholders if s.name == "Anika Reddy"),
            4: next(s for s in stakeholders if s.name == "Sneha Sharma"),
            5: next(s for s in stakeholders if s.name == "Priya Singh"),
        }

        for i, proposal in enumerate(proposals):
            sme = sme_map.get(i)
            if sme:
                db.add(Assignment(
                    proposal_id=proposal.id,
                    stakeholder_id=sme.id,
                    role="sme",
                    bu=sme.bu,
                    status="in_progress" if i in (0, 1, 2, 5) else "pending",
                    assigned_at=datetime.utcnow() - timedelta(days=OPPORTUNITIES_DATA[i][7]),
                ))

        # Activity feed
        for opp_idx, activities in ACTIVITY_SEED.items():
            proposal = proposals[opp_idx]
            for actor, action_type, description, is_alert, hours_ago in activities:
                db.add(ActivityFeed(
                    proposal_id=proposal.id,
                    actor_name=actor,
                    action_type=action_type,
                    description=description,
                    is_alert=is_alert,
                    created_at=datetime.utcnow() - timedelta(hours=hours_ago),
                ))

        # Audit log entries
        for opp in opportunities:
            db.add(AuditLog(
                entity_type="opportunity",
                entity_id=opp.id,
                actor_id=presales_lead.id,
                action="created",
                to_state="intake",
                occurred_at=opp.created_at,
            ))

        db.commit()
        print(f"✓ Seeded: {len(clients)} clients, {len(stakeholders)} stakeholders, {len(opportunities)} opportunities")
        print("  HDFC SOC Transformation  → security_review  (score: 87)")
        print("  Infosys Zero Trust       → approval         (score: 92, OVERDUE)")
        print("  Apollo SIEM Migration    → drafting         (score: 71)")
        print("  DRDO AI Governance       → sme_assignment   (score: 55)")
        print("  Titan Cloud              → qualification    (score: 68)")
        print("  Flipkart Compliance      → technical_review (score: 79)")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
