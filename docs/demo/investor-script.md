# Investor Demo Script — Presales Hub

> 8-minute pitch flow. Audience: technical investors, VCs, strategic partners.
> Focus: TAM, defensibility, architecture quality, traction potential.

---

## The Problem (1 min)

> "Every enterprise sales team has a presales bottleneck. RFP responses take 3-5 analyst days. SLA compliance is tracked in spreadsheets. AI tools are siloed — no context from past wins, no workflow integration, no governance."

**Numbers to cite:**
- Average enterprise RFP response: 40-120 hours of analyst time
- Win rate for timely responses vs. delayed: 2-3× higher
- Compliance failure rate for manually-tracked SLAs: ~30% at scale

---

## The Solution (1 min)

> "Presales Hub is an AI-native presales operating system. Not a productivity tool — an OS. It orchestrates the entire deal lifecycle: RFP intake → discovery → SME coordination → AI-assisted drafting → multi-level approval → submission. With full observability, multi-tenant controls, and enterprise security from day one."

**Architecture headline:**
- FastAPI backend with Temporal workflow orchestration
- Claude AI with RAG grounding (every output is cited)
- Real-time WebSocket event bus
- Circuit breakers on every external provider
- Multi-tenant RBAC from the first commit

---

## Live Demo (4 min)

### Screen 1: Executive Wallboard (`/executive`)
> "This is the VP of Sales dashboard. ₹12.4 Cr pipeline, 67% win rate, 2 SLA breaches right now — one of them is ₹3.2 Cr at risk. The CFO sees this on a conference room screen. Updates every 15 seconds from live data."

**Investor signal:** *The metric they're looking at is revenue-at-risk, not activity metrics. This is how enterprise software justifies its price point.*

### Screen 2: AI Copilot (`/copilot`)
> "This is where the time savings happen. 12 minutes to generate a proposal draft that took 3 hours before. Every line is grounded in the company's past wins, compliance templates, and industry knowledge. The confidence score is not a gimmick — it's a calibrated grounding metric we enforce server-side."

**Investor signal:** *The differentiation is in the grounding layer + evaluation score, not the LLM call.*

### Screen 3: System Health (`/system`)
> "Enterprise buyers ask: 'What's your SLA?' This is our answer. Circuit breakers on every AI provider. If Anthropic goes down, we failover automatically. Dead-letter queue means zero data loss. This is how you sell to a CISO."

**Investor signal:** *Production-grade reliability is table stakes for enterprise. Most AI startups skip this. We built it first.*

### Screen 4: AI Governance (`/ai-governance`)
> "GDPR, SOC 2, ISO 27001 — every AI call is logged with tenant, tokens, cost, model version. You can shut down AI per-tenant in one click. This is how you close regulated industries: BFSI, healthcare, government."

**Investor signal:** *Governance and compliance are the moat in regulated verticals.*

---

## Traction & Go-To-Market (1 min)

**SISA Information Security — Design Partner**
- Active pre-sales deployment covering 6 service lines (ISO, PCI DSS, SOC, Pen Testing, DFIR)
- Real RFPs being processed through the system
- Direct feedback loop for enterprise presales workflow requirements

**Target ICP:**
- Enterprise security/consulting firms (50-500 person presales teams)
- IT services companies managing complex multi-stakeholder RFPs
- Regulated industry verticals requiring AI governance (BFSI, healthcare, government)

---

## Defensibility (30 sec)

1. **Workflow intelligence**: Temporal-orchestrated state machine is not replicable by adding AI to a CRM
2. **Grounding layer**: RAG with evaluation scoring creates institutional memory moat
3. **Enterprise-first architecture**: Multi-tenant, RBAC, circuit breakers, DLQ — most competitors retrofit this
4. **Vertical depth**: SISA partnership gives us domain data (compliance frameworks, security scoping patterns) that can't be scraped

---

## Ask (30 sec)

> "We're raising a [seed/Series A] round to expand the integration layer (CRM connectors, ERP sync), deepen the AI grounding corpus, and hire two enterprise AEs to replicate the SISA playbook at 10 more firms."

---

## Technical Q&A Cheat Sheet

| Question | Answer |
|----------|--------|
| "What's the tech stack?" | FastAPI + Next.js 15 + Temporal + PostgreSQL + Redis. No vendor lock-in on AI — provider abstraction with circuit breakers. |
| "How does the RAG work?" | Chunked documents → embedding → pgvector cosine similarity → top-k with score ≥ 0.6 threshold. |
| "How do you handle multi-tenancy?" | Row-level isolation via tenant_id, middleware-enforced context, per-tenant quotas and feature flags. |
| "Is this a wrapper around ChatGPT?" | No. We orchestrate 3 providers with failover, add grounding + evaluation layers, and wrap it in enterprise workflow (Temporal). |
| "What's the deployment model?" | Self-hosted (K8s manifests + Docker Compose) or managed cloud. Customer controls where data lives. |
| "How do you handle hallucinations?" | Grounding score threshold, evaluation_score field, human approval gates at the workflow level. |
