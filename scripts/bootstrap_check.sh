#!/usr/bin/env bash
# bootstrap_check.sh — One-command local environment validation
# Run before make up-build to catch problems early.
#
# Usage:
#   bash scripts/bootstrap_check.sh
#   bash scripts/bootstrap_check.sh --fix   # auto-fix what's possible

set -euo pipefail

GREEN='\033[32m'; YELLOW='\033[33m'; RED='\033[31m'; RESET='\033[0m'; BOLD='\033[1m'
OK="${GREEN}✓${RESET}"; WARN="${YELLOW}⚠${RESET}"; FAIL="${RED}✗${RESET}"

ERRORS=0; WARNINGS=0

pass()  { echo -e "  ${OK}  $1"; }
warn()  { echo -e "  ${WARN}  $1"; ((WARNINGS++)) || true; }
fail()  { echo -e "  ${FAIL}  $1"; ((ERRORS++)) || true; }

echo -e "\n${BOLD}Presales Hub — Bootstrap Check${RESET}\n"

# ── Tool dependencies ─────────────────────────────────────────────────────────
echo -e "${BOLD}Tools${RESET}"
for tool in docker "docker compose" python3 node npm make; do
  cmd="${tool%% *}"
  if command -v "$cmd" &>/dev/null; then
    pass "$tool ($(${cmd} --version 2>&1 | head -1))"
  else
    fail "$tool not found"
  fi
done

# Docker daemon running?
if docker info &>/dev/null 2>&1; then
  pass "Docker daemon running"
else
  fail "Docker daemon not running — start Docker Desktop"
fi

# ── Env file ──────────────────────────────────────────────────────────────────
echo -e "\n${BOLD}Configuration${RESET}"

if [[ -f ".env.full.example" ]]; then
  pass ".env.full.example exists"
else
  fail ".env.full.example missing"
fi

# Check critical vars in env file
for var in POSTGRES_PASSWORD REDIS_URL JWT_SECRET_KEY; do
  if grep -q "^${var}=" .env.full.example 2>/dev/null; then
    pass "$var defined in .env.full.example"
  else
    warn "$var not found in .env.full.example"
  fi
done

# ── Port availability ─────────────────────────────────────────────────────────
echo -e "\n${BOLD}Port Availability${RESET}"
PORTS=(5432 6379 7233 8003 8004 3002 16686 8080)
for port in "${PORTS[@]}"; do
  if ! lsof -i ":${port}" &>/dev/null 2>&1; then
    pass "Port $port available"
  else
    warn "Port $port in use — may conflict with stack"
  fi
done

# ── Disk space ────────────────────────────────────────────────────────────────
echo -e "\n${BOLD}Resources${RESET}"
FREE_GB=$(df -BG . 2>/dev/null | awk 'NR==2 {print $4}' | tr -d 'G' || echo 999)
if [[ "${FREE_GB:-0}" -ge 5 ]]; then
  pass "Disk space: ${FREE_GB}GB free"
else
  warn "Low disk space: ${FREE_GB}GB (recommend ≥5GB for Docker images)"
fi

# ── Python deps ───────────────────────────────────────────────────────────────
echo -e "\n${BOLD}Python Dependencies${RESET}"
if [[ -f "apps/hub-api/requirements.txt" ]]; then
  MISSING=$(pip show slowapi prometheus-client temporalio 2>&1 | grep "WARNING" | wc -l || echo 0)
  if [[ "$MISSING" -eq 0 ]]; then
    pass "Key Python packages installed"
  else
    warn "$MISSING key packages not installed (run: pip install -r apps/hub-api/requirements.txt)"
  fi
fi

# ── Node deps ─────────────────────────────────────────────────────────────────
echo -e "\n${BOLD}Node Dependencies${RESET}"
if [[ -d "apps/hub-dashboard/node_modules" ]]; then
  pass "node_modules exists"
else
  warn "node_modules missing — run: cd apps/hub-dashboard && npm install"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
if [[ $ERRORS -gt 0 ]]; then
  echo -e "${RED}${BOLD}  $ERRORS error(s) — fix before running make up-build${RESET}"
  exit 2
elif [[ $WARNINGS -gt 0 ]]; then
  echo -e "${YELLOW}  $WARNINGS warning(s) — review, then run: make up-build${RESET}"
  exit 1
else
  echo -e "${GREEN}${BOLD}  All checks passed — run: make up-build${RESET}"
  exit 0
fi
