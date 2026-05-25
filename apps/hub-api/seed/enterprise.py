"""
Enterprise seed engine — generates a realistic 6-month operating history.

Run:
  python -m seed.enterprise           # seeds if empty, skips if data exists
  python -m seed.enterprise --reset   # wipe + reseed

Demo credentials (created every run):
  admin@presaleshub.io / Admin@1234   — platform admin
  arjun@sisa.demo      / Demo@1234   — presales lead
  vikram@sisa.demo     / Demo@1234   — SME security
  priya@sisa.demo      / Demo@1234   — SME compliance
  ceo@sisa.demo        / Demo@1234   — executive
"""
from __future__ import annotations

import json
import os
import random
import sys
from datetime import datetime, timedelta
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import select, text
from db.database import SessionLocal, init_db
from models import Client, Opportunity, Stakeholder, Proposal, Assignment, SlaConfig, ActivityFeed, AuditLog
from models.approval import Approval, SmeRoutingRule
from models.tenant import Tenant
from models.user import User
from core.security import hash_password

# ── Deterministic RNG ─────────────────────────────────────────────────────────
rng = random.Random(42)

# ── Constants ─────────────────────────────────────────────────────────────────
NOW = datetime.utcnow()
SIX_MONTHS_AGO = NOW - timedelta(days=180)

STAGES_ORDER = [
    "intake", "qualification", "sme_assignment", "drafting",
    "technical_review", "security_review", "delivery_review",
    "finance_review", "legal_review", "approval", "submission",
]

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

# ── Tenants ───────────────────────────────────────────────────────────────────
TENANTS = [
    {"org_name": "SISA Information Security",  "tier": "enterprise", "status": "active",    "admin_email": "admin@sisa.demo"},
    {"org_name": "Wipro Security Services",    "tier": "professional","status": "active",    "admin_email": "admin@wipro.demo"},
    {"org_name": "HCL Cybersecurity",          "tier": "professional","status": "active",    "admin_email": "admin@hcl.demo"},
    {"org_name": "IBM Security India",         "tier": "enterprise", "status": "active",    "admin_email": "admin@ibm.demo"},
    {"org_name": "Accenture Security",         "tier": "starter",    "status": "active",    "admin_email": "admin@acc.demo"},
]

# ── Demo users (login credentials) ───────────────────────────────────────────
DEMO_USERS = [
    # (email, password, full_name, roles, tenant_idx)
    ("admin@presaleshub.io", "Admin@1234", "Platform Admin",    ["admin"],        0),
    ("arjun@sisa.demo",      "Demo@1234",  "Arjun Kumar",       ["presales_lead"],0),
    ("vikram@sisa.demo",     "Demo@1234",  "Vikram Mehta",      ["sme"],          0),
    ("priya@sisa.demo",      "Demo@1234",  "Priya Singh",       ["sme"],          0),
    ("ceo@sisa.demo",        "Demo@1234",  "Rajan Desai",       ["executive"],    0),
    ("approver@sisa.demo",   "Demo@1234",  "Neha Gupta",        ["approver"],     0),
]

# ── Stakeholders (presales team members at SISA) ──────────────────────────────
STAKEHOLDERS = [
    {"name": "Arjun Kumar",   "role": "presales_lead",      "bu": "Cybersecurity", "expertise": ["SOC", "SIEM", "Zero Trust", "Threat Detection"],     "email": "arjun@sisa.demo",    "current_workload": 4},
    {"name": "Sneha Sharma",  "role": "solution_architect", "bu": "Cloud",         "expertise": ["Cloud Security", "DevSecOps", "IAM", "Network Security"], "email": "sneha@sisa.demo",    "current_workload": 3},
    {"name": "Rajiv Nair",    "role": "sme",                "bu": "Cybersecurity", "expertise": ["SOC", "Threat Detection", "SIEM", "DFIR"],             "email": "rajiv@sisa.demo",    "current_workload": 3},
    {"name": "Priya Singh",   "role": "sme",                "bu": "Compliance",    "expertise": ["Compliance", "Risk", "AI Security", "ISO 27001"],      "email": "priya@sisa.demo",    "current_workload": 2},
    {"name": "Vikram Mehta",  "role": "security_reviewer",  "bu": "Cybersecurity", "expertise": ["Zero Trust", "IAM", "Network Security", "Pen Testing"],"email": "vikram@sisa.demo",   "current_workload": 2},
    {"name": "Deepa Rao",     "role": "finance",            "bu": "Finance",       "expertise": ["Pricing", "Commercial Review"],                        "email": "deepa@sisa.demo",    "current_workload": 1},
    {"name": "Karan Joshi",   "role": "legal",              "bu": "Legal",         "expertise": ["Contract Review", "Compliance", "Risk"],               "email": "karan@sisa.demo",    "current_workload": 1},
    {"name": "Anika Reddy",   "role": "sme",                "bu": "AI",            "expertise": ["AI Security", "LLM Security", "Compliance"],           "email": "anika@sisa.demo",    "current_workload": 2},
    {"name": "Rajan Desai",   "role": "executive",          "bu": "Leadership",    "expertise": ["Strategy", "BD"],                                      "email": "ceo@sisa.demo",      "current_workload": 0},
    {"name": "Neha Gupta",    "role": "approver",           "bu": "PMO",           "expertise": ["Project Management", "Quality Assurance"],             "email": "approver@sisa.demo", "current_workload": 1},
]

# ── Client universe ───────────────────────────────────────────────────────────
CLIENTS = [
    ("HDFC Bank",               "Banking",            "Mumbai",      "Enterprise"),
    ("Infosys",                 "IT Services",        "Bengaluru",   "Enterprise"),
    ("Apollo Hospitals",        "Healthcare",         "Hyderabad",   "Enterprise"),
    ("DRDO",                    "Government/Defence", "Delhi",       "Enterprise"),
    ("Titan Industries",        "Manufacturing",      "Bengaluru",   "Mid-Market"),
    ("Flipkart",                "E-Commerce",         "Bengaluru",   "Enterprise"),
    ("Tata Steel",              "Manufacturing",      "Jamshedpur",  "Enterprise"),
    ("ONGC",                    "Energy/Oil & Gas",   "Mumbai",      "Enterprise"),
    ("Mahindra Finance",        "NBFC/Finance",       "Mumbai",      "Enterprise"),
    ("Bajaj Electricals",       "Manufacturing",      "Mumbai",      "Mid-Market"),
    ("Manipal Hospitals",       "Healthcare",         "Bengaluru",   "Mid-Market"),
    ("Air India",               "Aviation",           "Delhi",       "Enterprise"),
    ("National Payments Corp",  "Fintech",            "Mumbai",      "Enterprise"),
    ("Bharat Electronics",      "Government/Defence", "Bengaluru",   "Enterprise"),
    ("Paytm",                   "Fintech",            "Noida",       "Mid-Market"),
    ("ICICI Bank",              "Banking",            "Mumbai",      "Enterprise"),
    ("Wipro",                   "IT Services",        "Bengaluru",   "Enterprise"),
    ("HCL Technologies",        "IT Services",        "Noida",       "Enterprise"),
    ("Sun Pharma",              "Pharma",             "Mumbai",      "Enterprise"),
    ("Larsen & Toubro",         "Infrastructure",     "Mumbai",      "Enterprise"),
]

# ── Opportunity templates ─────────────────────────────────────────────────────
# (title_template, rfp_type, min_cr, max_cr, base_win_prob)
OPP_TEMPLATES = [
    ("SOC Transformation",          "SOC Transformation",   1.5, 4.5, 70),
    ("Zero Trust Architecture",     "Zero Trust",           1.2, 3.5, 72),
    ("SIEM Migration & Tuning",     "SIEM Migration",       0.8, 2.2, 65),
    ("AI Governance Framework",     "AI Governance",        2.0, 5.0, 55),
    ("Cloud Security Posture",      "Cloud Modernization",  0.7, 2.0, 68),
    ("Compliance Automation Suite", "Compliance Automation",1.0, 2.8, 74),
    ("Pen Testing Program",         "Pen Testing",          0.3, 1.2, 80),
    ("Incident Response Retainer",  "DFIR",                 0.5, 1.8, 75),
    ("Red Team Assessment",         "Pen Testing",          0.4, 1.5, 70),
    ("ISO 27001 Implementation",    "Compliance Automation",0.6, 1.8, 72),
    ("PCI DSS Compliance",          "Compliance Automation",0.8, 2.5, 68),
    ("OT/SCADA Security",           "SOC Transformation",   1.2, 3.2, 60),
    ("Data Loss Prevention",        "Cloud Modernization",  0.6, 1.9, 66),
    ("Identity & Access Mgmt",      "Zero Trust",           0.9, 2.8, 71),
    ("Threat Intelligence Platform","SOC Transformation",   1.0, 2.6, 67),
    ("DevSecOps Enablement",        "Cloud Modernization",  0.5, 1.6, 73),
    ("API Security Audit",          "Pen Testing",          0.2, 0.8, 82),
    ("SOC 2 Type II Readiness",     "Compliance Automation",0.7, 2.0, 76),
    ("Cloud WAF Implementation",    "Cloud Modernization",  0.4, 1.4, 74),
    ("Security Awareness Training", "Compliance Automation",0.2, 0.7, 85),
]

def _rand_stage() -> tuple[str, int]:
    """Return (stage, health_score)."""
    weights = [3, 4, 4, 6, 5, 5, 4, 3, 3, 4, 2]   # more mid-funnel opps
    stage = rng.choices(STAGES_ORDER, weights=weights, k=1)[0]
    base  = {"intake": 45, "qualification": 55, "sme_assignment": 60, "drafting": 68,
             "technical_review": 72, "security_review": 78, "delivery_review": 80,
             "finance_review": 82, "legal_review": 85, "approval": 90, "submission": 95}
    health = min(99, base[stage] + rng.randint(-10, 10))
    return stage, health


def _days_ago(n: float) -> datetime:
    return NOW - timedelta(days=n)


def _activity(proposal_id: str, actor: str, action_type: str, desc: str, is_alert: bool, when: datetime) -> ActivityFeed:
    return ActivityFeed(
        proposal_id=proposal_id,
        actor_name=actor,
        action_type=action_type,
        description=desc,
        is_alert=is_alert,
        created_at=when,
    )


# ── Routing rules ─────────────────────────────────────────────────────────────
ROUTING_RULES = [
    ("SOC Transformation",   "SOC",             "Cybersecurity",  1),
    ("SOC Transformation",   "SIEM",            "Cybersecurity",  2),
    ("SOC Transformation",   "Threat Detection","Cybersecurity",  3),
    ("Zero Trust",           "Zero Trust",      "Cybersecurity",  1),
    ("Zero Trust",           "IAM",             "Cybersecurity",  2),
    ("Zero Trust",           "Network Security","Infrastructure", 3),
    ("AI Governance",        "AI Security",     "AI",             1),
    ("AI Governance",        "Compliance",      "Compliance",     2),
    ("SIEM Migration",       "SIEM",            "Cybersecurity",  1),
    ("SIEM Migration",       "SOC",             "Cybersecurity",  2),
    ("Cloud Modernization",  "Cloud Security",  "Cloud",          1),
    ("Cloud Modernization",  "DevSecOps",       "Cloud",          2),
    ("Compliance Automation","Compliance",      "Compliance",     1),
    ("Compliance Automation","Risk",            "Compliance",     2),
    ("Pen Testing",          "Pen Testing",     "Cybersecurity",  1),
    ("DFIR",                 "DFIR",            "Cybersecurity",  1),
]


def seed(db):
    init_db()

    print("\n[seed] Starting enterprise seed...\n")

    # ── Tenants ───────────────────────────────────────────────────────────────
    print("[seed] Creating tenants...")
    tenants = []
    for td in TENANTS:
        t = Tenant(**td)
        db.add(t)
        tenants.append(t)
    db.flush()
    sisa_tenant = tenants[0]

    # ── Demo users ────────────────────────────────────────────────────────────
    print("[seed] Creating user accounts...")
    tenant_ids = [t.id for t in tenants]
    for email, password, full_name, roles, tenant_idx in DEMO_USERS:
        existing = db.query(User).filter(User.email == email).first()
        if not existing:
            db.add(User(
                email=email,
                hashed_password=hash_password(password),
                full_name=full_name,
                tenant_id=tenant_ids[tenant_idx],
                roles=roles,
                is_active=True,
                is_verified=True,
            ))
    db.flush()

    # ── SLA configs ───────────────────────────────────────────────────────────
    print("[seed] Writing SLA configs...")
    for stage, hours, role in SLA_DEFAULTS:
        db.merge(SlaConfig(stage=stage, hours_allowed=hours, escalate_to_role=role))

    # ── Routing rules ─────────────────────────────────────────────────────────
    print("[seed] Writing SME routing rules...")
    for rfp, skill, bu, priority in ROUTING_RULES:
        db.add(SmeRoutingRule(rfp_type=rfp, required_expertise=skill, bu=bu, priority=priority))

    # ── Stakeholders ──────────────────────────────────────────────────────────
    print("[seed] Creating stakeholders...")
    stakeholders = []
    for sd in STAKEHOLDERS:
        s = Stakeholder(**sd)
        db.add(s)
        stakeholders.append(s)
    db.flush()

    def _by_role(role: str) -> Stakeholder:
        return next(s for s in stakeholders if s.role == role)

    presales_lead = _by_role("presales_lead")
    sol_arch      = _by_role("solution_architect")
    sec_reviewer  = _by_role("security_reviewer")
    finance_rev   = _by_role("finance")
    legal_rev     = _by_role("legal")

    # SME pool
    smes = [s for s in stakeholders if s.role == "sme"]
    def _pick_sme(expertise_hint: str) -> Stakeholder:
        matches = [s for s in smes if any(expertise_hint.lower() in e.lower() for e in s.expertise)]
        return rng.choice(matches) if matches else rng.choice(smes)

    # ── Clients ───────────────────────────────────────────────────────────────
    print("[seed] Creating clients...")
    clients = []
    for name, sector, region, tier in CLIENTS:
        c = Client(name=name, sector=sector, region=region, tier=tier)
        db.add(c)
        clients.append(c)
    db.flush()

    # ── Opportunities (100+ total across SISA's book) ────────────────────────
    print("[seed] Generating 110 opportunities + proposals...")
    opportunities = []
    proposals     = []

    # First 6 are the fixed "live" opps from original seed (exact same scenario)
    LIVE_OPPS = [
        # (title, client_idx, rfp_type, value, win_prob, stage, health, hours_in_stage, deadline_days)
        ("SOC Transformation",      0, "SOC Transformation",   2.4, 75, "security_review",  87, 20, 45),
        ("Zero Trust Rollout",      1, "Zero Trust",           1.8, 85, "approval",          92,  5, 30),
        ("SIEM Migration",          2, "SIEM Migration",       1.1, 60, "drafting",          71, 60, 60),
        ("AI Governance Platform",  3, "AI Governance",        3.2, 50, "sme_assignment",    55,  3, 90),
        ("Cloud Modernization",     4, "Cloud Modernization",  0.9, 65, "qualification",     68, 20, 75),
        ("Compliance Automation",   5, "Compliance Automation",1.4, 70, "technical_review",  79, 20, 50),
    ]

    for title, client_idx, rfp_type, value, win_prob, stage, health, hours_in_stage, deadline_days in LIVE_OPPS:
        created = NOW - timedelta(days=14)
        updated = NOW - timedelta(hours=hours_in_stage)
        opp = Opportunity(
            client_id=clients[client_idx].id, title=title, rfp_type=rfp_type,
            deal_value_cr=value, win_probability=win_prob, stage=stage,
            owner_id=presales_lead.id,
            deadline=(NOW + timedelta(days=deadline_days)).date(),
            created_at=created, updated_at=updated,
        )
        db.add(opp)
        opportunities.append(opp)
    db.flush()

    for i, opp in enumerate(opportunities[:6]):
        _, _, _, _, _, stage, health, hours_in_stage, _ = LIVE_OPPS[i]
        created = NOW - timedelta(days=14)
        updated = NOW - timedelta(hours=hours_in_stage)
        p = Proposal(
            opportunity_id=opp.id, stage=stage, health_score=health,
            content={"exec_summary": f"Executive summary for {opp.title}", "scope": "TBD", "pricing": {"total_cr": float(opp.deal_value_cr or 0)}},
            created_at=created, updated_at=updated,
        )
        db.add(p)
        proposals.append(p)
    db.flush()

    # ── Historical pipeline (past 6 months) ──────────────────────────────────
    # Mix: closed-won, closed-lost, in-flight at various stages
    HISTORICAL_OUTCOMES = ["submission", "submission", "submission", "qualification", "sme_assignment", "drafting"]

    for idx in range(104):  # total = 6 live + 104 historical = 110
        tmpl_idx  = idx % len(OPP_TEMPLATES)
        client    = clients[idx % len(clients)]
        template  = OPP_TEMPLATES[tmpl_idx]
        title_pfx, rfp_type, min_cr, max_cr, base_wp = template

        # Spread creation over 6 months
        days_back_created = rng.uniform(5, 180)
        created = _days_ago(days_back_created)

        # Most historical opps are closed or late-stage
        if days_back_created > 90:
            # Older opps: mostly closed
            stage = rng.choice(["submission", "submission", "legal_review", "approval"])
        elif days_back_created > 30:
            stage = rng.choice(["technical_review", "security_review", "approval", "finance_review"])
        else:
            stage, _ = _rand_stage()

        health = rng.randint(55, 95)
        value  = round(rng.uniform(min_cr, max_cr), 1)
        wp     = base_wp + rng.randint(-10, 15)
        updated = created + timedelta(days=rng.uniform(1, min(days_back_created, 20)))

        opp = Opportunity(
            client_id=client.id,
            title=f"{title_pfx} — {client.name}",
            rfp_type=rfp_type,
            deal_value_cr=value,
            win_probability=min(95, wp),
            stage=stage,
            owner_id=presales_lead.id,
            deadline=(NOW + timedelta(days=rng.randint(15, 120))).date(),
            created_at=created,
            updated_at=updated,
        )
        db.add(opp)
        opportunities.append(opp)

    db.flush()

    for opp in opportunities[6:]:
        stage_idx = STAGES_ORDER.index(opp.stage) if opp.stage in STAGES_ORDER else 3
        health = rng.randint(55, 95)
        p = Proposal(
            opportunity_id=opp.id, stage=opp.stage, health_score=health,
            content={"exec_summary": f"Executive summary for {opp.title}", "pricing": {"total_cr": float(opp.deal_value_cr or 0)}},
            created_at=opp.created_at,
            updated_at=opp.updated_at,
        )
        db.add(p)
        proposals.append(p)
    db.flush()

    # ── Approvals for live opps ───────────────────────────────────────────────
    soc_proposal        = proposals[0]
    infosys_proposal    = proposals[1]
    compliance_proposal = proposals[5]

    for review_stage, reviewer in [("technical_review", sol_arch), ("security_review", sec_reviewer), ("delivery_review", sol_arch)]:
        sla_hrs = next((h for s, h, _ in SLA_DEFAULTS if s == review_stage), 24)
        db.add(Approval(proposal_id=soc_proposal.id, approver_id=reviewer.id, stage=review_stage,
                        parallel_group="review_round_1", order_index=0, status="pending",
                        due_at=NOW - timedelta(hours=20) + timedelta(hours=sla_hrs)))

    for review_stage, reviewer in [("technical_review", sol_arch), ("security_review", sec_reviewer), ("delivery_review", sol_arch)]:
        sla_hrs = next((h for s, h, _ in SLA_DEFAULTS if s == review_stage), 24)
        db.add(Approval(proposal_id=compliance_proposal.id, approver_id=reviewer.id, stage=review_stage,
                        parallel_group="review_round_1", order_index=0, status="pending",
                        due_at=NOW - timedelta(hours=20) + timedelta(hours=sla_hrs)))

    for order, (approver, stg, approved_hours_ago) in enumerate([
        (sol_arch,    "technical_review", 10),
        (sol_arch,    "delivery_review",  10),
        (sec_reviewer,"security_review",   9),
        (finance_rev, "finance_review",    8),
        (legal_rev,   "legal_review",      7),
    ]):
        db.add(Approval(proposal_id=infosys_proposal.id, approver_id=approver.id, stage=stg,
                        parallel_group="review_round_1" if stg in ("technical_review","security_review","delivery_review") else None,
                        order_index=order, status="approved",
                        decided_at=NOW - timedelta(hours=approved_hours_ago),
                        due_at=NOW - timedelta(hours=approved_hours_ago - 2)))
    db.add(Approval(proposal_id=infosys_proposal.id, approver_id=presales_lead.id,
                    stage="approval", order_index=5, status="pending",
                    due_at=NOW - timedelta(hours=1)))

    # ── SME Assignments ───────────────────────────────────────────────────────
    sme_map = {i: smes[i % len(smes)] for i in range(6)}
    for i, proposal in enumerate(proposals[:6]):
        sme = sme_map.get(i)
        if sme:
            db.add(Assignment(proposal_id=proposal.id, stakeholder_id=sme.id, role="sme", bu=sme.bu,
                              status="in_progress" if i in (0,1,2,5) else "pending",
                              assigned_at=NOW - timedelta(days=13)))

    for proposal in proposals[6:]:
        sme = _pick_sme(proposal.stage)
        if rng.random() > 0.3:
            db.add(Assignment(proposal_id=proposal.id, stakeholder_id=sme.id, role="sme", bu=sme.bu,
                              status=rng.choice(["in_progress","in_progress","completed","pending"]),
                              assigned_at=proposal.created_at + timedelta(days=1)))
    db.flush()

    # ── Activity feed — live opps ─────────────────────────────────────────────
    activity_seed = {
        0: [("Rajiv Nair",  "stage_transition",  "Entered parallel review phase",             False, 20),
            ("Arjun Kumar", "sme_assigned",       "SME assigned: SOC → Rajiv Nair",           False, 21),
            ("Sneha Sharma","stage_transition",   "Draft submitted for technical review",      False, 48),
            ("SLA Monitor", "sla_breach",         "⚠ Warning: Security Review approaching SLA",True,  1)],
        1: [("SLA Monitor", "sla_breach",         "🚨 SLA BREACHED: Approval overdue by 1h",  True,   1),
            ("Arjun Kumar", "stage_transition",   "All reviews passed → moved to Approval",   False,  5),
            ("Karan Joshi", "approval_decision",  "Karan Joshi approved Legal Review",        False,  7),
            ("Deepa Rao",   "approval_decision",  "Deepa Rao approved Finance Review",        False,  8),
            ("Vikram Mehta","approval_decision",  "Vikram Mehta approved Security Review",    False,  9)],
        2: [("Rajiv Nair",  "stage_transition",   "Drafting in progress — 60h elapsed",       False, 60),
            ("Arjun Kumar", "sme_assigned",       "SME assigned: SIEM Migration → Rajiv",     False, 62)],
        3: [("System",      "sme_assigned",       "Auto-routing SME for AI Governance",       False,  3),
            ("Arjun Kumar", "stage_transition",   "Moved to SME Assignment",                  False,  4)],
        4: [("Sneha Sharma","stage_transition",   "Qualification call completed",              False, 20)],
        5: [("Priya Singh", "stage_transition",   "Entered parallel technical review",         False, 20),
            ("Arjun Kumar", "sme_assigned",       "SME assigned: Compliance → Priya Singh",   False, 22)],
    }
    for opp_idx, activities in activity_seed.items():
        proposal = proposals[opp_idx]
        for actor, action_type, description, is_alert, hours_ago in activities:
            db.add(ActivityFeed(proposal_id=proposal.id, actor_name=actor, action_type=action_type,
                                description=description, is_alert=is_alert, created_at=NOW - timedelta(hours=hours_ago)))

    # ── Activity feed — historical opps (realistic per-stage events) ──────────
    action_pool = [
        ("stage_transition",  "Stage advanced: {stage} completed",  False),
        ("sme_assigned",      "SME {name} assigned to review",       False),
        ("approval_decision", "{name} approved the {stage} stage",   False),
        ("stage_transition",  "Proposal entered {stage} review",     False),
        ("sla_breach",        "⚠ SLA warning: {stage} approaching deadline", True),
    ]
    actor_pool = ["Arjun Kumar","Sneha Sharma","Rajiv Nair","Priya Singh","Vikram Mehta","System"]

    for proposal in proposals[6:]:
        n_events = rng.randint(2, 8)
        base_time = proposal.created_at
        for j in range(n_events):
            action_tmpl = rng.choice(action_pool)
            action_type, desc_tmpl, is_alert = action_tmpl
            actor = rng.choice(actor_pool)
            stage = rng.choice(STAGES_ORDER)
            desc  = desc_tmpl.format(stage=stage, name=actor)
            event_time = base_time + timedelta(hours=rng.uniform(1, 72) * (j + 1))
            if event_time > NOW:
                break
            db.add(ActivityFeed(proposal_id=proposal.id, actor_name=actor, action_type=action_type,
                                description=desc, is_alert=is_alert, created_at=event_time))

    # ── Audit log ─────────────────────────────────────────────────────────────
    for opp in opportunities:
        db.add(AuditLog(entity_type="opportunity", entity_id=opp.id, actor_id=presales_lead.id,
                        action="created", to_state="intake", occurred_at=opp.created_at))
        if opp.stage != "intake":
            stage_idx = STAGES_ORDER.index(opp.stage) if opp.stage in STAGES_ORDER else 1
            for si in range(1, min(stage_idx + 1, len(STAGES_ORDER))):
                db.add(AuditLog(entity_type="proposal", entity_id=opp.id, actor_id=presales_lead.id,
                                action="stage_transition", from_state=STAGES_ORDER[si-1],
                                to_state=STAGES_ORDER[si],
                                occurred_at=opp.created_at + timedelta(days=si * rng.uniform(0.5, 3))))

    db.commit()

    won  = sum(1 for o in opportunities if o.stage == "submission")
    live = sum(1 for o in opportunities if o.stage not in ("submission",))
    print(f"\n[seed] ✅  Done!\n")
    print(f"  Tenants:       {len(tenants)}")
    print(f"  Users:         {len(DEMO_USERS)}")
    print(f"  Stakeholders:  {len(stakeholders)}")
    print(f"  Clients:       {len(clients)}")
    print(f"  Opportunities: {len(opportunities)} total ({live} live, {won} submitted)")
    print(f"  Proposals:     {len(proposals)}")
    print(f"\n  Demo logins:")
    for email, pwd, name, roles, _ in DEMO_USERS:
        print(f"    {email:35s}  /  {pwd}   ({roles[0]})")
    print()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Presales Hub — enterprise seed")
    parser.add_argument("--reset", action="store_true", help="Drop + recreate all tables before seeding")
    args = parser.parse_args()

    if args.reset:
        from db.database import Base, engine
        print("[seed] Dropping all tables...")
        Base.metadata.drop_all(bind=engine)
        print("[seed] Tables dropped.")

    init_db()
    db = SessionLocal()
    try:
        # Check if already seeded
        existing = db.scalar(select(Tenant))
        if existing and not args.reset:
            print("[seed] Data already exists — use --reset to wipe and reseed.")
            # Still ensure demo users exist
            for email, password, full_name, roles, tenant_idx in DEMO_USERS:
                existing_user = db.query(User).filter(User.email == email).first()
                if not existing_user:
                    tenant = db.query(Tenant).first()
                    if tenant:
                        db.add(User(email=email, hashed_password=hash_password(password),
                                   full_name=full_name, tenant_id=tenant.id,
                                   roles=roles, is_active=True, is_verified=True))
            db.commit()
            print("[seed] Demo user accounts verified.")
            return
        seed(db)
    except Exception as e:
        db.rollback()
        print(f"[seed] ERROR: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
