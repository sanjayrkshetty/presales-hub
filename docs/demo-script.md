# Demo Script — 15-Minute Presales Hub Walkthrough

**Audience:** Investor / Pilot customer / Internal stakeholder  
**Duration:** 13–15 minutes + Q&A  
**Prerequisites:** Stack running (`make up-build`), seeded with enterprise data (`make seed`)  
**Login URL:** http://localhost:3002

---

## Pre-Demo Checklist (5 min before)

```bash
make up           # start stack if not running
curl -s http://localhost:8003/api/health | python -m json.tool
# health.status must be "ok" or "degraded" — not "critical"
```

- [ ] Browser at http://localhost:3002, logged out
- [ ] Devtools closed, zoom at 100%
- [ ] `/system` page: circuit breakers all CLOSED, DLQ = 0
- [ ] Backup: have `/executive` route bookmarked if login is slow

---

## Minute 0–1: Login & First Impression

**URL:** http://localhost:3002/login  
**Credentials:** arjun@sisa.demo / Demo@1234

**Talk track:**  
> "This is Arjun — he leads pre-sales at a mid-size cybersecurity firm. His team handles 30+ active opportunities at any time across ISO 27001, PCI DSS, penetration testing, and DFIR. He opens the hub every morning. Notice: no blank screen. It's instant."

**Wow moment:** Dashboard loads data in < 1s (cached pipeline data, no spinner on KPI cards).

**Fallback:** If login is slow (>3s), say "The API is doing a cold start — in production this would be pre-warmed." Navigate directly to `/executive`.

---

## Minute 1–3: Executive Dashboard

**URL:** /executive  
**Key elements to show:**
- 4 KPI cards: Open Opportunities, Weighted Pipeline Value, SLA Compliance Rate, Average Deal Velocity
- Revenue at Risk tile (amber/red)
- Animated funnel — click to expand
- Press **F** for fullscreen mode (built-in for investor demos)

**Talk track:**  
> "This is Arjun's first screen. Four numbers that answer: are we healthy? The revenue-at-risk tile tells him which deals need attention today without scrolling. The funnel shows where deals are stalling. This view auto-refreshes every 30 seconds — Arjun can put it on a wall monitor."

**Wow moment:** Press **F** — funnel expands to full-screen. This is the investor screen.

---

## Minute 3–5: Operations Dashboard

**URL:** /ops  
**Key elements:**
- Live activity feed (fires every 10s — events are real-time via WebSocket)
- SLA timer countdown on at-risk deals
- Click any activity item → drill-down modal with full context

**Talk track:**  
> "This is the ops view — what's happening right now. Every event — proposal updated, approval decision, SLA breach — fires in under 100 milliseconds. The SLA timer isn't cosmetic: when it hits zero, the system triggers escalation logic. Click this activity item."

**Wow moment:** Click activity → modal opens with deal history, stakeholder map, and recommended next action.

**Fallback:** If activity feed is empty, navigate to `/ops` — events are broadcasted on a 10s tick. Wait 10s.

---

## Minute 5–7: AI Copilot

**URL:** /copilot  
**Key elements:**
- Section selector (Executive Summary, Scope of Work, Pricing, Risk Mitigation)
- Generate button → streamed response with confidence bar
- Grounding citations panel (links to which memory/context was used)
- Risk flags panel (auto-detected scope risks)

**Talk track:**  
> "Arjun is writing a proposal for a healthcare client. He picks 'Scope of Work', adds context, clicks Generate. The model doesn't hallucinate scope — it's grounded in this client's past engagements, SISA's service catalog, and regulatory requirements. The confidence bar reflects how much of the output is grounded versus generated. Risk flags surface automatically: here it's flagging that the client's stated timeline conflicts with typical HIPAA readiness durations."

**Wow moment:** Show the grounding citations panel — point to specific memory chunks that informed the output.

**Fallback:** If AI returns 503 (circuit breaker open), say "This is the circuit breaker in action — the AI provider is degraded, so the system returns a graceful error rather than hanging. In production you'd have a fallback to a cheaper model." Navigate to `/system` to show the OPEN state.

---

## Minute 7–9: Approval Workflow

**URL:** /approvals  
**Key elements:**
- Pending approval queue (multi-level: L1 → L2 → L3)
- Approve / Escalate / Request Info buttons
- Approval chain visualization

**Talk track:**  
> "Any proposal above $200K requires three approval levels. Arjun can see what's waiting for him, what's pending others, and the full chain. One click to approve — the action is audited and time-stamped. The Temporal workflow underneath ensures this survives a server restart: approval state is durable, not in-memory."

**Wow moment:** Approve a decision → the opportunity status updates in real-time on the activity feed (visible if `/ops` is open in another tab).

---

## Minute 9–11: Analytics

**URL:** /analytics  
**Key elements:**
- Funnel chart with stage conversion rates
- SLA breach by stage (bar chart)
- SME utilization heatmap
- Export to CSV button

**Talk track:**  
> "This is the analytics layer — not just charts, but actionable data. The funnel shows conversion by stage: this firm is losing deals at the 'scoping' stage at 34% — that's a coaching signal. SLA breaches by stage show where the process breaks. The SME heatmap shows who's over-utilized — critical for capacity planning. Everything exports to CSV for Excel."

**Wow moment:** Export CSV — file downloads immediately, opens in Excel cleanly.

---

## Minute 11–12: System Health

**URL:** /system  
**Key elements:**
- Circuit breaker status table (anthropic / openai / groq / temporal)
- DLQ event count (should be 0 in clean state)
- WebSocket connection indicator (live)
- Memory usage + uptime

**Talk track:**  
> "This is what the ops team watches. Every AI provider has a circuit breaker — if Anthropic is down, we switch to OpenAI or Groq without user impact. Dead Letter Queue shows events that failed to process — in a healthy system it's zero. The WebSocket indicator is live: that green dot means all 3 WS channels are active right now."

**Wow moment:** If a circuit breaker is OPEN (from earlier demo), show the state machine logic — CLOSED → OPEN → HALF_OPEN → CLOSED.

---

## Minute 12–13: AI Governance

**URL:** /ai-governance  
**Key elements:**
- Per-tenant token usage (bar/line chart)
- Quota forecast (will this tenant exceed their monthly limit?)
- Efficiency trend (tokens per proposal section over time)
- Provider split (Anthropic vs OpenAI vs Groq by request)

**Talk track:**  
> "This is the commercial layer on top of AI. Every token consumed by every tenant is tracked. When a tenant is trending toward their quota limit, the system flags it before they hit it. The efficiency trend shows whether AI-assisted proposals are getting better or worse at using context — a signal for prompt quality improvement."

---

## Minute 13–15: Q&A + Technical Cheat Sheet

Use the Q&A section from [docs/demo/investor-script.md](demo/investor-script.md) for common objections.

**Top 3 questions and one-sentence answers:**

| Question | Answer |
|----------|--------|
| "Is the AI output accurate?" | "Grounded in your firm's actual service catalog and past proposals — the confidence bar tells you exactly how much is grounded vs. generated." |
| "What happens when an AI provider goes down?" | "Circuit breakers automatically failover — your reps keep working, they just see a slightly slower response while the backup provider is probed." |
| "How does it integrate with our CRM?" | "Integration fabric in Phase 2 — REST webhook targets for Salesforce, HubSpot, and custom CRMs. Currently in the roadmap after pilot feedback." |

---

## Demo Mode Notes

- Demo mode is always active (`DemoModeProvider`) — no real API keys required
- All AI responses in demo mode use cached/mock outputs
- Data is fully seeded with enterprise-realistic opportunity data
- If any page shows an error, refresh once — the mock LLM provider has random latency
