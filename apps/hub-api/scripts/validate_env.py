#!/usr/bin/env python3
"""
Environment validation CLI for Presales Hub.

Usage:
    python -m scripts.validate_env                    # validate current .env
    python -m scripts.validate_env --env production   # strict production checks
    python -m scripts.validate_env --fix              # print export commands to fix issues

Exit codes:
    0 — all checks pass
    1 — warnings (non-blocking)
    2 — errors (blocking for production)
"""
import os
import sys
import argparse
import socket
from typing import NamedTuple

GREEN  = "\033[32m"
YELLOW = "\033[33m"
RED    = "\033[31m"
RESET  = "\033[0m"
BOLD   = "\033[1m"


class Check(NamedTuple):
    name: str
    ok: bool
    message: str
    severity: str  # "ok" | "warn" | "error"


def check_var(name: str, required_in_prod: bool = False, not_default: str | None = None) -> Check:
    val = os.getenv(name, "")
    if not val:
        sev = "error" if required_in_prod else "warn"
        return Check(name, False, f"Not set (default will be used)", sev)
    if not_default and val == not_default:
        return Check(name, False, f"Using insecure default '{not_default}'", "error")
    return Check(name, True, f"Set ({val[:20]}{'…' if len(val) > 20 else ''})", "ok")


def check_db_reachable(url: str) -> Check:
    if url.startswith("sqlite://"):
        return Check("DATABASE_URL", True, "SQLite (dev only)", "warn")
    try:
        from urllib.parse import urlparse
        p = urlparse(url)
        sock = socket.create_connection((p.hostname, p.port or 5432), timeout=3)
        sock.close()
        return Check("DB connectivity", True, f"{p.hostname}:{p.port or 5432} reachable", "ok")
    except Exception as e:
        return Check("DB connectivity", False, f"Cannot reach DB: {e}", "error")


def check_redis_reachable(url: str) -> Check:
    try:
        from urllib.parse import urlparse
        p = urlparse(url)
        sock = socket.create_connection((p.hostname or "localhost", p.port or 6379), timeout=3)
        sock.close()
        return Check("Redis connectivity", True, f"{p.hostname}:{p.port or 6379} reachable", "ok")
    except Exception as e:
        return Check("Redis connectivity", False, f"Cannot reach Redis: {e}", "warn")


def check_temporal_reachable(host: str) -> Check:
    try:
        h, _, p = host.partition(":")
        sock = socket.create_connection((h, int(p) if p else 7233), timeout=3)
        sock.close()
        return Check("Temporal connectivity", True, f"{host} reachable", "ok")
    except Exception as e:
        return Check("Temporal connectivity", False, f"Cannot reach Temporal: {e}", "warn")


def run_checks(env: str) -> list[Check]:
    checks: list[Check] = []
    is_prod = env == "production"

    # Required env vars
    checks.append(check_var("DATABASE_URL",        required_in_prod=True))
    checks.append(check_var("REDIS_URL",            required_in_prod=True))
    checks.append(check_var("TEMPORAL_HOST",        required_in_prod=True))
    checks.append(check_var("JWT_SECRET_KEY",       required_in_prod=True))
    checks.append(check_var("PLATFORM_ADMIN_KEY",   required_in_prod=is_prod, not_default="dev-admin-key"))

    # Optional AI keys
    checks.append(check_var("ANTHROPIC_API_KEY",    required_in_prod=False))
    checks.append(check_var("OPENAI_API_KEY",       required_in_prod=False))

    # Production-specific
    if is_prod:
        db_url = os.getenv("DATABASE_URL", "sqlite:///")
        if db_url.startswith("sqlite://"):
            checks.append(Check("DATABASE_URL", False, "SQLite not allowed in production", "error"))
        debug = os.getenv("DEBUG", "true").lower()
        if debug in ("1", "true", "yes"):
            checks.append(Check("DEBUG", False, "DEBUG must be False in production", "error"))
        sentry = os.getenv("SENTRY_DSN", "")
        if not sentry:
            checks.append(Check("SENTRY_DSN", False, "Not set — errors won't be tracked in production", "warn"))

    # Connectivity checks
    db_url  = os.getenv("DATABASE_URL",  "sqlite:///./presales_hub.db")
    redis   = os.getenv("REDIS_URL",     "redis://localhost:6379")
    temporal = os.getenv("TEMPORAL_HOST","localhost:7233")

    checks.append(check_db_reachable(db_url))
    checks.append(check_redis_reachable(redis))
    checks.append(check_temporal_reachable(temporal))

    return checks


def print_results(checks: list[Check]) -> int:
    errors = warnings = 0
    print(f"\n{BOLD}Presales Hub — Environment Validation{RESET}\n")

    for c in checks:
        if c.severity == "ok":
            icon = f"{GREEN}✓{RESET}"
        elif c.severity == "warn":
            icon = f"{YELLOW}⚠{RESET}"
            warnings += 1
        else:
            icon = f"{RED}✗{RESET}"
            errors += 1
        print(f"  {icon}  {c.name:<30} {c.message}")

    print()
    if errors:
        print(f"{RED}{BOLD}  {errors} error(s) must be fixed before production deploy.{RESET}")
        return 2
    if warnings:
        print(f"{YELLOW}  {warnings} warning(s) — review before deploying.{RESET}")
        return 1
    print(f"{GREEN}{BOLD}  All checks passed.{RESET}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Validate Presales Hub environment configuration")
    parser.add_argument("--env", default=os.getenv("ENVIRONMENT", "development"),
                        choices=["development", "staging", "production"])
    parser.add_argument("--fix", action="store_true", help="Print export commands to fix missing vars")
    args = parser.parse_args()

    if args.env:
        os.environ.setdefault("ENVIRONMENT", args.env)

    # Load .env if present
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    checks = run_checks(args.env)
    exit_code = print_results(checks)

    if args.fix:
        print(f"\n{BOLD}Suggested exports to fix missing vars:{RESET}")
        missing = [c.name for c in checks if not c.ok and "connectivity" not in c.name.lower()]
        for name in missing:
            print(f"  export {name}=<value>")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
