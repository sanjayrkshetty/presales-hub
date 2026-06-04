#!/usr/bin/env python
"""
Generate the Presales Hub Security Review report (.docx) with python-docx.
Self-conducted security review write-up. No client identifiers, no third-party
company names — proposals referred to generically (Proposal A/B).
Author: Sanjay R K Shetty.
Run:  python gen_audit_docx.py
Out:  docs/Presales-Hub-Security-Review.docx
"""
import os
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")
OUT_PATH = os.path.join(OUT_DIR, "Presales-Hub-Security-Review.docx")

NAVY = RGBColor(0x1F, 0x33, 0x55)
GREY = RGBColor(0x55, 0x55, 0x55)
RED = RGBColor(0xB0, 0x2A, 0x2A)
AMBER = RGBColor(0xB7, 0x6E, 0x00)
GREEN = RGBColor(0x1E, 0x7A, 0x3C)

SEV_COLOR = {"Critical": RED, "High": RED, "Medium": AMBER, "Low": GREY, "Info": GREY}

# ---------------------------------------------------------------- content data
VERSION_ROWS = [
    ("Version", "Date", "Author", "Description"),
    ("v1.0", "2026-06-04", "Sanjay R K Shetty", "Initial security review report"),
]

SUMMARY_ROWS = [
    ("ID", "Finding", "Severity", "Status"),
    ("F-01", "Unauthenticated API surface (no auth dependency on routers)", "Critical", "Fixed"),
    ("F-02", "Broken browser auth flow (refresh cookie / WS / reload bounce)", "High", "Fixed"),
    ("F-03", "Authorization not enforced — RBAC dead code (privilege escalation)", "High", "Open"),
    ("F-04", "Sidebar navigation not role-gated", "Medium", "Open"),
    ("F-05", "Approval decisions never signal the review workflow", "High", "Open"),
    ("F-06", "No server-side stage-transition validation", "High", "Open"),
    ("F-07", "Workflow panel does not refresh after a transition", "Medium", "Open"),
    ("F-08", "Parallel-review UX / state not surfaced", "Medium", "Open"),
    ("F-09", "Cancel freezes stage instead of terminal state", "Low", "Open"),
    ("F-10", "AI copilot fully non-functional (pgvector → session cascade)", "High", "Open"),
    ("F-11", "Agent task list endpoint method mismatch (405)", "Medium", "Open"),
    ("F-12", "Proposal detail id mismatch (every detail 404)", "Medium", "Fixed"),
    ("F-13", "Forecast crash from field-name mismatch", "High", "Fixed"),
    ("F-14", "Intelligence widget renders object as React child (crash)", "Medium", "Open"),
    ("F-15", "Approval queue unfiltered (sourced from opportunities)", "Medium", "Open"),
    ("F-16", "No decision actions on the Approvals page", "Low", "Open"),
    ("F-17", "No opportunity/proposal creation UI (endpoint orphaned)", "Medium", "Open"),
    ("F-18", "Large orphaned, unauthorized mutating API surface", "Medium", "Open"),
    ("F-19", "Pervasive date/SLA formatting defects", "Low", "Open"),
    ("F-20", "Percentages double-scaled (e.g. 8200%, 5000%)", "Low", "Open"),
    ("F-21", "Auto-assign blocked by seed capacity", "Low", "Open"),
    ("F-22", "Login ignores post-auth redirect (?next)", "Low", "Open"),
    ("F-23", "Swagger /docs blank (CDN assets blocked)", "Medium", "Open"),
    ("F-24", "Dead route /dashboard (404)", "Medium", "Open"),
    ("F-25", "Request-level traces missing (FastAPI not instrumented)", "Medium", "Open"),
]

GROUPS = [
    ("A. Authentication & Authorization", [
        ("F-01", "Unauthenticated API surface", "Critical", "Fixed",
         "Every /api/** router was mounted without an authentication dependency, leaving the entire "
         "API reachable without a token. Root cause: authentication was assumed to be global, yet no "
         "auth dependency was applied at the router level. Remediation (applied): the auth dependency "
         "is attached to every included router centrally (health/readiness/metrics left public); "
         "verified no-token requests now return 401 and valid-token requests 200."),
        ("F-02", "Broken browser authentication flow", "High", "Fixed",
         "The refresh-token cookie was issued with SameSite=Lax and Secure restricted to production, "
         "so the browser rejected it over the cross-origin local flow; token refresh then failed, "
         "WebSockets never authenticated, and any full-page reload of a protected route bounced to "
         "the login screen. Root cause: cookie attributes incompatible with the single-page app's "
         "cross-origin bootstrap. Remediation (applied): corrected cookie flags and gated protected "
         "routes on bootstrap; verified refresh succeeds (200), WebSockets upgrade (101), and a hard "
         "refresh preserves the page."),
        ("F-03", "Authorization not enforced (RBAC dead code)", "High", "Open",
         "Authorization is not enforced anywhere: a correct require_permission() dependency exists but "
         "is applied to zero routes, so any authenticated user holds every permission regardless of "
         "role. Proof of concept: a presales-lead account that lacks webhook write/delete permissions "
         "successfully created and deleted a webhook (POST 201, DELETE 200). Recommendation: wire the "
         "existing require_permission factory to each route via a permission map and treat the "
         "permission model as authoritative."),
        ("F-04", "Sidebar navigation not role-gated", "Medium", "Open",
         "The navigation sidebar is identical for every role — an administrator and a presales lead "
         "see the same sixteen entries — because the available role-check helper is never used in the "
         "sidebar component. On its own this is cosmetic, but combined with F-03 the exposed "
         "administrative links actually function. Recommendation: gate navigation by role on the "
         "client and enforce on the server (F-03)."),
    ]),
    ("B. Workflow Integrity", [
        ("F-05", "Approvals never signal the review workflow", "High", "Open",
         "Approving an item in the war-room approval chain calls the approval-decide endpoint, which "
         "only updates the database row and emits an event with no consumers; it never signals the "
         "durable parallel-review workflow that actually gates the review. As a result a proposal that "
         "enters parallel review can never progress past it through the interface, and every "
         "downstream stage is unreachable. Recommendation: have the decide path also signal the "
         "review-submit operation for review-stage approvals."),
        ("F-06", "No server-side transition validation", "High", "Open",
         "The workflow applies any requested stage transition without validating it against the "
         "permitted transition graph; an illegal jump from the first stage straight to the approval "
         "stage — skipping six stages including all reviews — was accepted and persisted. Root cause: "
         "the state machine is enforced only by the frontend's button list, never on the server. "
         "Recommendation: validate the requested stage against the allowed-transition map in the "
         "persistence step and reject illegal moves."),
        ("F-07", "Panel does not refresh after a transition", "Medium", "Open",
         "After advancing a stage, the war-room panel does not reflect the new stage until a manual "
         "reload, because the status query fires before the asynchronous workflow signal is processed "
         "and is never re-fetched. Recommendation: invalidate and re-fetch the workflow-status query "
         "after a transition, or poll briefly until it settles."),
        ("F-08", "Parallel-review UX and state not surfaced", "Medium", "Open",
         "The drafting stage presents three separate advance buttons (technical, security, delivery "
         "review) but the workflow treats any of them identically as 'run all three reviews', and "
         "during review the parent stage remains 'drafting' so the progress rail and stage assistant "
         "never reflect the review phase. Recommendation: collapse to a single 'submit for review' "
         "action and surface the parallel-review sub-state explicitly."),
        ("F-09", "Cancel freezes stage instead of a terminal state", "Low", "Open",
         "Cancelling a workflow correctly marks it inactive but leaves the stage frozen at its last "
         "value rather than moving to a lost/closed terminal stage as the cancel contract implies, so "
         "a cancelled proposal still reads as mid-pipeline. Recommendation: persist a terminal stage "
         "on cancel."),
    ]),
    ("C. AI Subsystem", [
        ("F-10", "AI copilot fully non-functional", "High", "Open",
         "The entire AI copilot surface is dead. A vector-similarity query binds its parameter in a "
         "form the database rejects as a syntax error; the fallback path catches the exception but "
         "never rolls back the session, so the next query fails with 'current transaction is aborted', "
         "and the resulting server error reaches the browser without cross-origin headers — appearing "
         "as a misleading CORS / network failure that masks the real fault. Confirmed across the "
         "RFP-analysis and draft-generation assistants. Recommendation: fix the parameter binding, add "
         "an explicit session rollback in the fallback, and attach CORS headers to error responses."),
        ("F-11", "Agent task list endpoint mismatch", "Medium", "Open",
         "The Agent Monitor can never list tasks: the frontend issues a GET to the agent-tasks "
         "collection, but the backend defines only a create (POST) and a fetch-by-id (GET), with no "
         "GET-list, so the request returns 405 and the interface silently shows zero. Recommendation: "
         "add a list endpoint, or point the client at the correct path."),
    ]),
    ("D. Frontend / Backend Contract Drift", [
        ("F-12", "Proposal detail id mismatch", "Medium", "Fixed",
         "Every proposal-detail link returned 'not found' because list views linked by the proposal "
         "identifier while the detail page fetched by the opportunity identifier. Remediation "
         "(applied): a backend fallback resolves either identifier; verified the detail and health "
         "panels now load."),
        ("F-13", "Forecast crash from field-name mismatch", "High", "Fixed",
         "The intelligence forecast crashed because the frontend read forecast fields whose names "
         "differed from the API response keys, and the shared type declared the wrong names so the "
         "compiler never caught it. Remediation (applied): aligned the field names; the crash is gone "
         "(a flat-axis chart-scaling issue remains, cosmetic)."),
        ("F-14", "Widget renders an object as a React child", "Medium", "Open",
         "The intelligence 'dependencies' widget crashes (objects are not valid as a React child) "
         "because it renders a stakeholder-dependency object directly instead of its fields; the API "
         "returns 200, so this is purely a render defect that trips an error boundary. Recommendation: "
         "render the object's individual fields."),
        ("F-15", "Approval queue unfiltered", "Medium", "Open",
         "The approval queue's 'pending' tab lists all proposals — including closed/won and closed/lost "
         "— because it is sourced from the opportunities collection rather than a pending-approvals "
         "query, and the 'pending' filter is a no-op. Recommendation: source the queue from actual "
         "pending approvals."),
        ("F-16", "No decision actions on the Approvals page", "Low", "Open",
         "The Approvals page exposes no decision control (approve, reject, escalate) — only a link to "
         "the war room; combined with F-05 there is no working path to action an approval anywhere in "
         "the product. Recommendation: add inline decision controls wired to a working signal."),
        ("F-17", "No creation UI for opportunities/proposals", "Medium", "Open",
         "There is no interface to create an opportunity or proposal: the create endpoint exists (and "
         "creates the client, opportunity and proposal records together) but no page or component "
         "calls it, so records can only be seeded or created by direct API. Recommendation: add a "
         "creation form bound to the existing endpoint."),
        ("F-18", "Large orphaned, unauthorized mutating surface", "Medium", "Open",
         "A substantial fraction of the API is reachable but unreachable from the interface "
         "('orphaned'): state-changing operations such as review-submit and SLA-resolve, agent task "
         "create/approve/reject, tenant administration, integration webhook/sync/ingest, memory "
         "indexing/reindexing, and AI proposal generation have no working UI path. Combined with F-03 "
         "(no authorization), these orphaned mutating endpoints form an unmonitored, unauthorized "
         "attack surface. Recommendation: wire, gate, or remove unused endpoints."),
    ]),
    ("E. Data Quality & Cosmetic", [
        ("F-19", "Pervasive date / SLA formatting defects", "Low", "Open",
         "Time and SLA values render incorrectly throughout — transition history reads 'NaN days ago', "
         "approval due-dates show negative seconds, and almost every proposal shows 'Overdue' — driven "
         "by date-parsing/formatting bugs and past-dated seed deadlines. Recommendation: centralise "
         "date formatting and refresh seed deadlines."),
        ("F-20", "Percentages double-scaled", "Low", "Open",
         "Percentages are scaled twice: win probability renders as '8200%' and analytics win-rate as "
         "'5000.0%' because a value already expressed in percent is multiplied by one hundred again. "
         "Recommendation: a single percentage-formatting helper."),
        ("F-21", "Auto-assign blocked by seed capacity", "Low", "Open",
         "Auto-assigning a subject-matter expert always fails with a clear '422 — all experts at "
         "maximum workload' because every eligible expert in the seed data is at capacity (the "
         "spare-capacity people shown elsewhere hold non-eligible roles). The logic is correct; the "
         "seed needs spare capacity to demonstrate a successful assignment."),
        ("F-22", "Login ignores post-auth redirect", "Low", "Open",
         "After login the requested return path is ignored and the user lands on the default page "
         "instead of the route they originally requested. Recommendation: honor the post-auth redirect "
         "parameter."),
    ]),
    ("F. Observability & Infrastructure", [
        ("F-23", "Swagger documentation blank", "Medium", "Open",
         "The interactive API documentation renders blank because its asset bundle is loaded from a "
         "CDN that is blocked in the environment. Recommendation: self-host the documentation assets."),
        ("F-24", "Dead route", "Medium", "Open",
         "A primary route returns 404 (dead link). Recommendation: remove the link or implement the "
         "route."),
        ("F-25", "Request-level traces missing", "Medium", "Open",
         "Distributed traces contain only database spans because the web framework is not instrumented, "
         "so request-level spans never reach the trace collector. Recommendation: enable framework "
         "instrumentation."),
    ]),
]

CLAIMS = [
    ('"Unauthenticated endpoint access … JWT Bearer required on all /api/** routes — Implemented"',
     "Reality: at the time of review no router carried an authentication dependency (F-01), and "
     "role-based authorization is applied to zero routes (F-03)."),
    ('Architecture diagram: an "Authorization — Role-based access control" component (presales_lead · sme · admin)',
     "Reality: the authorization enforcer is imported by no route; the box exists on the diagram, not "
     "in the request path (F-03)."),
    ('"Privilege escalation … enforces tenant isolation — Implemented"',
     "Reality: privilege escalation across roles was demonstrated — a low-privilege account performed "
     "an administrative write (F-03)."),
    ('"Refresh token … httpOnly cookie, SameSite=Lax, Secure=prod-only — Implemented"',
     "Reality: that exact cookie configuration broke the browser authentication flow end-to-end "
     "(F-02)."),
]

ZONES = [
    "1 — Core API & infrastructure", "2 — Authentication & authorization",
    "3 — Durable workflow execution", "4 — Frontend routes", "5 — Observability",
    "6 — Proposals module", "H — Human-in-the-loop workflow (end-to-end lifecycle)",
    "7 — Approvals", "8 — Analytics", "9 — AI (copilot / agents / governance)",
    "10 — Administration & RBAC", "11 — Stakeholders",
]

# ---------------------------------------------------------------- helpers
def shade(cell, hexcolor):
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    tcPr = cell._tc.get_or_add_tcPr()
    sh = OxmlElement("w:shd")
    sh.set(qn("w:val"), "clear")
    sh.set(qn("w:fill"), hexcolor)
    tcPr.append(sh)

def heading(doc, text, level):
    h = doc.add_heading(text, level=level)
    for run in h.runs:
        run.font.color.rgb = NAVY
    return h

def body(doc, text, size=10.5, space_after=8):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    r = p.add_run(text)
    r.font.size = Pt(size)
    return p

# ---------------------------------------------------------------- build
def build():
    doc = Document()
    base = doc.styles["Normal"]
    base.font.name = "Calibri"
    base.font.size = Pt(10.5)

    # Cover
    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for _ in range(4):
        doc.add_paragraph()
    r = t.add_run("SECURITY REVIEW")
    r.bold = True; r.font.size = Pt(30); r.font.color.rgb = NAVY
    sub = doc.add_paragraph(); sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    rs = sub.add_run("Presales Hub — AI-assisted proposal lifecycle platform")
    rs.font.size = Pt(14); rs.font.color.rgb = GREY
    cls = doc.add_paragraph(); cls.alignment = WD_ALIGN_PARAGRAPH.CENTER
    rc = cls.add_run("Confidential · Self-conducted security assessment")
    rc.italic = True; rc.font.size = Pt(11); rc.font.color.rgb = GREY
    for _ in range(8):
        doc.add_paragraph()
    auth = doc.add_paragraph(); auth.alignment = WD_ALIGN_PARAGRAPH.CENTER
    ra = auth.add_run("Author: Sanjay R K Shetty    |    Version v1.0    |    04 June 2026")
    ra.font.size = Pt(10.5)
    doc.add_page_break()

    # Document control
    heading(doc, "Document Control", 1)
    tbl = doc.add_table(rows=0, cols=4); tbl.style = "Light Grid Accent 1"
    for i, row in enumerate(VERSION_ROWS):
        cells = tbl.add_row().cells
        for j, val in enumerate(row):
            cells[j].text = val
            if i == 0:
                for run in cells[j].paragraphs[0].runs:
                    run.bold = True
                shade(cells[j], "1F3355")
                for run in cells[j].paragraphs[0].runs:
                    run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    doc.add_paragraph()

    # Executive summary
    heading(doc, "1. Executive Summary", 1)
    body(doc, "Presales Hub is an internally built, AI-assisted platform that carries a sales "
              "proposal through its full lifecycle, with a durable workflow engine and an AI copilot. "
              "This report documents a self-conducted security and quality review of the platform, "
              "performed as a structured red-team-style exercise against the reviewer's own code.")
    body(doc, "Verdict: the platform is a sound, durable workflow engine wrapped in a weak "
              "integration and enforcement layer. The core lifecycle is correct and resilient, but the "
              "surfaces around it repeatedly fail to enforce their own rules.")
    body(doc, "A single root cause explains the majority of findings: the system trusts the client "
              "and rarely enforces its invariants on the server, while the backend often does not serve "
              "or validate exactly what the user interface assumes. This manifests as missing "
              "authorization, an unenforced state machine, and pervasive contract drift between "
              "frontend and backend.")
    body(doc, "Twenty-five distinct findings were recorded: one Critical and several High-severity "
              "issues (authorization not enforced, the approval workflow gate disconnected, the AI "
              "subsystem inoperative, and stage transitions unvalidated), alongside a long tail of "
              "Medium and Low issues. Several Critical/High issues identified earlier in the review "
              "have already been remediated and re-verified.")

    # Scope & methodology
    heading(doc, "2. Scope & Methodology", 1)
    body(doc, "Scope: the full application — its HTTP API, durable workflow engine, authentication and "
              "authorization, AI copilot and agent subsystems, analytics, and administrative surfaces. "
              "The assessment used demonstration/seed data only; no real customer data was involved.")
    body(doc, "Method: a structured twelve-area smoke test combining three techniques — (1) "
              "agent-driven browser testing, in which the reviewer drove an instrumented browser to "
              "exercise each surface end-to-end and capture network traffic, console output and "
              "screenshots; (2) source-code review to establish root cause; and (3) authenticated API "
              "testing to confirm behaviour and demonstrate exploitability. Findings are evidence-backed "
              "and reproducible.")
    body(doc, "Out of scope: infrastructure penetration testing, dependency/CVE scanning, and load "
              "testing.")

    # Findings summary
    heading(doc, "3. Findings Summary", 1)
    st = doc.add_table(rows=0, cols=4); st.style = "Light Grid Accent 1"
    for i, row in enumerate(SUMMARY_ROWS):
        cells = st.add_row().cells
        for j, val in enumerate(row):
            cells[j].text = val
            p0 = cells[j].paragraphs[0]
            for run in p0.runs:
                run.font.size = Pt(9)
            if i == 0:
                for run in p0.runs:
                    run.bold = True; run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
                shade(cells[j], "1F3355")
            elif j == 2:
                col = SEV_COLOR.get(val, GREY)
                for run in p0.runs:
                    run.bold = True; run.font.color.rgb = col
    doc.add_paragraph()

    # Detailed findings
    heading(doc, "4. Detailed Findings", 1)
    for group_title, items in GROUPS:
        heading(doc, group_title, 2)
        for fid, title, sev, status, text in items:
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(2)
            lead = p.add_run(f"{fid} — {title}  ")
            lead.bold = True; lead.font.size = Pt(11); lead.font.color.rgb = NAVY
            tag = p.add_run(f"[{sev} · {status}]")
            tag.bold = True; tag.font.size = Pt(9.5); tag.font.color.rgb = SEV_COLOR.get(sev, GREY)
            body(doc, text, size=10.5, space_after=10)

    # Conclusion
    heading(doc, "5. Conclusion & Risk Posture", 1)
    body(doc, "The strongest signal from this review is the gap between the platform's documented "
              "security posture and its actual behaviour. The repository's own threat-model and "
              "architecture documents describe controls that the implementation does not apply:")
    for claim, reality in CLAIMS:
        p = doc.add_paragraph(style="List Bullet")
        rc = p.add_run("Claim: "); rc.bold = True
        p.add_run(claim)
        p2 = doc.add_paragraph()
        p2.paragraph_format.left_indent = Inches(0.5)
        rr = p2.add_run(reality); rr.italic = True; rr.font.color.rgb = GREY
    body(doc, "In short: the architecture diagram contained an authorization component, but the "
              "enforcer was imported by zero routes. The lesson is not that the engineering is poor — "
              "the durable core is genuinely solid — but that security controls must be verified in the "
              "request path, not asserted in a diagram. The highest-priority remediations are to "
              "enforce authorization server-side (F-03), reconnect the approval workflow gate (F-05), "
              "validate stage transitions (F-06), and restore the AI subsystem (F-10).")

    # Appendix
    heading(doc, "Appendix A — Assessment Areas", 1)
    for z in ZONES:
        p = doc.add_paragraph(style="List Bullet")
        p.add_run(z)
    body(doc, "Evidence (network captures, console logs and screenshots) was retained for each "
              "finding during testing.", size=9.5)

    os.makedirs(OUT_DIR, exist_ok=True)
    doc.save(OUT_PATH)
    print("WROTE", OUT_PATH)

if __name__ == "__main__":
    build()
