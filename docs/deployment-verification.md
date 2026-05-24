# Deployment Verification

**Date:** 2026-05-24  
**Scripts:** `scripts/preflight_check.py`, `scripts/post_deploy_verify.py`

---

## Pre-Deploy Checklist

Run before every deployment:

```bash
python scripts/preflight_check.py
```

### What It Checks

| Check | Pass condition | Fail condition |
|-------|----------------|----------------|
| Python version | ≥ 3.11 | < 3.11 |
| Node.js version | ≥ 18.0 | < 18.0 or not found |
| Docker daemon | Responding to `docker info` | Not running |
| Docker Compose v2 | `docker compose version` succeeds | v1 compose or missing |
| Disk space | ≥ 5 GB free | < 5 GB |
| `.env` file | Exists in project root | Missing |
| Required env vars | `SECRET_KEY`, `DATABASE_URL`, `ALLOWED_ORIGINS` set and non-empty | Missing or empty |
| Port availability | Ports 8003, 3002, 5432, 6379, 7233 not in use | Any port occupied (warn) |

**Exit codes:** 0 = all pass, 1 = warnings, 2 = failures (do not deploy on 2)

**CI usage:**

```bash
python scripts/preflight_check.py --json | tee preflight.json
# Fail pipeline on exit code 2:
python scripts/preflight_check.py --json; if [ $? -eq 2 ]; then exit 1; fi
```

---

## Database Migration State

Before deploying, verify migrations are current:

```bash
# Check current migration head
docker compose run --rm hub-api alembic current

# Apply any pending migrations
docker compose run --rm hub-api alembic upgrade head

# Verify (should show "(head)")
docker compose run --rm hub-api alembic current
```

**Never deploy with pending migrations in production.** Run migrations before traffic cutover in blue/green.

---

## Deployment Steps (Docker Compose)

### Fresh deploy

```bash
# 1. Pre-flight
python scripts/preflight_check.py
# (exit code must be 0 or 1)

# 2. Pull/build
make up-build

# 3. Wait for startup (~20s)
sleep 20

# 4. Post-deploy verify
python scripts/post_deploy_verify.py
```

### Update deploy (no data loss)

```bash
# 1. Pull new images (or build from source)
docker compose -f docker-compose.full.yml build hub-api hub-dashboard

# 2. Rolling restart — API first, then dashboard
docker compose -f docker-compose.full.yml up -d --no-deps hub-api
sleep 10
docker compose -f docker-compose.full.yml up -d --no-deps hub-dashboard

# 3. Verify
python scripts/post_deploy_verify.py
```

---

## Post-Deploy Verification

Run immediately after deployment:

```bash
python scripts/post_deploy_verify.py
python scripts/post_deploy_verify.py --host https://api.presaleshub.io  # production
```

### Checks Performed

| Check | Expected | Failure means |
|-------|----------|---------------|
| `GET /api/health` | `status: ok` or `degraded` | API not started / DB issue |
| `GET /metrics` | HTTP 200, non-empty body | Prometheus exporter broken |
| `POST /auth/login` (demo user) | HTTP 200 + access_token | Auth broken / DB not seeded |
| `GET /api/analytics/pipeline` | HTTP 200 | Analytics router error |
| `GET /api/analytics/sla` | HTTP 200 | SLA aggregation error |
| WebSocket `/ws/activity` | Connect + message within 5s | WS auth broken / broadcaster down |
| 21× bad login → 429 | 429 appears in status list | Rate limiter not working |
| 11 MB body POST | HTTP 413 | Request size middleware not applied |

**Exit code:** 0 = all pass, 1 = any fail

---

## Rolling Restart (Kubernetes)

```bash
# Applies to K8s deployment (manifests in deployment/)
kubectl rollout restart deployment/hub-api -n presales-hub
kubectl rollout status deployment/hub-api -n presales-hub --timeout=120s

# Verify
kubectl get pods -n presales-hub
python scripts/post_deploy_verify.py --host https://api.presaleshub.io
```

**Rolling strategy (deployment/k8s/hub-api-deployment.yaml):**
- `maxSurge: 1` — one extra pod during rollout
- `maxUnavailable: 0` — zero downtime

---

## Rollback Procedure

### Docker Compose rollback

```bash
# 1. Tag the known-good image before deploying
docker tag presales-hub-hub-api:latest presales-hub-hub-api:rollback

# 2. If new deploy fails:
docker tag presales-hub-hub-api:rollback presales-hub-hub-api:latest
docker compose -f docker-compose.full.yml up -d --no-deps hub-api
python scripts/post_deploy_verify.py
```

### K8s rollback

```bash
# View rollout history
kubectl rollout history deployment/hub-api -n presales-hub

# Roll back to previous revision
kubectl rollout undo deployment/hub-api -n presales-hub
kubectl rollout status deployment/hub-api -n presales-hub --timeout=60s
```

---

## Backup and Restore (PostgreSQL)

```bash
# Backup
docker compose -f docker-compose.full.yml exec postgres \
  pg_dump -U presales_user presales_hub > backup_$(date +%Y%m%d_%H%M).sql

# Restore
docker compose -f docker-compose.full.yml exec -T postgres \
  psql -U presales_user presales_hub < backup_20260524_1400.sql
```

---

## Common Post-Deploy Failures

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `/api/health` returns 503 with postgres error | DB not ready or migrations pending | Wait 10s, run `alembic upgrade head` |
| Login returns 500 | `SECRET_KEY` not set in env | Check `.env`, restart hub-api |
| WebSocket returns 403 | WS token auth — demo user doesn't exist | Re-seed: `make seed` |
| 413 on large body | `RequestSizeLimitMiddleware` not applied | Check middleware order in `main.py` |
| Rate limit test fails (all 401 not 429) | `LoginRateLimiter` window not reset between test runs | Restart hub-api to reset in-memory state |
