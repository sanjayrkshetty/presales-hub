#!/usr/bin/env python3
"""
Failure scenario: PostgreSQL container restart

Restarts the postgres container and measures:
  1. Time from restart until first failed health check (degradation onset)
  2. Time from restart until postgres health returns to 'ok' (recovery time)
  3. API behavior during outage (should return 503 with 'critical' status)

Usage:
    python scripts/failure_scenarios/postgres_reconnect.py
    python scripts/failure_scenarios/postgres_reconnect.py --host http://10.0.0.1:8003
    python scripts/failure_scenarios/postgres_reconnect.py --wait-timeout 60

Requires: docker CLI accessible, presales-hub compose stack running.
PostgreSQL container name must match docker-compose.full.yml service name.
"""
import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request

POSTGRES_CONTAINER = "presales-hub-postgres-1"
DEFAULT_HOST = "http://localhost:8003"
MAX_WAIT_SECONDS = 60


def _ts() -> str:
    return time.strftime("%H:%M:%S")


def _get_health(host: str) -> tuple[int, dict]:
    try:
        req = urllib.request.Request(f"{host}/api/health")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {}
    except Exception as exc:
        return 0, {"error": str(exc)}


def _docker(cmd: list[str], timeout: int = 30) -> tuple[int, str]:
    result = subprocess.run(
        ["docker"] + cmd,
        capture_output=True, text=True, timeout=timeout,
    )
    return result.returncode, (result.stdout + result.stderr).strip()


def _postgres_status(container: str) -> str:
    code, out = _docker(["inspect", "--format", "{{.State.Status}}", container])
    return out.strip() if code == 0 else "unknown"


def main() -> None:
    parser = argparse.ArgumentParser(description="PostgreSQL reconnect simulation")
    parser.add_argument("--host", default=DEFAULT_HOST, help="API base URL")
    parser.add_argument("--container", default=POSTGRES_CONTAINER,
                        help=f"Postgres container name (default: {POSTGRES_CONTAINER})")
    parser.add_argument("--wait-timeout", type=int, default=MAX_WAIT_SECONDS,
                        help=f"Max seconds to wait for recovery (default: {MAX_WAIT_SECONDS})")
    args = parser.parse_args()

    host = args.host.rstrip("/")
    passed = True

    print(f"\n[{_ts()}] PostgreSQL Reconnect Simulation")
    print(f"  API:       {host}")
    print(f"  Container: {args.container}")
    print(f"  Timeout:   {args.wait_timeout}s\n")

    # Baseline health check
    status, body = _get_health(host)
    postgres_before = body.get("dependencies", {}).get("postgres", {}).get("status", "?")
    overall_before = body.get("status", "?")
    print(f"[{_ts()}] Baseline — overall={overall_before}, postgres={postgres_before}")

    if status == 0:
        print(f"[{_ts()}] SKIP — API not reachable. Start the stack first.")
        sys.exit(0)

    pg_container_state = _postgres_status(args.container)
    print(f"[{_ts()}] Postgres container state: {pg_container_state}")

    if pg_container_state not in ("running", "paused"):
        print(f"[{_ts()}] SKIP — container '{args.container}' not in running state ({pg_container_state})")
        sys.exit(0)

    # Restart postgres
    print(f"\n[{_ts()}] Restarting postgres container...")
    t_restart = time.monotonic()
    code, out = _docker(["restart", args.container], timeout=60)
    if code != 0:
        print(f"[{_ts()}] ERROR — restart failed: {out}")
        sys.exit(2)
    print(f"[{_ts()}] Restart command issued")

    # Poll until degraded
    t_degraded: float | None = None
    t_recovered: float | None = None
    observations: list[dict] = []

    print(f"[{_ts()}] Polling health every 2s (max {args.wait_timeout}s)...\n")
    deadline = time.monotonic() + args.wait_timeout

    while time.monotonic() < deadline:
        time.sleep(2)
        elapsed = time.monotonic() - t_restart
        http_status, hbody = _get_health(host)
        overall = hbody.get("status", f"HTTP {http_status}" if http_status else "unreachable")
        pg_status = (
            hbody.get("dependencies", {}).get("postgres", {}).get("status", "?")
            if isinstance(hbody, dict) else "?"
        )
        pg_container_now = _postgres_status(args.container)

        obs = {
            "elapsed_s": round(elapsed, 1),
            "http": http_status,
            "overall": overall,
            "postgres": pg_status,
            "container": pg_container_now,
        }
        observations.append(obs)
        print(f"[{_ts()}] +{elapsed:.1f}s — overall={overall}, postgres={pg_status}, container={pg_container_now}")

        if t_degraded is None and overall in ("degraded", "critical") or http_status == 503:
            t_degraded = elapsed
            print(f"[{_ts()}]   → Degradation detected at +{elapsed:.1f}s")

        if t_recovered is None and pg_status == "ok" and overall in ("ok", "degraded"):
            t_recovered = elapsed
            print(f"[{_ts()}]   → PostgreSQL recovered at +{elapsed:.1f}s")
            break

    if t_recovered is None:
        print(f"\n[{_ts()}] ✗ PostgreSQL did not recover within {args.wait_timeout}s")
        passed = False
    else:
        print(f"\n[{_ts()}] ✓ PostgreSQL recovered in {t_recovered:.1f}s")

    # Final health check
    time.sleep(2)
    final_status, final_body = _get_health(host)
    final_overall = final_body.get("status", f"HTTP {final_status}")
    final_pg = final_body.get("dependencies", {}).get("postgres", {}).get("status", "?")
    print(f"[{_ts()}] Final health — overall={final_overall}, postgres={final_pg}")

    if final_overall not in ("ok", "degraded"):
        print(f"[{_ts()}] ✗ API not healthy after recovery window")
        passed = False

    print(f"\n{'─'*55}")
    print(f"  RESULT: {'PASS' if passed else 'FAIL'}")
    print(f"  Time to degradation  : {f'{t_degraded:.1f}s' if t_degraded else 'not observed'}")
    print(f"  Time to recovery     : {f'{t_recovered:.1f}s' if t_recovered else 'not recovered'}")
    print(f"  Final API status     : {final_overall}")
    print(f"  Final postgres status: {final_pg}")
    print(f"{'─'*55}\n")

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
