# AGENTS.md - Working on Presales Hub

Instructions for Cursor / Claude / any coding agent. Humans: skim once; agents: follow every time.

**Last updated:** 2026-07-28

---

## Read first

1. [`PURPOSE.md`](PURPOSE.md) - why we exist
2. [`docs/DECISIONS.md`](docs/DECISIONS.md) - locked decisions
3. [`docs/CORPUS.md`](docs/CORPUS.md) - never commit real proposals
4. [`ROADMAP.md`](ROADMAP.md) - Now / Next / Later

Do **not** re-open settled decisions (RAG vs fine-tune, Qdrant, VA, Supabase Auth, Temporal removal) unless the user explicitly changes them.

---

## Guardrails

- Minimal, reuse-first, no over-engineering.
- Prefer wiring existing FastAPI / Temporal / memory_engine / copilot code over new frameworks.
- No LangGraph / Qdrant / fine-tune pipelines unless Sanjay asks.
- No unscrubbed client or employer data in the repo, commits, issues, or screenshots.
- Demo data only in seeds and docs.

---

## Stack (current)

| Layer | Choice |
|-------|--------|
| API | FastAPI (`apps/hub-api`) |
| UI | Next.js 15 (`apps/hub-dashboard`) |
| DB | Postgres 16 + pgvector (app + vectors) |
| Workflows | Temporal (`temporal-db` separate) |
| Cache/events | Redis |
| Local LLM | Ollama (to be wired) |
| Later hosted DB | Neon |

Docker full stack: `docker-compose.full.yml`. After code edits: `docker compose -f docker-compose.full.yml up -d --build <service>` (no source mounts).

---

## Git workflow (session loop)

1. One logical change (feature slice / fix / docs).
2. Show summary of files touched.
3. Commit with conventional message (`docs:`, `fix:`, `feat:`).
4. **Ask before `git push`** unless Sanjay said auto-push for the session.
5. Prefer feature branches (`fix/...`). Default branch is `master`.
6. Next RBAC work: continue on `fix/part-b-remediation` (partial `require_permission` already applied).

Never force-push to `master`. Never commit secrets (`.env`, raw corpus).

---

## Session sequence (do not skip ahead without asking)

0. Docs (PURPOSE / DECISIONS / CORPUS / AGENTS / ROADMAP) - anti-zero
1. Finish API RBAC write-route gating
2. Click-path HIGHs: pgvector CAST+rollback, approval -> Temporal signal, Temporal stage validation
3. Scrub + DFIR RAG ingest + war-room Generate -> docx
4. Full UI redesign: dark default, light toggle, teal/cyan, airy, role-based nav

---

## Frontend notes

- Target: simple, minimal, Linear-inspired calm product UI (not a 16-item ops cockpit by default).
- Theme: dark default + toggle; accent refined teal/cyan.
- Role nav: start from draft table in `docs/DECISIONS.md`; Sanjay will correct after multi-user use.

---

## If context is missing

Re-read PURPOSE + DECISIONS. Do not invent a new north star from old Claude Code resume prompts (Part B remediation prompts are historical; current sequence is above).