# Technical Debt Register

**Date:** 2026-05-24  
**Phase:** 11 (post-hardening)

---

## Immediate — Before First Paying Customer

These are blocking items for production trust.

| Item | Why it matters | Effort | Owner |
|------|---------------|--------|-------|
| Penetration test | No security posture claim is credible without external validation. WS auth, RBAC, admin key, LLM prompt injection all need testing. | 3–5 days (external) | Security team |
| E2E test coverage for approval workflow | Approval is the most complex flow (multi-level, Temporal-backed). No Playwright test covers the full chain including callback. | 1 day | Engineering |
| Refresh token rotation | Stolen refresh token is valid until expiry (default: 30 days). Single-use tokens prevent replay attacks. | 0.5 day | Engineering |
| CSRF protection on `/auth/refresh` | Cookie-based refresh is susceptible to CSRF. Add SameSite=Strict or CSRF token for this endpoint. | 0.5 day | Engineering |
| `LoginRateLimiter` is in-memory | Current rate limiter state resets on API restart. Multi-replica deployments have no shared state. | 0.5 day | Engineering |
| Migration tested on real PostgreSQL | All CI runs on SQLite. Alembic migrations have not been validated against PostgreSQL in CI. | 1 day | Engineering |
| Production secret rotation procedure | `SECRET_KEY` rotation invalidates all JWTs. No documented procedure for key rotation without downtime. | 0.5 day | Engineering |

---

## Medium-Term — Before 10+ Customers

These become load-bearing once there are multiple tenants and SLA commitments.

| Item | Why it matters | Effort |
|------|---------------|--------|
| CSRF protection (full) | Upgrade to SameSite=Strict + double-submit cookie pattern for all cookie-backed auth | 1 day |
| Redis Cluster / Sentinel | Single Redis node is SPOF. Sentinel adds automatic failover; Cluster adds horizontal scale | 3 days |
| Real nonces in CSP | Current CSP uses `'none'` for script-src on API (correct for API). Dashboard needs per-request nonces for Next.js hydration inline scripts | 1 day |
| Playwright visual regression tests | UI regressions caught by visual snapshots, not just E2E interaction tests | 2 days |
| SOC 2 evidence collection | Audit log → SIEM pipeline (Splunk/Datadog). Evidence collection for access control, change management, availability | 5+ days |
| Rate limiter backed by Redis | Replace in-memory `LoginRateLimiter` with Redis INCR + TTL for distributed enforcement | 1 day |
| Async SQLAlchemy | Current sync SQLAlchemy calls block the event loop. Migrate to `sqlalchemy.ext.asyncio` for better concurrency | 3–5 days |
| Admin key upgrade to JWT | Static `X-Admin-Key` is brittle. Replace with time-limited admin tokens with audit trail | 1 day |
| Prompt injection sanitization | User context is passed to LLM without sanitization. Add an input validation layer (deny list + length limits) | 1 day |
| AI quota hard enforcement | Token tracking exists but no hard block. Add Redis INCR counter that rejects over-quota requests | 1 day |

---

## Scale-Stage — Before 100+ Customers

These are architectural changes that cannot be retrofitted quickly.

| Item | Why it matters | Effort |
|------|---------------|--------|
| WebSocket broadcast service (Centrifugo/Ably) | Current in-process broadcast cannot scale beyond ~500 concurrent connections. Extracting to Centrifugo is a non-trivial refactor. | 5–10 days |
| Read replicas for PostgreSQL | Write-heavy analytics aggregations compete with read traffic. Read replicas require session management changes. | 3 days (infra) + 2 days (code) |
| Multi-region deployment | Currently designed for single-region. Multi-region requires data sovereignty decisions, latency-aware routing, replication topology. | 2–4 weeks |
| Real-time fraud/anomaly detection | Out of scope for MVP. Requires streaming pipeline (Kafka/Flink or similar). | Team-weeks |
| Advanced RAG corpus management | Current memory engine uses simple similarity search. Production RAG needs chunking strategy, re-ranking, evaluation pipeline. | Team-weeks |
| CRM integration maintenance | Salesforce/HubSpot APIs change; maintaining integration fabric requires dedicated engineering bandwidth. | Ongoing |
| Temporal cluster HA | Current Temporal is single-node in Docker. Production requires Temporal Cloud or self-hosted cluster. | 1 week |
| Grafana + PagerDuty observability | Current observability: Prometheus + Jaeger. Production requires dashboards (Grafana) + alerting (PagerDuty/OpsGenie). | 2–3 days |

---

## Already Addressed in Phase 11

| Item | Resolution |
|------|-----------|
| WS unauthenticated access | JWT validation on all 3 WS endpoints |
| CSP `unsafe-inline` on API | Removed — `script-src 'none'` |
| CORS wildcard methods/headers | Restricted to explicit allowlist |
| Sensitive fields in logs | `SensitiveFilter` redacts password/token/secret/api_key/authorization |
| slowapi/FastAPI incompatibility | Replaced `@limiter.limit()` decorator with `LoginRateLimiter` Depends |
| 204 response body assertion | `response_model=None` on logout endpoint |
