# Presales Hub - Roadmap

> An AI-native operating console for the pre-sales lifecycle: discovery -> scoping -> proposal ->
> approval, with durable workflows and **in-house** AI drafting (RAG over scrubbed proposals).

This document is the public point of view on where Presales Hub is and where it is going. It is
deliberately honest about current maturity.

**Canonical intent:** see [`PURPOSE.md`](PURPOSE.md) and [`docs/DECISIONS.md`](docs/DECISIONS.md).
**AI topology:** see [`docs/architecture/ai-pipeline.md`](docs/architecture/ai-pipeline.md).

---

## Why this exists

Pre-sales work in security and compliance services is high-context and deadline-bound: many
opportunities, multi-stage proposals, SME assignments, approval chains, and SLAs running in parallel.
Presales Hub models that lifecycle as durable, observable, AI-assisted workflows instead of
spreadsheets and email threads - and keeps sensitive drafting **in-house** via local RAG.

**Motivation (personal):** organisational DLP blocks pasting sensitive content into public Generative AI,
and trust in opaque public-AI agent tooling is thin. Design consequence: scrub before remote calls;
embeddings stay local (MiniLM); chat/Generate may use Groq **only on scrubbed** payloads. See [`PURPOSE.md`](PURPOSE.md).

This is a **personal** project (not a SISA product). Employer/public platforms may inspire the
"central layer over BUs" story; they do not own this repo.

## Engineering principles

1. **Security is a feature, not a footnote.** Auth, RBAC, scrubbed corpus, and honest docs.
2. **Durable over best-effort.** Proposal lifecycles run on Temporal.
3. **Private by default for AI.** Scrub -> local embed (MiniLM) -> Groq on scrubbed-only -> editable docx; no raw client docs in git.
4. **Honest maturity.** Ship what works, document what does not.

---

## Where it is today

**Foundation running locally** (FastAPI + Next.js + PostgreSQL/pgvector + Redis + Temporal):

- Opportunity, proposal, approval, stakeholder, and analytics domains
- Durable proposal-lifecycle workflows on Temporal (engine sound; Session 4 UI still deferred)
- Real-time dashboard via WebSocket event streaming
- JWT auth + partial route-level RBAC
- Observability: health/ready, Prometheus, Jaeger, Langfuse draft spans

**Sessions 0–3 + G1 landed (high level):**

- Anti-zero docs (PURPOSE / DECISIONS / CORPUS / AGENTS)
- Click-path HIGHs (pgvector CAST/rollback, approval → Temporal, stage validation) on remediation branches
- Scrub + DFIR RAG ingest + war-room Generate → editable `.docx`
- LangGraph **draft-only** graph (D-014): load → scrub → retrieve → graph_expand → draft → validate → repair/fallback → emit
- Chat = Groq scrubbed-only; embeddings = local `all-MiniLM-L6-v2` (384-d); pgvector column + dual-write intent; fail-closed search when schema missing
- `generate-docx` uses per-route **180s** `TimeoutAPIRoute` (not the 30s middleware default)

**Open work (ordered):** Post-G1 reliability (pgvector dual-write / fail-closed hardening) → Session 4 UI redesign (deferred) → share/host scrubbed demo later.

---

## Roadmap

### Done recently - Docs, click-path, scrub+RAG+docx, G1 draft graph

- PURPOSE / DECISIONS / CORPUS / AGENTS / architecture docs aligned with D-004 / D-006 / D-014
- Scrub pipeline + DFIR pack ingest + Generate → docx
- LangGraph drafting with grounding hard gate + template fallback
- Temporal remains lifecycle-only (not proposal writer)

### Now - Post-G1 reliability

- pgvector `embedding vector(384)` migration + dual-write upsert
- Fail-closed when USE_PGVECTOR and schema/extension missing (no silent JSON cosine for search)
- Keep generate-docx within 180s route timeout under load

### Next - Session 4 UI (deferred)

- Full visual redesign: dark default, light toggle, teal/cyan, airy layout, role-based nav
- DFIR + empty VAPT/GRC packs in UI
- Same Temporal engine; simpler DFIR UI path (no workflow fork)

### Later - Share and deepen

- Neon for scrubbed demo hosting
- Optional SME availability Activity (calendar) with human confirm
- Multi-user SaaS hardening if the product earns it
- Deeper AI quality only after RAG demo stays reliable

---

## Non-goals (for now)

- Not a general CRM.
- Not fine-tune-first or public-AI pasting of client RFPs.
- Not VA-as-the-product (parked).
- Not replacing Temporal with LangGraph for multi-day approvals.
- Not chasing feature breadth ahead of a clean demo loop.

---

*Maintained by [Sanjay R K Shetty](https://github.com/sanjayrkshetty). Roadmap is a direction, not a contract.*
