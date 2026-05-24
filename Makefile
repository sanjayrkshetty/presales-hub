# Presales Hub — Local Development Makefile
# Usage: make <target>
# Requires: docker, docker compose v2, npm, python 3.11+

COMPOSE      = docker compose -f docker-compose.full.yml
API_DIR      = apps/hub-api
DASH_DIR     = apps/hub-dashboard

.DEFAULT_GOAL := help

.PHONY: help up up-build down reset seed logs logs-api logs-dash \
        logs-worker test test-api test-dash typecheck demo ps clean

# ── Help ──────────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "  Presales Hub — Local Stack Commands"
	@echo ""
	@echo "  make up          Start all services (background)"
	@echo "  make up-build    Rebuild images then start"
	@echo "  make down        Stop all services"
	@echo "  make reset       Wipe volumes and restart fresh (re-seeds data)"
	@echo "  make seed        Re-run enterprise seed against running stack"
	@echo "  make logs        Tail API + dashboard logs"
	@echo "  make logs-api    Tail hub-api logs only"
	@echo "  make logs-dash   Tail hub-dashboard logs only"
	@echo "  make logs-worker Tail temporal-worker logs only"
	@echo "  make test        Run all tests (api + dashboard)"
	@echo "  make test-api    Run backend pytest suite"
	@echo "  make test-dash   Run frontend vitest suite"
	@echo "  make typecheck   Run tsc --noEmit on dashboard"
	@echo "  make demo        Print demo URLs and credentials"
	@echo "  make ps          Show running service status"
	@echo "  make clean       Remove Docker build cache"
	@echo ""

# ── Stack lifecycle ───────────────────────────────────────────────────────────
up:
	$(COMPOSE) up -d
	@$(MAKE) -s demo

up-build:
	$(COMPOSE) up -d --build
	@$(MAKE) -s demo

down:
	$(COMPOSE) down

reset:
	$(COMPOSE) down -v --remove-orphans
	$(COMPOSE) up -d --build
	@echo "Waiting for stack to initialise..."
	@sleep 5
	@$(MAKE) -s demo

seed:
	$(COMPOSE) run --rm hub-seed python -m seed.enterprise

# ── Logs ──────────────────────────────────────────────────────────────────────
logs:
	$(COMPOSE) logs -f hub-api hub-dashboard

logs-api:
	$(COMPOSE) logs -f hub-api

logs-dash:
	$(COMPOSE) logs -f hub-dashboard

logs-worker:
	$(COMPOSE) logs -f temporal-worker

ps:
	$(COMPOSE) ps

# ── Tests ─────────────────────────────────────────────────────────────────────
test: test-api test-dash

test-api:
	cd $(API_DIR) && python -m pytest tests/ -x -q

test-dash:
	cd $(DASH_DIR) && npm test

typecheck:
	cd $(DASH_DIR) && npx tsc --noEmit

# ── Demo ──────────────────────────────────────────────────────────────────────
demo:
	@echo ""
	@echo "  ╔══════════════════════════════════════════════════════╗"
	@echo "  ║           PRESALES HUB — LOCAL DEMO STACK           ║"
	@echo "  ╠══════════════════════════════════════════════════════╣"
	@echo "  ║  Dashboard    →  http://localhost:3002               ║"
	@echo "  ║  API Docs     →  http://localhost:8003/docs          ║"
	@echo "  ║  Temporal UI  →  http://localhost:8080               ║"
	@echo "  ║  Jaeger UI    →  http://localhost:16686              ║"
	@echo "  ║  Worker Health→  http://localhost:8004/health        ║"
	@echo "  ╠══════════════════════════════════════════════════════╣"
	@echo "  ║  Demo login (presales lead):                         ║"
	@echo "  ║    Email:     arjun@sisa.demo                        ║"
	@echo "  ║    Password:  Demo@1234                              ║"
	@echo "  ║  Admin login:                                        ║"
	@echo "  ║    Email:     admin@presaleshub.io                   ║"
	@echo "  ║    Password:  Admin@1234                             ║"
	@echo "  ╚══════════════════════════════════════════════════════╝"
	@echo ""

# ── Maintenance ───────────────────────────────────────────────────────────────
clean:
	docker builder prune -f
	docker image prune -f
