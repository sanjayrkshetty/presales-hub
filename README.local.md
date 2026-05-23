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

---

## Quick Start (5 minutes)

```bash
# 1. Clone and enter the repo
git clone <repo-url>
cd presales-hub

# 2. Copy environment file
cp .env.full.example .env.full

# 3. Start the full stack (builds images, seeds data, opens demo info)
make up-build

# 4. Open the dashboard
open http://localhost:3002
```

Login with the demo credentials printed by `make demo`.

---

## Service URLs

| Service | URL | Purpose |
|---------|-----|---------|
| **Dashboard** | http://localhost:3002 | Main UI |
| **API** | http://localhost:8003 | FastAPI backend |
| **API Docs** | http://localhost:8003/docs | Swagger UI |
| **Temporal UI** | http://localhost:8080 | Workflow inspector |
| **Jaeger** | http://localhost:16686 | Distributed traces |
| **pgAdmin** | http://localhost:5050 | DB browser (opt-in) |

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
make up          # Start all services in background
make up-build    # Rebuild images then start (use after code changes)
make down        # Stop all services (data preserved)
make reset       # Wipe all data volumes and restart fresh
make seed        # Re-run enterprise seed against live stack
make logs        # Tail API + dashboard logs
make logs-api    # Tail backend logs only
make test        # Run full test suite (backend + frontend)
make typecheck   # TypeScript type check
make demo        # Print demo URLs and credentials
make ps          # Show service health status
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
└──┬──────────┬────────────┬──────────────┬───────────────────┘
   │          │            │              │
┌──▼──┐  ┌───▼───┐  ┌─────▼──────┐  ┌───▼───────────┐
│ PG  │  │ Redis │  │  Temporal  │  │    Jaeger      │
│5432 │  │ 6379  │  │  :7233     │  │ :16686/:4318   │
└─────┘  └───────┘  └────────────┘  └───────────────┘
```

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

### Seed fresh data
```bash
# Against running Docker stack:
make seed

# Against local Python env:
cd apps/hub-api
python -m seed.enterprise
```

### Run tests
```bash
make test           # both
make test-api       # backend only
make test-dash      # frontend only
```

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

Or to just re-seed without wiping:
```bash
make seed
```

---

## Production Deployment Notes

See `apps/hub-api/.env.production.example` for all required production variables.

Key differences from local dev:
- Use PostgreSQL instead of SQLite
- Set a strong `JWT_SECRET_KEY` (64+ random bytes)
- Set `ENVIRONMENT=production` (enables HTTPS-only cookies)
- Replace `ALLOWED_ORIGINS` wildcard with specific frontend domain
- Point `OTLP_ENDPOINT` to your observability backend (Datadog, Grafana, etc.)
