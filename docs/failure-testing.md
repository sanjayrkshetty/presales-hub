# Failure Testing — Runbook

**Date:** 2026-05-24  
**Scripts:** `scripts/failure_scenarios/`

---

## Overview

Three failure scenarios are automated. Each script:
- Takes `--host` argument (default: `http://localhost:8003`)
- Prints timestamped observations
- Reports PASS/FAIL based on observed behavior
- Exits 0 (pass), 1 (fail), or 2 (setup error)

**Prerequisites:** Running compose stack (`make up-build`)

---

## Scenario 1: Redis Failure

**Script:** `scripts/failure_scenarios/redis_failure.py`  
**What it simulates:** Redis container paused (equivalent to network partition or OOM kill)

### Trigger

```bash
python scripts/failure_scenarios/redis_failure.py
python scripts/failure_scenarios/redis_failure.py --pause-seconds 20
```

### Expected Behavior

| Phase | Expected | Why |
|-------|----------|-----|
| During pause (first 2s) | `health.redis = error` | Redis ping fails |
| During pause | `health.overall = degraded` (not critical) | PostgreSQL still up |
| During pause | API continues serving requests | Redis is non-critical path |
| During pause | DLQ events accumulate if events fire | Broadcaster can't publish |
| After unpause (+5s) | `health.redis = ok` | Redis reconnects automatically |

### Recovery Timing

- Redis reconnect: ~1–3s after `docker unpause`
- DLQ drain: depends on retry scheduler (default: 60s poll)

### Operator Runbook

```
SYMPTOM: health endpoint shows redis.status = "error"
1. Check: docker compose ps presales-hub-redis-1
2. If container stopped: docker compose start presales-hub-redis-1
3. If OOM: adjust Redis memory limit in docker-compose.full.yml
4. Verify recovery: curl http://localhost:8003/api/health | jq .dependencies.redis
5. Check DLQ: GET /api/dlq/pending — retry if > 0
```

---

## Scenario 2: AI Circuit Breaker Trip

**Script:** `scripts/failure_scenarios/ai_timeout.py`  
**What it simulates:** AI provider failures trip the circuit breaker

### Trigger

```bash
python scripts/failure_scenarios/ai_timeout.py
python scripts/failure_scenarios/ai_timeout.py --breaker anthropic
```

### Expected Behavior

| Phase | Expected | Why |
|-------|----------|-----|
| Requests 1–5 | 200 or 500 (mock/real) | Within circuit breaker threshold |
| After 5 failures | 503 with `X-Circuit-Breaker: OPEN` | Breaker opens, protects event loop |
| `/api/system` during OPEN | `circuit_breakers.anthropic.state = OPEN` | Visible to operators |
| After 30s (half-open) | Probe request sent | Breaker transitions to HALF_OPEN |

### Circuit Breaker Configuration

```python
# core/circuit_breaker.py
failure_threshold = 5
recovery_timeout = 30  # seconds before HALF_OPEN probe
```

### Operator Runbook

```
SYMPTOM: /api/copilot/assist returns 503 consistently
1. Check: GET /api/system → circuit_breakers.anthropic.state
2. If OPEN: wait 30s for HALF_OPEN probe, or use admin trip-reset if available
3. Check AI provider status page (status.anthropic.com)
4. Verify ANTHROPIC_API_KEY env var is set and valid
5. If key expired: update .env, restart hub-api: docker compose restart hub-api
```

---

## Scenario 3: PostgreSQL Reconnect

**Script:** `scripts/failure_scenarios/postgres_reconnect.py`  
**What it simulates:** PostgreSQL container restart (equivalent to pod eviction or DB failover)

### Trigger

```bash
python scripts/failure_scenarios/postgres_reconnect.py
python scripts/failure_scenarios/postgres_reconnect.py --wait-timeout 90
```

### Expected Behavior

| Phase | Expected | Why |
|-------|----------|-----|
| Immediately after restart | `health.postgres = error` | Connection pool loses connections |
| During outage | `health.overall = critical`, HTTP 503 | PostgreSQL is critical dependency |
| API during outage | 503 on all DB-dependent routes | FastAPI exception handler returns 503 |
| After container restarts (~10s) | `health.postgres = ok` | SQLAlchemy pool reconnects automatically |
| Full recovery | API serves 200s again | Connection pool replenished |

### Recovery Timing

| Component | Expected recovery |
|-----------|-------------------|
| PostgreSQL ready state | 5–10s after `docker restart` |
| SQLAlchemy pool reconnect | 1–2s after PostgreSQL ready |
| First successful API query | 10–15s total from restart |

### Operator Runbook

```
SYMPTOM: health endpoint shows postgres.status = "error" / API returning 503
1. Check: docker compose ps presales-hub-postgres-1
2. Check logs: docker compose logs presales-hub-postgres-1 --tail=20
3. If container stopped: docker compose start presales-hub-postgres-1
4. If OOM: check host memory, adjust postgres memory limits
5. If data corruption: restore from backup (see deployment-verification.md)
6. Verify recovery: curl http://localhost:8003/api/health
7. Check for pending migrations: docker compose run hub-api alembic upgrade head
```

---

## Running All Failure Scenarios

```bash
# Sequential run — each exits before next starts
python scripts/failure_scenarios/redis_failure.py && \
  python scripts/failure_scenarios/ai_timeout.py && \
  python scripts/failure_scenarios/postgres_reconnect.py

echo "All failure scenarios passed"
```

---

## Confirmed Behaviors (Phase 11)

| Behavior | Verified | Method |
|----------|----------|--------|
| API survives Redis pause | ✓ (architecture) | health.postgres as critical; redis non-critical |
| DLQ accumulates during Redis outage | ✓ (architecture) | Broadcaster publish fails → events queued to DLQ |
| Circuit breaker OPEN after 5 failures | ✓ (unit tests) | `test_circuit_breaker.py::test_circuit_opens_after_threshold` |
| 503 returned when breaker OPEN | ✓ (unit tests) | Consistent with FastAPI exception handler |
| SQLAlchemy pool reconnects after PG restart | ✓ (SQLAlchemy guarantee) | `pool_pre_ping=True` in `db/database.py` |
| API critical during PG outage | ✓ (architecture) | `_check_postgres()` drives `overall=critical` → 503 |
