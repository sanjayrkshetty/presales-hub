# Presales Hub — Local Development Guide

> Enterprise AI-Native Presales Operating System — Full Local Stack

---

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Docker Desktop | 4.x+ | Container runtime |
| Docker Compose | v2 (bundled with Docker Desktop) | Multi-service orchestration |
| Node.js | 20+ | Frontend development |
| Python | 3.11+ | Backend development |
| make | any | Convenience targets |

Run the bootstrap check before your first start:

```bash
bash scripts/bootstrap_check.sh
```

This validates tool versions, port availability, disk space, and dependency installation in one pass.

---

## Quick Start (5 minutes)

```bash
# 1. Clone and enter the repo
git clone <repo-url>
cd presales-hub

# 2. Copy environment file
cp .env.full.example .env.full

# 3. (Optional) Validate environment before starting
python -m apps.hub-api.scripts.validate_env

# 4. Start the full stack (builds images, seeds data, opens demo info)
make up-build

# 5. Open the dashboard
open http://localhost:3002
```

Login with the demo credentials printed by `make demo`.

---

## Service URLs

| Service | URL | Purpose |
|---------|-----|---------|
| **Dashboard** | http://localhost:3002 | Main Next.js UI |
| **API** | http://localhost:8003 | FastAPI backend |
| **API Docs** | http://localhost:8003/docs | Swagger / OpenAPI |
| **Health** | http://localhost:8003/api/health | Dependency health (PG + Redis + Temporal) |
| **Readiness** | http://localhost:8003/api/ready | K8s readiness probe endpoint |
| **Metrics** | http://localhost:8003/metrics | Prometheus metrics scrape endpoint |
| **Worker Health** | http://localhost:8004/health | Temporal worker liveness |
| **Temporal UI** | http://localhost:8080 | Workflow inspector |
| **Jaeger** | http://localhost:16686 | Distributed traces |
| **pgAdmin** | http://localhost:5050 | DB browser (opt-in — see below) |

---

## Demo Credentials

| Role | Email | Password |
|------|-------|---------|
| Platform Admin | `admin@presaleshub.io` | `Admin@1234` |
| Presales Lead | `arjun@sisa.demo` | `Demo@1234` |
| SME (Security) | `vikram@sisa.demo` | `Demo@1234` |
| SME (Compliance) | `priya@sisa.demo` | `Demo@1234` |
| Executive | `ceo@sisa.demo` | `Demo@1234` |

---

## Make Targets

```bash
make up           # Start all services in background
make up-build     # Rebuild images then start (use after code changes)
make down         # Stop all services (data preserved)
make reset        # Wipe all data volumes and restart fresh
make seed         # Re-run enterprise seed against live stack
make logs         # Tail API + dashboard logs
make logs-api     # Tail backend logs only
make logs-dash    # Tail dashboard logs only
make logs-worker  # Tail temporal-worker logs only
make test         # Run full test suite (backend + frontend)
make test-api     # Backend pytest only
make test-dash    # Frontend vitest only
make typecheck    # TypeScript type check (tsc --noEmit)
make demo         # Print demo URLs and credentials
make ps           # Show service health status
make clean        # Remove Docker build cache
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Browser                              │
│                   localhost:3002 (Next.js)                  │
└────────────────────┬────────────────────────────────────────┘
                     │ REST + WebSocket
┌────────────────────▼────────────────────────────────────────┐
│              Hub API (FastAPI)  :8003                        │
│   Auth · RBAC · Proposals · Approvals · AI · Agents         │
│   /api/health  /api/ready  /metrics                         │
└──┬──────────┬────────────┬──────────────┬───────────────────┘
   │          │            │              │
┌──▼──┐  ┌───▼───┐  ┌─────▼──────┐  ┌───▼───────────┐
│ PG  │  │ Redis │  │  Temporal  │  │    Jaeger      │
│5432 │  │ 6379  │  │  :7233     │  │ :16686/:4318   │
└─────┘  └───────┘  └─────┬──────┘  └───────────────┘
                           │ schedules / signals
                    ┌──────▼──────┐
                    │  temporal-  │
                    │   worker    │
                    │  :8004/hlth │
                    └─────────────┘
```

### Key middleware chain (outermost → innermost)

```
CorrelationId → TenantContext → RequestTimeout → RequestSize → SecurityHeaders → CORS → Route
```

### Circuit breakers

External AI provider calls (Anthropic, OpenAI, Groq) and Temporal client calls are wrapped by `core.circuit_breaker`. They open after 5 consecutive failures and self-heal after 60 seconds (Temporal: 3 failures / 30s). Circuit breaker states appear in `/api/health` under `circuit_breakers`.

### Event bus + dead-letter queue

Redis pub/sub is used for real-time events to the dashboard. On Redis publish failure the event is persisted to a PostgreSQL `dead_letter_events` table and retried with exponential backoff (1 → 5 → 15 → 60 → 240 minutes). Retry is triggered on the next successful startup via lifespan.

---

## Development Workflow

### Frontend hot-reload (without Docker)
```bash
cd apps/hub-dashboard
npm install
npm run dev        # → http://localhost:3002
```

### Backend hot-reload (without Docker)
```bash
cd apps/hub-api
pip install -r requirements.txt
uvicorn main:app --reload --port 8003
```

### Temporal worker (without Docker)
```bash
cd apps/hub-api
python -m temporal.worker   # health endpoint on :8004
```

### Seed fresh data
```bash
# Against running Docker stack:
make seed

# Against local Python env:
cd apps/hub-api
python -m seed.enterprise
```

---

## Tests

### Unit + integration
```bash
make test           # backend pytest + frontend vitest
make test-api       # backend only
make test-dash      # frontend only
make typecheck      # tsc --noEmit
```

### E2E (Playwright)
```bash
cd apps/hub-dashboard
npx playwright install --with-deps
npx playwright test               # all suites
npx playwright test tests/e2e/auth.spec.ts
npx playwright test tests/e2e/proposal-lifecycle.spec.ts
npx playwright test tests/e2e/api-health.spec.ts
npx playwright show-report        # browse test results
```

E2E tests require the full Docker stack running (`make up-build`).

### Load tests (Locust)
```bash
pip install locust
# Interactive UI mode:
locust -f load_tests/locustfile.py --host http://localhost:8003
# Headless 60-second run with 50 users:
locust -f load_tests/locustfile.py --host http://localhost:8003 \
       --users 50 --spawn-rate 5 --run-time 60s --headless
```

Three user profiles: `ApiUser` (health/metrics, unauthenticated), `AuthenticatedUser` (full journey, weight 4), `HeavyUser` (2 req/s constant throughput).

---

## Environment Validation

```bash
# Development (default)
cd apps/hub-api
python -m scripts.validate_env

# Staging / production check (blocks on missing required vars)
python -m scripts.validate_env --env production

# Print export commands to fix missing vars
python -m scripts.validate_env --fix
```

Exit codes: `0` all pass · `1` warnings · `2` errors (blocks production deploy).

---

## pgAdmin (Optional)

Start with the `admin` profile:
```bash
docker compose -f docker-compose.full.yml --profile admin up -d pgadmin
```

Open http://localhost:5050 and add server:
- Host: `postgres`
- Port: `5432`
- Database: `presales_hub`
- Username: `presales`
- Password: `presales_dev`

---

## Resetting Demo Data

```bash
make reset    # tears down all volumes, rebuilds, re-seeds
```

To re-seed without wiping volumes:
```bash
make seed
```

---

## DB Migrations

```bash
cd apps/hub-api

# Apply all pending migrations
alembic upgrade head

# Check current revision
alembic current

# Show pending migrations
alembic history --verbose

# Create a new migration
alembic revision --autogenerate -m "describe_change"
```

---

## Security Features (local dev awareness)

| Feature | Implementation |
|---------|---------------|
| Security headers | `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, CSP, HSTS |
| Rate limiting | `/auth/login` → 20 req/min (slowapi) |
| Account lockout | 5 failed logins → locked 15 minutes |
| Request size limit | Bodies > 10 MB rejected with 413 |
| Request timeout | 30s default · 120s AI/copilot prefixes · **180s** `generate-docx` (`TimeoutAPIRoute`) · 0 WebSocket |
| CORS | Configurable `ALLOWED_ORIGINS` (wildcard in dev) |

---

## Production Deployment

See [`PRODUCTION.md`](PRODUCTION.md) for the full production deployment guide covering nginx, blue/green deploys, Kubernetes, AWS ECS/Fargate, CI/CD pipelines, environment variables, and secrets management.
