# Validation Report — Phase 11

**Date:** 2026-05-24  
**Commit range:** Phase 10 baseline → Phase 11  
**Environment:** Windows 11 / Python 3.11.9 / Node.js (runtime in container)

---

## Test Suite Results

### Backend — pytest

| Metric | Value |
|--------|-------|
| Total tests | 605 |
| Passed | 605 |
| Failed | 0 |
| Warnings | 3 (non-blocking: pydantic v2 deprecation, pythonjsonlogger module rename, opentelemetry importlib deprecation) |
| Runtime | 182.8s |

**Test files covered (17):**
- `test_health.py` — health, security headers, rate limiting, circuit breaker
- `test_auth.py` — login, refresh, logout, lockout, JWT validation
- `test_proposals.py` — CRUD, approval linkage, search
- `test_approvals.py` — multi-level approval workflow
- `test_opportunities.py` — pipeline CRUD
- `test_analytics.py` — pipeline/SLA aggregation
- `test_copilot.py` — AI section generation, mock provider
- `test_memory.py` — memory chunk ingestion and retrieval
- `test_decision_intelligence.py` — scoring logic
- `test_agents.py` — agent task lifecycle
- `test_strategy.py` — strategy generation
- `test_integration.py` — integration fabric
- `test_platform.py` — tenant/RBAC
- `test_ai_governance.py` — quota enforcement
- `test_admin.py` — admin router
- `test_dlq.py` — dead letter queue persist/retry
- `test_circuit_breaker.py` — state machine transitions

**Fixes applied in Phase 11:**
1. `routers/auth.py` line 165 — `response_model=None` added to 204 logout (FastAPI 0.115.5 stricter assertion)
2. `routers/auth.py` — Replaced `@limiter.limit("20/minute")` decorator with `Depends(login_rate_limiter)` to fix slowapi 0.1.9 / FastAPI 0.115.5 signature introspection incompatibility (decorator wrapped function caused FastAPI to misclassify `body` and `db` params as missing query params → 422)
3. `middleware/rate_limit.py` — Added `LoginRateLimiter` class (sliding-window, in-process, FastAPI Depends-compatible)

### Frontend — TypeScript

| Metric | Value |
|--------|-------|
| `tsc --noEmit` | PASS |
| Errors fixed | 2 |

**Fixes applied:**
- `components/analytics/FunnelChartInner.tsx:70` — Recharts `Tooltip.formatter` typed as `(v: any, _: any, item: any)` to handle `ValueType | undefined` (Recharts types emit `undefined` for values in newer versions)
- `components/analytics/SlaBreachTrendInner.tsx:65` — Same pattern; `Number(v)` cast handles `undefined` gracefully

### Frontend — Vitest

Not run in this environment (requires Node.js container). Run with:

```bash
make test-dash
# or
cd apps/hub-dashboard && npm test
```

Expected: existing vitest tests pass unchanged (no component logic modified in Phase 11).

---

## Bundle Size

Not captured in this environment. Build with:

```bash
cd apps/hub-dashboard && npm run build
```

Previous known output (Phase 10): ~310 kB first load JS, gzip ~95 kB.

---

## Startup Timing

From `docker compose logs --since 10s` on a 4-core VM:

| Service | Time to first healthy |
|---------|----------------------|
| postgres | ~3s |
| redis | ~1s |
| hub-api | ~8–12s (Alembic migrations + model init) |
| hub-dashboard | ~15–20s (Next.js build on first start) |
| temporal-worker | ~5s |

---

## Known Flaky Areas

| Test | Flakiness | Reason | Mitigation |
|------|-----------|--------|-----------|
| `test_rate_limit_on_login` | Previously flaky | slowapi 0.1.9 compat | Fixed: replaced with `LoginRateLimiter` Depends |
| `test_circuit_breaker_half_open` | Occasionally flaky | 1s timer is wall-clock sensitive in slow CI | Add `@pytest.mark.flaky(reruns=2)` if CI is slow |
| WebSocket E2E tests (Playwright) | Environment-dependent | Requires running compose stack | Only run in integration environment |

---

## Makefile Targets Added (Phase 11A)

```
make lint          # flake8 apps/hub-api --max-line-length=120
make lint-ts       # eslint app/**/*.tsx components/**/*.tsx lib/**/*.ts
make test-e2e      # playwright test
make smoke-docker  # curl /api/health + dashboard
make validate-all  # lint → lint-ts → typecheck → test-api → test-dash → smoke-docker
```
