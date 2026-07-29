# Presales Hub - Purpose

> Single source of truth for **why this project exists**. Read this before changing scope.

**Owner:** Sanjay R K Shetty (personal project)
**Last updated:** 2026-07-29

---

## Why I built this (personal story)

Two pressures made "just paste the RFP into ChatGPT / Claude" unacceptable for me:

1. **Organisational DLP / policy reality.** Corporate Data Loss Prevention does not treat public Generative AI as a safe scratchpad. A representative control message:

   > "Our Data Loss Prevention (DLP) system detected a copy/paste action of sensitive corporate content into a public Generative AI platform."

   That is not a theoretical risk — it is an **enforced boundary**. Presales content (client RFPs, proposal IP, commercials patterns) is exactly the class of material DLP exists to stop leaking into consumer AI products.

2. **Erosion of trust in public AI tooling.** I was genuinely devastated to see reporting such as [this IntCyberDigest thread](https://x.com/IntCyberDigest/status/2082047179276120142) on opaque / covert handling of user context inside public AI coding agents. Even when the vendor narrative is "helpful agent," the **control and transparency** story is broken: you cannot responsibly put employer or client material into a black box you do not operate.

**Design consequence for this repo:** scrub before any remote call; embeddings stay local (MiniLM); chat/Generate may use Groq **only on scrubbed text + scrubbed retrieved chunks**; raw proposals never enter git, Docker images, or public remotes ([docs/CORPUS.md](docs/CORPUS.md)). The human stays the decision-maker; the hub is a **private drafting + durable lifecycle** console, not a paste-into-public-AI shortcut.

---

## What this is

A **demoable, AI-assisted pre-sales operating console** for cybersecurity / compliance-style services work:

1. **Lifecycle ops** - A human (presales lead, SME, approver, executive) carries a proposal through a durable workflow: qualify -> assign SME -> draft -> reviews -> approve -> submit.
2. **In-house drafting** - At the drafting stage, attach a brief / RFP and **Generate** an editable Word (`.docx`) draft grounded on **scrubbed** past proposals via **RAG** (not fine-tuning first). Chat uses Groq on **scrubbed-only** payloads; embeddings are local `all-MiniLM-L6-v2` — so sensitive material is not pasted raw into public AI tools.

It is **not** a SISA product, not an internal company system, and not a Vulnerability Assessment showcase. Public [sisa.ai](https://sisa.ai) (unified platform over historically split service lines) is **inspiration only** for the idea of a **central presales layer** over BU-split delivery. The DLP / public-AI distrust story above is **personal motivation** for the architecture — not a claim that this repo is an employer production system.

---

## Problem it solves

Pre-sales work is high-context and deadline-bound: many opportunities, multi-stage proposals, SME coordination, approval chains, and SLAs - today often spreadsheets and email. Public AI is a poor fit for client RFPs and proposal IP — both because **policy/DLP forbids the paste**, and because **trust in public agent tooling is thin**. This hub keeps the **human as decision-maker**, makes state **durable** (Temporal), and keeps drafting **private-by-construction** (scrub -> local embed -> scrubbed-only cloud chat -> editable docx).

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
- Not adopting Qdrant / fine-tune-first / Supabase Auth unless a measured need appears (see `docs/DECISIONS.md`). LangGraph is allowed **draft-only** once decided in DECISIONS; Temporal remains the lifecycle control plane.

---

## Related docs

| Doc | Role |
|-----|------|
| [`docs/DECISIONS.md`](docs/DECISIONS.md) | Locked architecture and product decisions |
| [`docs/CORPUS.md`](docs/CORPUS.md) | Proposal corpus, scrub rules, never-commit |
| [`AGENTS.md`](AGENTS.md) | How coding agents must work this repo |
| [`ROADMAP.md`](ROADMAP.md) | Now / Next / Later |
| [`README.local.md`](README.local.md) | How to run the stack locally |