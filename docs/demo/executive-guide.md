# Executive Demo Guide — Presales Hub

> 15-minute demo script for CISOs, Presales Leadership, and Enterprise Buyers.
> Audience: non-technical. Focus: business value, speed, risk reduction.

---

## Setup (2 min before demo)

```bash
# Start full stack
make up-build

# Open in browser (full-screen recommended)
open http://localhost:3002?demo=1

# Open executive wallboard directly
open http://localhost:3002/executive?demo=1
```

Press `F` on the executive page for fullscreen mode.
Press `P` to toggle presentation mode (enlarges KPIs).

---

## Demo Flow (15 min)

### 1. Executive Wallboard — First Impression (2 min)
**URL:** `/executive`

**Talk track:**
> "This is what your presales leadership sees every morning. Four numbers tell the whole story: total pipeline value, win rate, SLA health, and AI time saved. Right now you can see ₹X Cr at risk from SLA breaches. This updates automatically every 15 seconds from live data."

**Show:**
- Live clock + refresh indicator
- Pipeline funnel animation — watch counts animate on load
- Revenue at Risk card (highlight deal names in the right panel)
- "Today in Presales" briefing — SME capacity, breach count

**Transition:** "Let me show you what happens when a deal needs attention."

---

### 2. Operations Console — Day-to-Day Command Center (3 min)
**URL:** `/ops`

**Talk track:**
> "The ops console is the war room. Every live proposal, every SLA status, all in one screen. Watch this — when an event fires, the row highlights in real time. No refreshing, no reports. If an SLA is about to breach, it shows up in red here, and the presales lead gets notified instantly."

**Show:**
- KPI strip at top
- Live proposal table — point out health scores, SLA timers
- Activity feed on the right — synthetic events fire every 10s in demo mode
- Click an activity item to open the drill-down modal

**Transition:** "The AI doesn't just show problems — it helps you act on them."

---

### 3. AI Copilot — Analyst Augmentation (3 min)
**URL:** `/copilot`

**Talk track:**
> "Instead of your presales team spending 3 hours writing the first draft of an RFP response, AI Copilot generates it in under 2 minutes. Every output is grounded — see these citations? The AI pulled from your past winning proposals and compliance templates. The confidence score tells you how reliable this response is."

**Show:**
- Draft Assist — generate proposal section
- Confidence bar (hover for grounding score)
- Grounding Citations panel — show source documents
- Risk Explainer — AI-flagged risks

**Key stats to mention:** "We're tracking ~2.3 analyst hours saved per opportunity. At your pipeline volume, that's [X hours] per month."

---

### 4. Analytics — Board-Level Visibility (2 min)
**URL:** `/analytics`

**Talk track:**
> "This is what you bring to the board. Pipeline by stage, SLA breach distribution by stage, SME utilization heatmap. The red cells in the heatmap are SMEs who are over-capacity — that's where you have assignment risk. One click exports to CSV for your existing BI tools."

**Show:**
- Pipeline funnel chart (Recharts horizontal bar, animated)
- SLA breach by stage chart
- SME heatmap — hover cells to see individual utilization
- Export CSV button

---

### 5. System Health — Enterprise Reliability (2 min)
**URL:** `/system`

**Talk track:**
> "Enterprise buyers always ask: 'What happens when something fails?' This is your answer. Every external dependency has a circuit breaker. If Anthropic Claude has an outage, we automatically fail over to OpenAI, then Groq. Your presales team never hits a blank screen. Dead-letter queue means no events are ever lost — they retry automatically."

**Show:**
- Service health matrix (PostgreSQL, Redis, Temporal — all green)
- Circuit breaker state cards (CLOSED = healthy)
- WebSocket connection health
- DLQ pending count

---

### 6. AI Governance — Compliance and Cost Control (1 min)
**URL:** `/ai-governance`

**Talk track:**
> "For CISOs and compliance teams: every AI call is logged. Token usage per tenant, cost per tenant, quota limits. You can see exactly how much AI is being consumed and shut it down per-tenant if needed. Full audit trail."

**Show:**
- KPI strip: total tokens, cost, active tenants
- Daily token chart
- Quota utilization bars — point out near-limit tenants
- Per-tenant breakdown table

---

### 7. Close — Q&A Prompt (2 min)

**Key value propositions to re-state:**
1. **Speed**: RFP draft time 3h → 12 min
2. **Visibility**: Zero dark time — live ops console, SLA counters
3. **Risk reduction**: Circuit breakers, account lockout, request size limits, DLQ
4. **Compliance**: Per-tenant AI usage audit, quota enforcement
5. **Enterprise-ready**: Multi-tenant RBAC, blue/green deploy, K8s manifests

**Suggested closing question:**
> "What's the biggest bottleneck in your current presales process — is it speed, visibility, or consistency?"

---

## Common Objections

| Objection | Response |
|-----------|----------|
| "What if AI gives wrong advice?" | Grounding citations + confidence score + human approval gates on every AI output |
| "Our data can't leave our servers" | Self-hosted deployment — K8s manifests and Docker Compose provided. AI keys stay on your infra. |
| "How does this handle our existing CRM?" | Integration connectors (Salesforce, HubSpot, Slack) via webhook/sync. See Integrations page. |
| "What's the disaster recovery story?" | Blue/green deploy, Alembic migrations, DLQ retry, circuit breakers. See PRODUCTION.md. |
| "How do you handle multi-team access?" | RBAC with presales_lead, sme, approver, admin roles. Per-tenant isolation at DB row level. |
