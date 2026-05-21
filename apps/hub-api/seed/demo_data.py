"""
Run: python -m seed.demo_data [--reset]
  --reset  wipe the DB and reseed from scratch (required when schema or timestamps change)

Seeds 6 RFPs across 5 sectors with realistic, stage-appropriate SLA timing so the dashboard
looks operational. All timestamps are computed relative to datetime.utcnow() at seed time.
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
    ("delivery_review",  24,  "solution_architect"),
    ("finance_review",   16,  "finance"),
    ("legal_review",     24,  "legal"),
    ("approval",          4,  "presales_lead"),
    ("submission",        2,  "presales_lead"),
]

ROUTING_RULES = [
    ("SOC Transformation",   "SOC",            "Cybersecurity",  1),
    ("SOC Transformation",   "SIEM",           "Cybersecurity",  2),
    ("SOC Transformation",   "Threat Detection","Cybersecurity", 3),
    ("Zero Trust",           "Zero Trust",     "Cybersecurity",  1),
    ("Zero Trust",           "IAM",            "Cybersecurity",  2),
    ("Zero Trust",           "Network Security","Infrastructure", 3),
    ("AI Governance",        "AI Security",    "AI",             1),
    ("AI Governance",        "Compliance",     "Compliance",     2),
    ("AI Governance",        "Risk",           "Compliance",     3),
    ("SIEM Migration",       "SIEM",           "Cybersecurity",  1),
    ("SIEM Migration",       "Log Management", "Cybersecurity",  2),
    ("SIEM Migration",       "SOC",            "Cybersecurity",  3),
    ("Cloud Modernization",  "Cloud Security", "Cloud",          1),
    ("Cloud Modernization",  "DevSecOps",      "Cloud",          2),
    ("Compliance Automation","Compliance",     "Compliance",     1),
    ("Compliance Automation","Risk",           "Compliance",     2),
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
    {"name": "HDFC Bank",        "sector": "Banking",       "region": "Mumbai",    "tier": "Enterprise"},
    {"name": "Infosys",          "sector": "IT",            "region": "Bengaluru", "tier": "Enterprise"},
    {"name": "Apollo Hospitals", "sector": "Healthcare",    "region": "Hyderabad", "tier": "Enterprise"},
    {"name": "DRDO",             "sector": "Government",    "region": "Delhi",     "tier": "Enterprise"},
    {"name": "Titan Industries", "sector": "Manufacturing", "region": "Bengaluru", "tier": "Mid-Market"},
    {"name": "Flipkart",         "sector": "Retail",        "region": "Bengaluru", "tier": "Enterprise"},
]

# hours_in_stage: how long the opp has been in its current stage, relative to utcnow().
# Chosen so the dashboard shows a realistic mix: 1 breach, 3 warnings, 2 healthy.
#   SLA check: warning = hours_remaining < 0.25 * hours_allowed
#
# (title, client_idx, rfp_type, value, win_prob, stage, health, hours_in_stage, deadline_days)
OPPORTUNITIES_DATA = [
    ("SOC Transformation",      0, "SOC Transformation",   2.4, 75, "security_review",  87, 20, 45),
    # 20h elapsed / 24h SLA → warning zone (4h left, threshold = 6h)

    ("Zero Trust Rollout",      1, "Zero Trust",           1.8, 85, "approval",          92,  5, 30),
    # 5h elapsed / 4h SLA → OVERDUE by 1h — the intentional demo breach

    ("SIEM Migration",          2, "SIEM Migration",       1.1, 60, "drafting",          71, 60, 60),
    # 60h elapsed / 72h SLA → warning zone (12h left, threshold = 18h)

    ("AI Governance Platform",  3, "AI Governance",        3.2, 50, "sme_assignment",    55,  3, 90),
    # 3h elapsed / 8h SLA → healthy (5h left)

    ("Cloud Modernization",     4, "Cloud Modernization",  0.9, 65, "qualification",     68, 20, 75),
    # 20h elapsed / 24h SLA → warning zone (4h left)

    ("Compliance Automation",   5, "Compliance Automation",1.4, 70, "technical_review",  79, 20, 50),
    # 20h elapsed / 24h SLA → warning zone (4h left)
]


def seed():
    init_db()
    db = SessionLocal()
    try:
        if db.scalar(select(Client)) is not None:
            print("Demo data already exists — use --reset to wipe and reseed.")
            return

        now = datetime.utcnow()

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

        presales_lead      = next(s for s in stakeholders if s.role == "presales_lead")
        solution_architect = next(s for s in stakeholders if s.role == "solution_architect")
        finance_reviewer   = next(s for s in stakeholders if s.role == "finance")
        legal_reviewer     = next(s for s in stakeholders if s.role == "legal")
        security_reviewer  = next(s for s in stakeholders if s.role == "security_reviewer")

        print("Seeding clients and opportunities...")
        clients = []
        for cd in CLIENTS_DATA:
            c = Client(**cd)
            db.add(c)
            clients.append(c)
        db.flush()

        opportunities = []
        proposals = []

        for i, (title, client_idx, rfp_type, value, win_prob, stage, health, hours_in_stage, deadline_days) in enumerate(OPPORTUNITIES_DATA):
            created = now - timedelta(days=14)
            updated = now - timedelta(hours=hours_in_stage)

            opp = Opportunity(
                client_id=clients[client_idx].id,
                title=title,
                rfp_type=rfp_type,
                deal_value_cr=value,
                win_probability=win_prob,
                stage=stage,
                owner_id=presales_lead.id,
                deadline=(now + timedelta(days=deadline_days)).date(),
                created_at=created,
                updated_at=updated,
            )
            db.add(opp)
            opportunities.append(opp)

        db.flush()

        for i, opp in enumerate(opportunities):
            _, _, _, _, _, stage, health, hours_in_stage, _ = OPPORTUNITIES_DATA[i]
            created = now - timedelta(days=14)
            updated = now - timedelta(hours=hours_in_stage)

            proposal = Proposal(
                opportunity_id=opp.id,
                stage=stage,
                health_score=health,
                content={
                    "exec_summary": f"Executive summary for {opp.title}",
                    "scope": "To be defined in discovery phase",
                    "pricing": {"total_cr": float(opp.deal_value_cr or 0)},
                },
                created_at=created,
                updated_at=updated,
            )
            db.add(proposal)
            proposals.append(proposal)

        db.flush()

        soc_proposal        = proposals[0]  # HDFC — security_review
        infosys_proposal    = proposals[1]  # Infosys — approval (OVERDUE)
        compliance_proposal = proposals[5]  # Flipkart — technical_review

        # ── Parallel review Approvals: SOC Transformation (currently in security_review)
        # All 3 parallel review Approval records must exist. SOC is in the security_review
        # stage; technical and delivery are pending alongside it.
        for review_stage, reviewer in [
            ("technical_review", solution_architect),
            ("security_review",  security_reviewer),
            ("delivery_review",  solution_architect),
        ]:
            sla_hrs = next((h for s, h, _ in SLA_DEFAULTS if s == review_stage), 24)
            db.add(Approval(
                proposal_id=soc_proposal.id,
                approver_id=reviewer.id,
                stage=review_stage,
                parallel_group="review_round_1",
                order_index=0,
                status="pending",
                due_at=now - timedelta(hours=OPPORTUNITIES_DATA[0][7]) + timedelta(hours=sla_hrs),
            ))

        # ── Parallel review Approvals: Compliance Automation (currently in technical_review)
        for review_stage, reviewer in [
            ("technical_review", solution_architect),
            ("security_review",  security_reviewer),
            ("delivery_review",  solution_architect),
        ]:
            sla_hrs = next((h for s, h, _ in SLA_DEFAULTS if s == review_stage), 24)
            db.add(Approval(
                proposal_id=compliance_proposal.id,
                approver_id=reviewer.id,
                stage=review_stage,
                parallel_group="review_round_1",
                order_index=0,
                status="pending",
                due_at=now - timedelta(hours=OPPORTUNITIES_DATA[5][7]) + timedelta(hours=sla_hrs),
            ))

        # ── Infosys Zero Trust (approval stage, OVERDUE)
        # Full chain: technical + delivery (approved), security + finance + legal (approved), final pending
        for order, (approver, stg, approved_hours_ago) in enumerate([
            (solution_architect, "technical_review", 10),
            (solution_architect, "delivery_review",  10),
            (security_reviewer,  "security_review",   9),
            (finance_reviewer,   "finance_review",    8),
            (legal_reviewer,     "legal_review",      7),
        ]):
            db.add(Approval(
                proposal_id=infosys_proposal.id,
                approver_id=approver.id,
                stage=stg,
                parallel_group="review_round_1" if stg in ("technical_review", "security_review", "delivery_review") else None,
                order_index=order,
                status="approved",
                decided_at=now - timedelta(hours=approved_hours_ago),
                due_at=now - timedelta(hours=approved_hours_ago - 2),
            ))

        # Final approval: pending and overdue (the demo's live tension)
        db.add(Approval(
            proposal_id=infosys_proposal.id,
            approver_id=presales_lead.id,
            stage="approval",
            order_index=5,
            status="pending",
            due_at=now - timedelta(hours=1),   # due 1h ago → OVERDUE
        ))

        # ── SME Assignments
        sme_map = {
            0: next(s for s in stakeholders if s.name == "Rajiv Nair"),    # SOC
            1: next(s for s in stakeholders if s.name == "Vikram Mehta"),  # Zero Trust
            2: next(s for s in stakeholders if s.name == "Rajiv Nair"),    # SIEM
            3: next(s for s in stakeholders if s.name == "Anika Reddy"),   # AI Gov
            4: next(s for s in stakeholders if s.name == "Sneha Sharma"),  # Cloud
            5: next(s for s in stakeholders if s.name == "Priya Singh"),   # Compliance
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
                    assigned_at=now - timedelta(days=14) + timedelta(days=1),
                ))

        # ── Activity feed (realistic event history per opportunity)
        activity_seed = {
            0: [  # HDFC SOC
                ("Rajiv Nair",   "stage_transition",  "Entered parallel review phase",            False, 20),
                ("Arjun Kumar",  "sme_assigned",      "SME assigned: SOC Transformation → Rajiv", False, 21),
                ("Sneha Sharma", "stage_transition",  "Draft submitted for review",                False, 48),
                ("SLA Monitor",  "sla_breach",        "Warning: Security Review approaching SLA", True,   1),
            ],
            1: [  # Infosys Zero Trust — OVERDUE
                ("SLA Monitor",  "sla_breach",        "SLA BREACHED: Approval overdue by 1h",     True,   1),
                ("Arjun Kumar",  "stage_transition",  "All reviews passed — moved to Approval",   False,  5),
                ("Karan Joshi",  "approval_decision", "Karan Joshi approved Legal Review",        False,  7),
                ("Deepa Rao",    "approval_decision", "Deepa Rao approved Finance Review",        False,  8),
                ("Vikram Mehta", "approval_decision", "Vikram Mehta approved Security Review",    False,  9),
            ],
            2: [  # Apollo SIEM
                ("Rajiv Nair",   "stage_transition",  "Drafting in progress — 60h elapsed",       False, 60),
                ("Arjun Kumar",  "sme_assigned",      "SME assigned: SIEM Migration → Rajiv",     False, 62),
            ],
            3: [  # DRDO AI Gov
                ("System",       "sme_assigned",      "Auto-routing SME for AI Governance",       False,  3),
                ("Arjun Kumar",  "stage_transition",  "Moved to SME Assignment",                  False,  4),
            ],
            4: [  # Titan Cloud
                ("Sneha Sharma", "stage_transition",  "Qualification call completed",              False, 20),
            ],
            5: [  # Flipkart Compliance
                ("Priya Singh",  "stage_transition",  "Entered parallel technical review",         False, 20),
                ("Arjun Kumar",  "sme_assigned",      "SME assigned: Compliance → Priya Singh",   False, 22),
            ],
        }

        for opp_idx, activities in activity_seed.items():
            proposal = proposals[opp_idx]
            for actor, action_type, description, is_alert, hours_ago in activities:
                db.add(ActivityFeed(
                    proposal_id=proposal.id,
                    actor_name=actor,
                    action_type=action_type,
                    description=description,
                    is_alert=is_alert,
                    created_at=now - timedelta(hours=hours_ago),
                ))

        # ── Audit log baseline
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
        print(f"[OK] Seeded: {len(clients)} clients, {len(stakeholders)} stakeholders, {len(opportunities)} opportunities")
        print("  HDFC SOC Transformation  -> security_review  (score: 87, WARNING - 4h left)")
        print("  Infosys Zero Trust       -> approval         (score: 92, BREACHED - 1h overdue)")
        print("  Apollo SIEM Migration    -> drafting         (score: 71, WARNING - 12h left)")
        print("  DRDO AI Governance       -> sme_assignment   (score: 55, OK - 5h left)")
        print("  Titan Cloud              -> qualification    (score: 68, WARNING - 4h left)")
        print("  Flipkart Compliance      -> technical_review (score: 79, WARNING - 4h left)")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Seed PRESALES HUB demo data")
    parser.add_argument("--reset", action="store_true", help="Wipe DB and reseed from scratch")
    args = parser.parse_args()

    if args.reset:
        db_file = os.path.join(os.path.dirname(__file__), "..", "presales_hub.db")
        db_file = os.path.normpath(db_file)
        if os.path.exists(db_file):
            os.remove(db_file)
            print(f"Wiped: {db_file}")

    seed()
