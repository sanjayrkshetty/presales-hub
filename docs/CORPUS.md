# Presales Hub - Corpus Rules

> How we handle past proposals for in-house RAG. **Violating this file is a security/privacy incident for this project.**

**Last updated:** 2026-07-28

---

## Source location (outside git)

Raw proposals live on the workstation (example path used in planning):

`OneDrive/.../Desktop/proposals`

Approximate inventory (Jul 2026): ~294 files (~176 `.docx`, ~63 `.pdf`, ~38 `.xlsx`, plus others) across many deal folders.

**Never** copy unscrubbed trees into this repository, Docker build contexts, or GitHub.

---

## Allowed local layout (gitignored)

```
corpus/
  raw/          # optional local copies - MUST be gitignored
  scrubbed/     # only scrubbed text/docx for indexing
  manifest.json # optional: source hash, bu tag, scrub date - no client names
```

Add `corpus/` to `.gitignore` if not already present.

---

## Scrub requirements (before index or any remote DB)

Replace or remove:

- Client / prospect legal names and brand names
- SISA / employer branding and internal-only identifiers
- People names, emails, phones, addresses
- Specific contract prices, invoice amounts, bank details
- Logos and letterheads that identify parties

Allowed to keep as **patterns**:

- Section structure (scope, approach, assumptions, commercials layout)
- Generic service descriptions (e.g. DFIR retainership outline)
- Pseudonymized rate **bands** (e.g. `{{RATE_BAND_A}}`) - not real quote lines tied to a client

Pricing "understanding patterns" means structural/commercial section patterns from scrubbed exemplars - **not** retaining real client commercials.

---

## BU filtering

- v1 index: prefer DFIR-labelled / DFIR-named materials after scrub, plus optional `shared` boilerplate.
- Tag every chunk with `bu=dfir|vapt|grc|shared`.
- Empty packs (VAPT/GRC) may exist in UI with zero chunks.

---

## Indexing stack

- Store embeddings in **Postgres + pgvector** (same app DB): native `memory_chunks.embedding vector(384)` plus `embedding_json` for SQLite/tests.
- Embed with local `sentence-transformers/all-MiniLM-L6-v2` (**384** dims; not Ollama for v1).
- **Dual-write (intended end state):** upsert writes JSON and the native vector column when the schema is present (hardening may land on the Post-G1 reliability branch).
- **Fail-closed search:** when `USE_PGVECTOR` is true, missing extension/column must not silently fall back to app-side JSON cosine — run `alembic upgrade head` on a pgvector image.
- Chat/Generate uses Groq on **scrubbed** text only; LangGraph draft graph (D-014) with one repair then `template_fallback` if Groq is down or grounding fails.
- Session 2 CAST/rollback click-path fixes are prerequisite; do not demo Generate against a DB missing the vector column.

---

## Neon / cloud later

Only **scrubbed** corpus and scrubbed demo seed may leave the laptop. No raw OneDrive sync to Neon.

---

## Checklist before any Generate demo

- [ ] Raw paths not in git status
- [ ] Scrubbed sample indexed
- [ ] Retrieval filtered to intended `bu`
- [ ] Output is editable docx without real client identifiers
