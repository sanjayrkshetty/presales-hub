# Presales Hub - Roadmap

> An AI-native operating console for the pre-sales lifecycle: discovery -> scoping -> proposal ->
> approval, with durable workflows and **in-house** AI drafting (RAG over scrubbed proposals).

This document is the public point of view on where Presales Hub is and where it is going. It is
deliberately honest about current maturity.

**Canonical intent:** see [`PURPOSE.md`](PURPOSE.md) and [`docs/DECISIONS.md`](docs/DECISIONS.md).

---

## Why this exists

Pre-sales work in security and compliance services is high-context and deadline-bound: many
opportunities, multi-stage proposals, SME assignments, approval chains, and SLAs running in parallel.
Presales Hub models that lifecycle as durable, observable, AI-assisted workflows instead of
spreadsheets and email threads - and keeps sensitive drafting **in-house** via local RAG.

This is a **personal** project (not a SISA product). Employer/public platforms may inspire the
"central layer over BUs" story; they do not own this repo.

## Engineering principles

1. **Security is a feature, not a footnote.** Auth, RBAC, scrubbed corpus, and honest docs.
2. **Durable over best-effort.** Proposal lifecycles run on Temporal.
3. **Private by default for AI.** Scrub -> retrieve -> generate locally (Ollama); no raw client docs in git.
4. **Honest maturity.** Ship what works, document what does not.

---

## Where it is today

**Foundation running locally** (FastAPI + Next.js + PostgreSQL/pgvector + Redis + Temporal):

- Opportunity, proposal, approval, stakeholder, and analytics domains
- Durable proposal-lifecycle workflows on Temporal (engine sound; UI/AI wiring still has gaps)
- Real-time dashboard via WebSocket event streaming
- JWT auth (auth-on-routers and cookie/bootstrap fixes landed; route-level RBAC partially started)
- Observability: health/ready, Prometheus, Jaeger

**Open work (ordered):** finish RBAC -> fix click-path HIGHs (incl. pgvector/copilot) -> scrubbed RAG Generate -> minimal dark/light UI redesign.

---

## Roadmap

### Now - Anti-zero docs + harden the click path

- Keep PURPOSE / DECISIONS / CORPUS / AGENTS aligned with reality
- Finish write-route RBAC (`fix/part-b-remediation`)
- Fix pgvector session poison; bridge approvals to Temporal; validate Temporal stage transitions
- Verify against browser behaviour, not only curl

### Next - In-house draft loop + simpler product UI

- Scrub pipeline + DFIR content pack ingest
- War-room Generate -> editable docx (Ollama)
- DFIR + empty VAPT/GRC packs in UI
- Full visual redesign: dark default, light toggle, teal/cyan, airy layout, role-based nav
- Same Temporal engine; simpler DFIR UI path (no workflow fork)

### Later - Share and deepen

- Neon for scrubbed demo hosting
- Optional SME availability Activity (calendar) with human confirm
- Multi-user SaaS hardening if the product earns it
- Deeper AI quality only after RAG demo works

---

## Non-goals (for now)

- Not a general CRM.
- Not fine-tune-first or public-AI pasting of client RFPs.
- Not VA-as-the-product (parked).
- Not chasing feature breadth ahead of a clean demo loop.

---

*Maintained by [Sanjay R K Shetty](https://github.com/sanjayrkshetty). Roadmap is a direction, not a contract.*