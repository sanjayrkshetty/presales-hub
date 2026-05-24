# Blue/Green Deployment — Presales Hub

Zero-downtime deploy strategy using two identical environments (blue/green) behind a load balancer.

## Concept

```
                    ┌─────────────┐
  Users ─→ nginx ─→ │  blue (live) │  ← 100% traffic
                    └─────────────┘
                    ┌─────────────┐
                    │ green (idle) │  ← deploy here
                    └─────────────┘
```

Flip traffic once green passes health checks. Blue becomes idle for instant rollback.

---

## Prerequisites

- Production server with nginx
- Two sets of Docker networks: `hub-blue` and `hub-green`
- Shared PostgreSQL and Redis (external, not in blue/green)
- REGISTRY and IMAGE_TAG env vars set

---

## Step-by-Step Deploy

### 1. Build and push new images

```bash
export IMAGE_TAG=sha-$(git rev-parse --short HEAD)
docker build -t $REGISTRY/presales-hub-api:$IMAGE_TAG ./apps/hub-api
docker build -t $REGISTRY/presales-hub-worker:$IMAGE_TAG ./apps/hub-api -f apps/hub-api/Dockerfile.worker
docker build -t $REGISTRY/presales-hub-dashboard:$IMAGE_TAG ./apps/hub-dashboard
docker push $REGISTRY/presales-hub-api:$IMAGE_TAG
docker push $REGISTRY/presales-hub-worker:$IMAGE_TAG
docker push $REGISTRY/presales-hub-dashboard:$IMAGE_TAG
```

### 2. Start green environment

```bash
export SLOT=green
export IMAGE_TAG=sha-<new-sha>

docker compose -f deployment/docker/docker-compose.prod.yml \
  --project-name presales-hub-green \
  up -d --build
```

### 3. Run DB migrations on green

```bash
docker compose -p presales-hub-green exec hub-api alembic upgrade head
```

### 4. Health-check green before flipping traffic

```bash
# Replace with your green internal port/hostname
until curl -sf http://localhost:8103/api/health | grep -q '"status":"ok"'; do
  echo "Waiting for green to be healthy…"
  sleep 3
done
echo "Green is healthy — flipping traffic"
```

### 5. Flip nginx to green

Edit `/etc/nginx/conf.d/presales.conf`:

```nginx
upstream hub_api {
    # server blue-api:8003;   ← comment out blue
    server green-api:8003;    # ← activate green
}
upstream hub_dashboard {
    # server blue-dashboard:3002;
    server green-dashboard:3002;
}
```

```bash
nginx -t && systemctl reload nginx
```

### 6. Verify production traffic on green

```bash
curl -s https://yourdomain.com/api/health | jq .status
```

### 7. Stop blue (keep for 15 min for instant rollback)

```bash
# Wait 15 minutes, then:
docker compose -p presales-hub-blue down
```

---

## Rollback

```bash
# Flip nginx back to blue
# Edit nginx.conf: uncomment blue, comment green
nginx -t && systemctl reload nginx

# Stop green
docker compose -p presales-hub-green down
```

---

## Environment Variables

| Variable      | Description                             |
|---------------|-----------------------------------------|
| `REGISTRY`    | Container registry (e.g., ghcr.io/org) |
| `IMAGE_TAG`   | Git SHA or semantic version             |
| `SLOT`        | `blue` or `green`                       |
| `PUBLIC_API_URL` | External API URL for dashboard      |

---

## Health Check Validation Script

```bash
#!/usr/bin/env bash
SLOT=${1:-green}
PORT=${2:-8103}
MAX_WAIT=120
ELAPSED=0

while true; do
  STATUS=$(curl -sf "http://localhost:${PORT}/api/health" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['status'])" 2>/dev/null || echo "error")
  if [[ "$STATUS" == "ok" || "$STATUS" == "degraded" ]]; then
    echo "$SLOT is healthy (status=$STATUS) — ready for traffic"
    exit 0
  fi
  if [[ $ELAPSED -ge $MAX_WAIT ]]; then
    echo "Timed out waiting for $SLOT health after ${MAX_WAIT}s — aborting deploy"
    exit 1
  fi
  sleep 5; ((ELAPSED+=5))
  echo "Waiting… ${ELAPSED}s (status=$STATUS)"
done
```
