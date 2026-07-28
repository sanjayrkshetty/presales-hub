# Presales Hub - Decisions Log

> Locked product and architecture decisions. Update when a decision changes; do not silently contradict this file.

**Last updated:** 2026-07-28

---

## D-001 - Personal project, not a SISA build

- **Decision:** Portfolio / personal demo. No SISA branding, client names, or unscrubbed IP in git or demos.
- **Inspiration only:** [sisa.ai](https://sisa.ai) central-platform story (split service lines -> unified layer) maps to **central presales over BUs**.

## D-002 - Two product jobs

1. Durable human-in-the-loop proposal lifecycle (Temporal + war room).
2. In-house RAG drafting -> editable `.docx` in the war room at drafting.

## D-003 - RAG first, not fine-tune

- ~10 months of Word proposals; scrub/forget requirement; laptop (12GB RAM / 6GB GPU).
- Fine-tune only later if structure/tone still fails with good retrieval.

## D-004 - Inference: Ollama on laptop

- Chat: ~8B Q4 (e.g. Qwen2.5 / Llama 3.1 class).
- Embeddings: `nomic-embed-text` (or equivalent local embed model).
- Cloud LLM only for **scrubbed** text if local quality is unacceptable.

## D-005 - Database: Postgres + pgvector

- **v1:** Local Docker Postgres 16; **app rows + vectors in one DB** (`presales_hub`).
- **Later demos:** **Neon** (managed Postgres). Scrubbed-only data OK in US/EU.
- **Not default:** Qdrant / Pinecone / Weaviate (add only on measured scale pain).
- **Not default:** Supabase (bundled auth/storage conflicts with existing FastAPI JWT stack). Revisit only if we deliberately replace auth/storage.

## D-006 - Temporal stays; separate Temporal DB

- Temporal is the durable control plane (multi-day waits, parallel reviews, SLA) - not the proposal writer.
- Keep container `temporal-db` separate from `postgres` / `presales_hub` (already in compose). Do not merge schemas.
- **Same engine, simpler DFIR UI path** - do not fork the workflow graph per BU.
- SME + calendar availability agent = future Activity inside Temporal + human confirm (not v1).

## D-007 - BU content packs

- v1: DFIR pack live; VAPT + GRC empty placeholders.
- Chunk metadata: `bu=dfir|vapt|grc|shared`. Retrieval filtered by selected pack.

## D-008 - Generate ACL

- Whole team may Generate (RBAC still applies to other mutating routes as we finish Part B).

## D-009 - Frontend direction

- Full visual redesign: Linear-inspired calm UI, airy spacing.
- **Dark default** + light mode toggle.
- Accent: **refined teal/cyan** (evolves current brand; avoid generic AI purple).
- **Role-based primary nav** - draft architecture below; refine after real multi-user use.

### Draft role -> primary nav (revise after use)

| Role | Primary nav (short) | Under More / Settings |
|------|---------------------|------------------------|
| `presales_lead` | Ops, Proposals, Approvals, Copilot/Generate | Analytics, Stakeholders, Workflows, System |
| `sme` | Proposals (mine), Approvals (mine), Copilot | Ops (read), Stakeholders |
| `approver` | Approvals, Proposals | Analytics |
| `executive` | Executive, Analytics, Proposals (read) | System (read) |
| `admin` | All primary + Platform / Integrations / System | - |

## D-010 - VA parked

- Yogesh asked to fix code, not run VA. Do not start VA unless Sanjay explicitly reopens it.

## D-011 - Part B RBAC continuation

- Branch `fix/part-b-remediation` already gates some write routes (`integration`, `agents`, `ai`, `copilot`).
- Next engineering session: **check out that branch and finish remaining write-route RBAC**, then click-path HIGH fixes.

## D-012 - Work style

- Minimal, reuse-first, no over-engineering.
- One logical change -> summarize -> commit -> ask before push.
- Docker: no source mounts in full compose -> `up -d --build <svc>` after code edits.

## D-013 - Session sequence

0. Docs (this arc) -> 1. RBAC -> 2. Click-path (pgvector, approval->Temporal, stage validation) -> 3. Scrub+RAG+docx -> 4. UI redesign