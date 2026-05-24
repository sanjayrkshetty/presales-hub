# Load Test Results — Phase 11

**Date:** 2026-05-24  
**Status:** Architecture analysis + expected characteristics (live results require running stack)

---

## How to Run

### Locust (all scenarios)

```bash
pip install locust
# Interactive UI:
locust -f load_tests/locustfile.py --host http://localhost:8003
# Headless:
locust -f load_tests/locustfile.py --host http://localhost:8003 \
       --users 50 --spawn-rate 5 --run-time 60s --headless
```

### Extended scenarios (Phase 11)

```bash
# Burst proposal writes — 10 VUs
locust -f load_tests/locustfile.py --host http://localhost:8003 \
       --users 10 --spawn-rate 2 --run-time 60s --headless \
       --class-picker ConcurrentProposalUser

# Approval storm — 5 VUs
locust -f load_tests/locustfile.py --host http://localhost:8003 \
       --users 5 --spawn-rate 1 --run-time 60s --headless \
       --class-picker ApprovalStormUser

# AI copilot load — 5 VUs with 4–8s think time
locust -f load_tests/locustfile.py --host http://localhost:8003 \
       --users 5 --spawn-rate 1 --run-time 120s --headless \
       --class-picker AICopilotUser
```

### WebSocket stress

```bash
pip install websocket-client
python load_tests/websocket_stress.py --clients 50 --duration 30
```

### k6

```bash
# Install k6: https://k6.io/docs/get-started/installation/
k6 run load_tests/k6/api_smoke.js
k6 run load_tests/k6/auth_flood.js
k6 run load_tests/k6/proposal_write.js
```

---

## Expected Performance Characteristics

Based on architecture analysis (SQLite in dev, PostgreSQL in production):

### Single-node estimate (4 vCPU / 8 GB RAM)

| Scenario | Estimated RPS | p95 latency | Notes |
|----------|--------------|-------------|-------|
| Read-only (analytics, opportunities) | 150–300 | <100ms | Cached by SQLAlchemy session |
| Authenticated read mix | 80–150 | <200ms | Token validation overhead ~20ms |
| Proposal creation (write) | 20–40 | <500ms | SQLAlchemy pool default: 5 connections |
| AI copilot requests | 2–5 | 2–8s | Rate-limited by LLM provider, circuit-broken |
| WebSocket connections | 200–500 | N/A | Event loop limited; upgrade to Centrifugo at 500+ |

### Concurrent user capacity estimate

| Concurrent users | Behavior |
|-----------------|----------|
| 1–10 | Smooth — single worker handles all traffic |
| 10–50 | Minor queueing on write paths; SQLAlchemy pool saturation possible |
| 50–100 | Requires multiple API replicas + connection pool tuning |
| 100+ | PostgreSQL becomes bottleneck; need read replicas + Redis-backed session store |
| 500+ concurrent WS | WebSocket broadcast must move to external service (Centrifugo/Ably) |

---

## Bottleneck Analysis

### 1. SQLAlchemy Connection Pool

**Default config:** `pool_size=5, max_overflow=10` (15 total connections)  
**Symptom:** Under 20+ concurrent write VUs, 503 pool timeout errors appear  
**Fix:** Increase `pool_size=10, max_overflow=20` in `db/database.py` + PostgreSQL `max_connections=100`

### 2. Event Loop Concurrency

**Architecture:** FastAPI async, but many routes call sync SQLAlchemy  
**Symptom:** CPU saturation before network saturation  
**Fix:** Use `run_in_executor` for blocking DB calls or migrate to async SQLAlchemy (SQLAlchemy 2.x)

### 3. Redis Pub/Sub Throughput

**Architecture:** Single Redis node, one listener task  
**Symptom:** WS event delivery lag under high publish rate  
**Limit:** ~50,000 messages/s on single Redis node (should not be hit at MVP scale)  
**Fix at scale:** Redis Cluster, or external WS service

### 4. AI Provider Latency

**Median response:** 1–5s per copilot call  
**Circuit breaker threshold:** 5 failures → OPEN state → 503  
**Under load:** Circuit breaker protects the event loop from blocking; 503s are expected

---

## Production Sizing Recommendations

| Component | Dev | Small production (≤25 users) | Scale (≤100 users) |
|-----------|-----|------------------------------|---------------------|
| API replicas | 1 | 2 (blue/green) | 3–4 behind load balancer |
| DB pool per replica | 5 | 10 | 15 |
| PostgreSQL max_connections | 50 | 100 | 200 + PgBouncer |
| Redis memory | 256 MB | 512 MB | 1 GB |
| WebSocket handling | In-process | In-process | Centrifugo sidecar |
| CDN/Edge caching | None | CloudFront for dashboard assets | Yes |

---

## Auth Flood (k6 auth_flood.js)

**Purpose:** Verify rate limiter fires before 22 consecutive login attempts  
**Expected result:** 429 appears within first 21 requests  
**Configured limit:** 20 requests/minute per IP (`LoginRateLimiter` in `middleware/rate_limit.py`)

---

## Write Contention (k6 proposal_write.js)

**Purpose:** Expose DB write deadlocks and pool exhaustion  
**Key metric:** `proposal_write_ms` p95 < 2000ms threshold  
**Watch for:** `pool_timeout_503` counter in k6 summary — any non-zero value signals pool exhaustion

---

## WebSocket Stress Results

**Script:** `load_tests/websocket_stress.py`  
**Target:** 80% of clients must connect successfully  
**Expected at 50 clients on single node:** All 50 connect within 200ms  
**Expected first message latency:** <500ms (broadcaster sends on connect + every 10s tick)
