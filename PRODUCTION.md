# Presales Hub — Production Deployment Guide

> Zero-downtime, production-grade deployment for the Presales Hub platform.

---

## Table of Contents

1. [Environment Variables](#environment-variables)
2. [Pre-Deploy Checklist](#pre-deploy-checklist)
3. [Database Migrations](#database-migrations)
4. [Docker Compose (Single Server)](#docker-compose-single-server)
5. [Blue/Green Deploy (Zero Downtime)](#bluegreen-deploy-zero-downtime)
6. [Kubernetes](#kubernetes)
7. [AWS ECS / Fargate](#aws-ecs--fargate)
8. [CI/CD Pipelines](#cicd-pipelines)
9. [nginx Configuration](#nginx-configuration)
10. [Observability](#observability)
11. [Secrets Management](#secrets-management)
12. [Rollback Procedure](#rollback-procedure)
13. [Known Gaps / Roadmap](#known-gaps--roadmap)

---

## Environment Variables

### Required — all environments

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL DSN | `postgresql://user:pass@host:5432/presales_hub` |
| `REDIS_URL` | Redis DSN | `redis://:password@host:6379` |
| `TEMPORAL_HOST` | Temporal gRPC address | `temporal:7233` |
| `JWT_SECRET_KEY` | HMAC signing key (64+ random bytes) | `openssl rand -hex 64` |
| `PLATFORM_ADMIN_KEY` | Admin API key (never use `dev-admin-key`) | `openssl rand -hex 32` |
| `ENVIRONMENT` | Runtime environment | `production` |

### Required — production only

| Variable | Description |
|----------|-------------|
| `SENTRY_DSN` | Sentry error tracking DSN |
| `ALLOWED_ORIGINS` | Comma-separated frontend origins (no wildcard) |
| `DEBUG` | Must be `false` |

### Optional AI providers (at least one recommended)

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Claude API key |
| `OPENAI_API_KEY` | OpenAI API key |
| `GROQ_API_KEY` | Groq API key |

### Optional observability

| Variable | Description | Default |
|----------|-------------|---------|
| `OTLP_ENDPOINT` | OpenTelemetry collector endpoint | `""` (disabled) |
| `REGISTRY` | Container registry prefix | — |
| `IMAGE_TAG` | Git SHA or semver tag | — |
| `SLOT` | Blue/green slot identifier (`blue`/`green`) | — |
| `PUBLIC_API_URL` | External API URL seen by dashboard | — |

### Validate before every deploy

```bash
cd apps/hub-api
python -m scripts.validate_env --env production
# Exit 0 = all pass. Exit 2 = blocking errors — do not deploy.
```

The startup validator (`core/config.py`) will also refuse to start if:
- `DATABASE_URL` points to SQLite
- `DEBUG=true`
- `PLATFORM_ADMIN_KEY` equals `dev-admin-key`

---

## Pre-Deploy Checklist

```
[ ] python -m scripts.validate_env --env production   → exit 0
[ ] alembic upgrade head                               → no errors
[ ] All CI checks green (pytest, tsc, vitest, build)
[ ] IMAGE_TAG set to git SHA (not `latest`)
[ ] SENTRY_DSN configured
[ ] ALLOWED_ORIGINS set to exact frontend domain
[ ] JWT_SECRET_KEY rotated from dev default
[ ] PLATFORM_ADMIN_KEY rotated from dev default
[ ] nginx config tested (nginx -t)
[ ] Backup taken before schema migrations
```

---

## Database Migrations

Alembic manages all schema changes. Never run `Base.metadata.create_all()` against production directly.

```bash
# Check current revision on production DB
DATABASE_URL=<prod-dsn> alembic current

# Apply all pending migrations
DATABASE_URL=<prod-dsn> alembic upgrade head

# Preview SQL without applying
DATABASE_URL=<prod-dsn> alembic upgrade head --sql

# Emergency rollback one revision
DATABASE_URL=<prod-dsn> alembic downgrade -1
```

### Migration notes from this build

| Revision | Description | Backwards-compatible |
|----------|-------------|----------------------|
| `h4i5j6k7l8m9` | Adds `failed_login_count` (int, default 0) and `locked_until` (timestamp, nullable) to `users` | Yes — new nullable columns |
| `dead_letter_events` | Auto-created by lifespan on first start | Yes — new table |

---

## Docker Compose (Single Server)

```bash
export REGISTRY=ghcr.io/your-org
export IMAGE_TAG=sha-$(git rev-parse --short HEAD)

# Pull new images
docker compose -f deployment/docker/docker-compose.prod.yml pull

# Apply migrations
docker compose -f deployment/docker/docker-compose.prod.yml \
  run --rm hub-api alembic upgrade head

# Rolling restart (brief downtime)
docker compose -f deployment/docker/docker-compose.prod.yml \
  up -d --remove-orphans
```

Production compose (`deployment/docker/docker-compose.prod.yml`) features:
- `restart: always` on all services
- CPU/memory resource limits
- Redis with password authentication
- 2 replicas for `hub-api`
- nginx reverse proxy with SSL termination

---

## Blue/Green Deploy (Zero Downtime)

Full step-by-step guide: [`deployment/docker/blue-green.md`](deployment/docker/blue-green.md)

### Quick reference

```bash
# 1. Build and push
export IMAGE_TAG=sha-$(git rev-parse --short HEAD)
docker build -t $REGISTRY/presales-hub-api:$IMAGE_TAG ./apps/hub-api
docker push $REGISTRY/presales-hub-api:$IMAGE_TAG
# ... repeat for worker and dashboard

# 2. Start green slot
export SLOT=green
docker compose -f deployment/docker/docker-compose.prod.yml \
  --project-name presales-hub-green up -d

# 3. Migrate on green
docker compose -p presales-hub-green exec hub-api alembic upgrade head

# 4. Health-check green (waits up to 120s)
bash deployment/docker/blue-green.md   # see embedded health-check script

# 5. Flip nginx to green
# Edit /etc/nginx/conf.d/presales.conf → comment blue, uncomment green
nginx -t && systemctl reload nginx

# 6. Stop blue (after 15 min)
docker compose -p presales-hub-blue down
```

### Rollback (< 30 seconds)

```bash
# Flip nginx back to blue
nginx -t && systemctl reload nginx
docker compose -p presales-hub-green down
```

---

## Kubernetes

Manifests are in `deployment/kubernetes/`. Apply in order:

```bash
kubectl apply -f deployment/kubernetes/namespace.yaml
kubectl apply -f deployment/kubernetes/configmap.yaml

# Fill in secrets.yaml.template with base64-encoded values, then:
kubectl apply -f deployment/kubernetes/secrets.yaml

kubectl apply -f deployment/kubernetes/postgres-statefulset.yaml
kubectl apply -f deployment/kubernetes/redis-deployment.yaml
kubectl apply -f deployment/kubernetes/api-deployment.yaml
kubectl apply -f deployment/kubernetes/worker-deployment.yaml
kubectl apply -f deployment/kubernetes/dashboard-deployment.yaml
kubectl apply -f deployment/kubernetes/ingress.yaml
```

Key configuration:
- API deployment has readiness (`/api/ready`) and liveness (`/api/health`) probes
- Worker deployment health checks against `:8004/health`
- PostgreSQL uses a 20Gi PVC (StatefulSet)
- Ingress uses cert-manager annotations for automatic TLS

### Rolling update

```bash
kubectl set image deployment/hub-api \
  hub-api=$REGISTRY/presales-hub-api:$IMAGE_TAG \
  -n presales-hub

kubectl rollout status deployment/hub-api -n presales-hub
```

---

## AWS ECS / Fargate

Task definition: `deployment/aws/ecs-task-definition.json`

- API and Worker containers are co-scheduled in the same task
- Secrets (`DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`) pulled from AWS Secrets Manager
- Logs shipped to CloudWatch (`/ecs/presales-hub-api`)
- Fargate CPU: 512 / Memory: 1024 per task

```bash
# Register new task definition revision
aws ecs register-task-definition \
  --cli-input-json file://deployment/aws/ecs-task-definition.json

# Update service to new revision
aws ecs update-service \
  --cluster presales-hub \
  --service hub-api \
  --task-definition presales-hub:$REVISION \
  --force-new-deployment
```

---

## CI/CD Pipelines

Three GitHub Actions workflows:

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `.github/workflows/ci.yml` | Every PR + push | Lint, test, type-check, build |
| `.github/workflows/cd-staging.yml` | Push to `main` | Build images → push → SSH deploy to staging |
| `.github/workflows/cd-production.yml` | Manual `workflow_dispatch` | Deploy to production with GitHub approval gate |

### CI checks

- PostgreSQL 15 + Redis 7 service containers
- `pytest` backend tests
- `tsc --noEmit` type check
- `vitest` frontend tests
- `npm run build` production build

### Production deploy (manual)

1. Go to Actions → `Deploy to Production`
2. Click **Run workflow**
3. Enter `image_tag` (git SHA or semver)
4. Requires approval from the `production` GitHub environment
5. Workflow runs `alembic upgrade head` then restarts services

### Required secrets (GitHub → Settings → Secrets)

```
GHCR_TOKEN          # GitHub container registry write token
PROD_SERVER_HOST    # Production server IP / hostname
PROD_SERVER_USER    # SSH user
PROD_SSH_KEY        # SSH private key
REGISTRY            # e.g. ghcr.io/your-org
```

---

## nginx Configuration

Config: `deployment/nginx/nginx.conf`

Key settings:
- TLS 1.2 / 1.3 only, strong cipher suite
- `limit_req_zone` — API: 100 req/min, auth: 20 req/min
- `client_max_body_size 10m` (matches RequestSizeMiddleware)
- WebSocket upgrade at `/ws/`
- HSTS 1 year with `includeSubDomains`

```bash
# Test config before reload
nginx -t

# Zero-downtime reload
systemctl reload nginx
# or
nginx -s reload
```

---

## Observability

### Health endpoints

| Endpoint | Returns | Use |
|----------|---------|-----|
| `GET /api/health` | JSON with status, checks, circuit_breakers, latency_ms | Load balancer health check |
| `GET /api/ready` | 200/503 | Kubernetes readiness probe |
| `GET /metrics` | Prometheus text format | Prometheus scrape |

### Prometheus metrics

| Metric | Type | Labels |
|--------|------|--------|
| `hub_http_requests_total` | Counter | method, path, status |
| `hub_http_request_duration_seconds` | Histogram | method, path |
| `hub_ws_connections_active` | Gauge | — |
| `hub_event_publishes_total` | Counter | channel, status |
| `hub_dlq_events_pending` | Gauge | — |
| `hub_circuit_breaker_open` | Gauge | name |

### Sentry

Set `SENTRY_DSN` to enable. Errors in backend API are captured automatically. Frontend Sentry integration is a known gap (see below).

### Distributed tracing

Set `OTLP_ENDPOINT` to your collector (e.g., `http://jaeger:4318/v1/traces`). Correlation IDs are injected by `CorrelationIdMiddleware` into every response as `X-Correlation-ID` and into structured logs.

---

## Secrets Management

### What to never commit

- `.env.full` (local dev env with real credentials)
- `deployment/kubernetes/secrets.yaml` (only commit the `.template` version)
- Any file containing `JWT_SECRET_KEY`, `PLATFORM_ADMIN_KEY`, `ANTHROPIC_API_KEY`, or database passwords

### Recommended secret stores

| Platform | Tool |
|----------|------|
| AWS | Secrets Manager — referenced in ECS task definition |
| Kubernetes | `kubectl create secret generic` + reference via `secretKeyRef` |
| GitHub Actions | GitHub Encrypted Secrets |
| Self-hosted | HashiCorp Vault or `sops`-encrypted `.env` files |

### Key rotation

```bash
# Rotate JWT_SECRET_KEY — invalidates all active sessions
openssl rand -hex 64

# Rotate PLATFORM_ADMIN_KEY
openssl rand -hex 32
```

---

## Rollback Procedure

### Docker Compose

```bash
# Set IMAGE_TAG to the previous known-good SHA
export IMAGE_TAG=sha-<previous>
docker compose -f deployment/docker/docker-compose.prod.yml up -d
```

### Blue/Green

```bash
# Flip nginx back to the idle slot (blue if green is live)
# Edit /etc/nginx/conf.d/presales.conf
nginx -t && systemctl reload nginx
docker compose -p presales-hub-green down
```

### DB rollback

```bash
# One revision back
DATABASE_URL=<prod-dsn> alembic downgrade -1

# To a specific revision
DATABASE_URL=<prod-dsn> alembic downgrade <revision-id>
```

Migrations `h4i5j6k7l8m9` (user lockout columns) are additive and safe to downgrade — the columns are dropped, existing user data is unaffected.

---

## Known Gaps / Roadmap

These are items not yet implemented that matter for a full production hardening:

### Security & Auth
- [ ] Sentry SDK not yet wired into frontend `ErrorBoundary` or backend startup
- [ ] Frontend OpenTelemetry browser instrumentation
- [ ] Distributed trace correlation IDs not yet surfaced in dashboard UI

### Observability
- [ ] Grafana dashboard JSON export files (metric dashboards are configured but not exported)
- [ ] WebSocket connection metrics visualization in UI (metric exists, no dashboard panel)
- [ ] Service health scoring dashboard (aggregate score across all circuit breakers)
- [ ] AI token usage histograms in dashboard

### Testing
- [ ] Chaos testing mode for Redis/API failures
- [ ] API contract validation (schema-level, e.g., Schemathesis)
- [ ] Snapshot tests for critical dashboard views
- [ ] Temporal workflow integration tests (against real Temporal server)
- [ ] Docker smoke-test in CI pipeline

### Commercialization
- [ ] Tenant onboarding wizard (first-run setup flow)
- [ ] License / plan enforcement UI
- [ ] API key management UI
- [ ] Webhook management UI
- [ ] Usage analytics dashboards per tenant
- [ ] White-label branding support
- [ ] Exportable executive reports (PDF-ready)

### Infrastructure
- [ ] Backup and restore scripts (pg_dump / pg_restore automation)
- [ ] Disaster recovery runbook
- [ ] Terraform starter templates (currently only K8s YAML + ECS JSON)
- [ ] Auto DB migration gate in Docker Compose (currently manual step in blue/green and CD)

---

## Exact Commands — Local to Production

### Run locally
```bash
bash scripts/bootstrap_check.sh     # pre-flight
make up-build                        # full stack
make test                            # all tests
```

### Validate production readiness
```bash
cd apps/hub-api
python -m scripts.validate_env --env production
```

### Deploy to production (Docker, manual)
```bash
export REGISTRY=ghcr.io/your-org
export IMAGE_TAG=sha-$(git rev-parse --short HEAD)

docker build -t $REGISTRY/presales-hub-api:$IMAGE_TAG ./apps/hub-api
docker build -t $REGISTRY/presales-hub-worker:$IMAGE_TAG ./apps/hub-api -f apps/hub-api/Dockerfile.worker
docker build -t $REGISTRY/presales-hub-dashboard:$IMAGE_TAG ./apps/hub-dashboard

docker push $REGISTRY/presales-hub-api:$IMAGE_TAG
docker push $REGISTRY/presales-hub-worker:$IMAGE_TAG
docker push $REGISTRY/presales-hub-dashboard:$IMAGE_TAG

# On production server:
DATABASE_URL=<prod-dsn> alembic upgrade head
docker compose -f deployment/docker/docker-compose.prod.yml up -d --remove-orphans
```

### Deploy via GitHub Actions (recommended)
1. Merge to `main` → staging deploy triggers automatically
2. Verify on staging
3. Actions → Deploy to Production → Run workflow → enter `image_tag`
