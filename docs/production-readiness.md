# Production Readiness Assessment — Presales Hub

> Assessed after Phase 10 completion. Covers security, reliability, observability,
> scalability, and demo readiness dimensions.

---

## Summary Scorecard

| Dimension | Status | Notes |
|-----------|--------|-------|
| Authentication & Authorization | **READY** | JWT + RBAC + account lockout |
| Multi-tenancy | **READY** | Row-level isolation, middleware-enforced |
| API Security | **READY** | Rate limiting, size limits, timeout middleware, security headers |
| AI Reliability | **READY** | Circuit breakers (Anthropic → OpenAI → Groq), DLQ, graceful degradation |
| Observability | **READY** | Prometheus metrics, structured logging, Temporal visibility |
| Database | **READY** | Alembic migrations, connection pooling, pgvector for RAG |
| Real-time Events | **READY** | Redis pub/sub + WebSocket fan-out + DLQ retry (1→5→15→60→240 min) |
| Deployment | **READY** | Docker Compose (dev), K8s manifests (prod), blue/green strategy documented |
| Secrets Management | **READY** | Startup validator blocks dev defaults in production |
| Demo Readiness | **READY** | Demo mode, synthetic events, reset button, executive wallboard |
| Accessibility | **PARTIAL** | aria-sort on DataTable, aria-label gaps on icon-only buttons in legacy components |
| Visual regression tests | **MISSING** | No screenshot/Playwright tests yet |
| E2E tests | **MISSING** | No Cypress/Playwright suite for user flows |

---

## Security Posture

### Implemented

- **Authentication**: JWT HMAC-SHA256, 15-min account lockout after 5 failed attempts
- **Rate limiting**: 20 req/min per IP on login (`slowapi`), configurable per-route
- **Transport**: TLS 1.2/1.3 enforced at nginx; HSTS 1 year
- **Headers**: CSP, X-Frame-Options: DENY, nosniff, X-XSS-Protection, Referrer-Policy
- **Payload guards**: RequestSizeLimitMiddleware (10 MB), RequestTimeoutMiddleware (30 s)
- **Tenant isolation**: `TenantContextMiddleware` on every request; all DB queries scoped to `tenant_id`
- **Secrets**: Startup validator rejects SQLite, DEBUG=true, or `dev-admin-key` in production
- **AI safety**: Grounding score threshold (≥ 0.6), evaluation score (≥ 0.7), safety_flags evaluation

### Remaining Gaps

| Gap | Risk | Mitigation path |
|-----|------|----------------|
| No CSRF token on form submissions | Medium | Mitigated by JWT Bearer auth (not cookie-based); add CSRF if switching to cookie sessions |
| Refresh token rotation not implemented | Low | Current short-lived JWT (configurable `exp`) is acceptable for MVP |
| Pen test not yet conducted | Unknown | Schedule with SISA team — they are the design partner |
| SOC 2 Type II evidence collection not automated | Low | Manual audit trail exists in AI governance logs |

---

## Reliability & Resilience

### Circuit Breakers

Three AI providers configured with automatic failover:

```
Anthropic Claude → OpenAI GPT-4o → Groq LLaMA
```

Circuit breaker thresholds (defaults):
- Failure threshold: 5 consecutive failures → OPEN
- Recovery window: 60 s in HALF_OPEN
- Surfaced in real-time on `/system` page

### Dead Letter Queue

- Events that fail to publish to Redis are persisted to `DeadLetterEvent` table
- Exponential retry: 1 → 5 → 15 → 60 → 240 min
- Admin API (`GET /api/admin/dlq`, `POST /api/admin/dlq/{id}/resolve`) for manual resolution
- DLQ pending count visible in `/api/health` and `/system` dashboard

### Temporal Workflow Orchestration

- All multi-step agent flows (RFP analysis, SME recommendation, proposal drafting, risk assessment) run as durable Temporal workflows
- Worker restarts recover in-flight workflows automatically
- Approval gate pattern prevents premature draft generation

---

## Observability

### Metrics (Prometheus)

- `/metrics` endpoint exposes standard FastAPI + custom counters
- AI request counts, circuit breaker state transitions, DLQ depth
- Redis and PostgreSQL health included in `/api/health`

### Logging

- Structured JSON logging with `correlation_id` propagated through middleware
- Every AI call logs: tenant_id, model, tokens (prompt + completion), cost_usd, latency_ms
- Full audit trail visible in AI Governance dashboard

### Dashboards Available

| Dashboard | URL | Refresh |
|-----------|-----|---------|
| Executive Wallboard | `/executive` | 15 s auto |
| Ops Console | `/ops` | WebSocket live |
| System Health | `/system` | 10 s auto |
| AI Governance | `/ai-governance` | On demand |
| Analytics | `/analytics` | On demand |

---

## Scalability

### Current Bottlenecks (by design — acceptable for MVP)

| Component | Limit | Path to scale |
|-----------|-------|--------------|
| Temporal worker | Single instance | Add worker replicas — stateless |
| Redis pub/sub | Single node | Redis Cluster or Valkey for HA |
| WebSocket broadcaster | In-process | Extract to dedicated broadcast service (e.g., Ably or self-hosted Centrifugo) |
| AI quota enforcement | DB-level count | Move to Redis INCR for lower latency at scale |

### Multi-Tenant Quota Model

- Per-tenant `monthly_token_limit` enforced before every AI call
- Quota breach forecast shown in AI Governance UI
- Per-tenant AI kill-switch (one click, instant effect)

---

## Demo Readiness

### What Works Without a Backend

- Demo mode (`?demo=1` or `NEXT_PUBLIC_DEMO_MODE=true`) injects synthetic events every 6–18 s
- Executive wallboard (`/executive`) shows live-updating KPIs from `analyticsApi`
- Activity feed, SLA alerts, notification panel all populated from synthetic stream
- Demo reset button (`DemoResetButton`) clears event log and re-seeds in <1 s

### Recommended Demo Setup

```bash
# Full stack (backend + dashboard)
make up-build

# Dashboard only (demo mode, no backend required)
cd apps/hub-dashboard
NEXT_PUBLIC_DEMO_MODE=true npm run dev
# Open http://localhost:3002?demo=1
```

### Screens for Each Audience

| Audience | Primary screens | Time |
|----------|----------------|------|
| Investors (8 min) | `/executive` → `/copilot` → `/system` → `/ai-governance` | See `docs/demo/investor-script.md` |
| CISO / Enterprise buyer (15 min) | `/executive` → `/ops` → `/copilot` → `/analytics` → `/system` → `/ai-governance` | See `docs/demo/executive-guide.md` |
| Technical review | `/system` + `/ai-governance` + API docs at `/docs` | Architecture diagrams in `docs/architecture/` |

---

## Remaining Work Before First Customer Deployment

**Must-have:**
- [ ] E2E test suite for login → proposal creation → approval flow (Playwright recommended)
- [ ] Pen test by SISA team (they are the design partner — internal resource available)
- [ ] Load test sign-off at target concurrency (load tests written in Phase 9 — run and document results)
- [ ] Environment-specific config validation (staging vs. production `DATABASE_URL`, `JWT_SECRET_KEY`)

**Nice-to-have:**
- [ ] `ANALYZE=true` CI step to track bundle size per PR
- [ ] Playwright visual regression snapshots for `/executive` and `/system`
- [ ] CSRF token implementation if cookie-based auth is added
- [ ] Accessibility audit: aria-labels on icon-only buttons in Sidebar and TopBar
- [ ] Storybook for UI system components (deferred — low ROI before Series A)
