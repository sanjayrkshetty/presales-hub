# Presales Hub - Purpose

> Single source of truth for **why this project exists**. Read this before changing scope.

**Owner:** Sanjay R K Shetty (personal project)
**Last updated:** 2026-07-28

---

## What this is

A **demoable, AI-assisted pre-sales operating console** for cybersecurity / compliance-style services work:

1. **Lifecycle ops** - A human (presales lead, SME, approver, executive) carries a proposal through a durable workflow: qualify -> assign SME -> draft -> reviews -> approve -> submit.
2. **In-house drafting** - At the drafting stage, attach a brief / RFP and **Generate** an editable Word (`.docx`) draft grounded on **scrubbed** past proposals via **RAG** (not fine-tuning first), with inference on a local LLM (Ollama) so sensitive material is not pasted into public AI tools.

It is **not** a SISA product, not an internal company system, and not a Vulnerability Assessment showcase. Public [sisa.ai](https://sisa.ai) (unified platform over historically split service lines) is **inspiration only** for the idea of a **central presales layer** over BU-split delivery.

---

## Problem it solves

Pre-sales work is high-context and deadline-bound: many opportunities, multi-stage proposals, SME coordination, approval chains, and SLAs - today often spreadsheets and email. Public AI is a poor fit for client RFPs and proposal IP. This hub keeps the **human as decision-maker**, makes state **durable** (Temporal), and keeps drafting **private** (local RAG over scrubbed corpus).

---

## Demo success (definition of done for the current arc)

Someone can:

1. Log in (demo users).
2. Open a proposal war room and advance stages without crashes / 404s.
3. Assign SME / complete approvals so the lifecycle actually moves.
4. At drafting: Generate a scrubbed-grounded **docx**.
5. Hard-refresh and still see workflow state (Temporal durability).

---

## Business-unit model

- **Central UI** over multiple BUs (content packs).
- **v1:** DFIR pack is real; **VAPT** and **GRC** are empty placeholders to show "central over BUs."
- **Stages:** one Temporal engine for all BUs; **simpler DFIR path in the UI** (progressive disclosure) - do **not** fork the workflow graph per BU.

---

## Non-goals (for now)

- Not a general CRM.
- Not fine-tuning on real client data.
- Not shipping unscrubbed proposals to git, Docker images, or public remotes.
- Not a full VA / pentest engagement as the deliverable.
- Not replacing Temporal with ad-hoc agents for multi-day approvals.
- Not adopting Qdrant / LangGraph / Supabase Auth unless a measured need appears (see `docs/DECISIONS.md`).

---

## Related docs

| Doc | Role |
|-----|------|
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | Locked architecture and product decisions |
| [`docs/CORPUS.md`](docs/CORPUS.md) | Proposal corpus, scrub rules, never-commit |
| [`AGENTS.md`](AGENTS.md) | How coding agents must work this repo |
| [`ROADMAP.md`](ROADMAP.md) | Now / Next / Later |
| [`README.local.md`](README.local.md) | How to run the stack locally |