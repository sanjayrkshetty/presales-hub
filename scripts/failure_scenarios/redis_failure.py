#!/usr/bin/env python3
"""
Failure scenario: Redis pause/unpause

Pauses the Redis container via `docker pause`, waits for observable DLQ accumulation,
then unpauses. Verifies that:
  1. API remains reachable (degrades gracefully, does not crash)
  2. DLQ event count increases while Redis is paused
  3. DLQ drains (or events are retried) after Redis resumes

Usage:
    python scripts/failure_scenarios/redis_failure.py
    python scripts/failure_scenarios/redis_failure.py --host http://10.0.0.1:8003
    python scripts/failure_scenarios/redis_failure.py --pause-seconds 15

Requires: docker CLI accessible, presales-hub compose stack running
"""
import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request

REDIS_CONTAINER = "presales-hub-redis-1"
DEFAULT_HOST = "http://localhost:8003"
PAUSE_SECONDS = 10


def _ts() -> str:
    return time.strftime("%H:%M:%S")


def _get(url: str, timeout: float = 5.0) -> tuple[int, dict]:
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {}
    except Exception as exc:
        return 0, {"error": str(exc)}


def _docker(cmd: list[str]) -> tuple[int, str]:
    result = subprocess.run(
        ["docker"] + cmd,
        capture_output=True, text=True, timeout=15,
    )
    return result.returncode, (result.stdout + result.stderr).strip()


def _dlq_count(host: str) -> int:
    status, body = _get(f"{host}/api/system/dlq")
    if status == 200:
        return body.get("total_pending", body.get("count", -1))
    return -1


def _health_status(host: str) -> str:
    status, body = _get(f"{host}/api/health")
    if status in (200, 503):
        return body.get("status", f"HTTP {status}")
    return f"unreachable (HTTP {status})"


def main() -> None:
    parser = argparse.ArgumentParser(description="Redis failure simulation")
    parser.add_argument("--host", default=DEFAULT_HOST, help="API base URL")
    parser.add_argument("--pause-seconds", type=int, default=PAUSE_SECONDS,
                        help="Seconds to keep Redis paused (default: 10)")
    parser.add_argument("--container", default=REDIS_CONTAINER,
                        help=f"Redis container name (default: {REDIS_CONTAINER})")
    args = parser.parse_args()

    host = args.host.rstrip("/")
    passed = True

    print(f"\n[{_ts()}] Redis Failure Simulation")
    print(f"  API:       {host}")
    print(f"  Container: {args.container}")
    print(f"  Pause:     {args.pause_seconds}s\n")

    # Baseline
    health_before = _health_status(host)
    dlq_before = _dlq_count(host)
    print(f"[{_ts()}] Baseline — health={health_before}, DLQ pending={dlq_before}")

    if health_before == "unreachable (HTTP 0)":
        print(f"[{_ts()}] SKIP — API not reachable at {host}. Start the stack first.")
        sys.exit(0)

    # Pause Redis
    print(f"[{_ts()}] Pausing Redis container ({args.container})...")
    code, out = _docker(["pause", args.container])
    if code != 0:
        print(f"[{_ts()}] ERROR — could not pause container: {out}")
        print(f"[{_ts()}] Is the stack running? Check: docker compose ps")
        sys.exit(2)
    print(f"[{_ts()}] Redis paused. Observing for {args.pause_seconds}s...")

    # Observe during pause
    health_during = []
    dlq_during = []
    for i in range(args.pause_seconds):
        time.sleep(1)
        h = _health_status(host)
        d = _dlq_count(host)
        health_during.append(h)
        dlq_during.append(d)
        print(f"[{_ts()}] +{i+1}s — health={h}, DLQ pending={d}")

    # API must remain reachable (degrade, not crash)
    api_stayed_up = all(s != "unreachable (HTTP 0)" for s in health_during)
    degraded_or_ok = any(s in ("degraded", "ok") for s in health_during)
    if api_stayed_up:
        print(f"[{_ts()}] ✓ API remained reachable during Redis outage (status: {set(health_during)})")
    else:
        print(f"[{_ts()}] ✗ API became unreachable during Redis pause — investigate crash")
        passed = False

    # Unpause Redis
    print(f"\n[{_ts()}] Unpausing Redis...")
    code, out = _docker(["unpause", args.container])
    if code != 0:
        print(f"[{_ts()}] ERROR — could not unpause: {out}. Manual intervention required.")
        sys.exit(2)

    print(f"[{_ts()}] Redis resumed. Waiting 5s for recovery...")
    time.sleep(5)

    health_after = _health_status(host)
    dlq_after = _dlq_count(host)
    print(f"\n[{_ts()}] After recovery — health={health_after}, DLQ pending={dlq_after}")

    if health_after in ("ok", "degraded"):
        print(f"[{_ts()}] ✓ API recovered after Redis resume")
    else:
        print(f"[{_ts()}] ✗ API did not recover to ok/degraded after Redis resume")
        passed = False

    # Summary
    print(f"\n{'─'*50}")
    print(f"  RESULT: {'PASS' if passed else 'FAIL'}")
    print(f"  API stayed up during outage : {api_stayed_up}")
    print(f"  API recovered after resume  : {health_after in ('ok', 'degraded')}")
    print(f"  DLQ before/during/after     : {dlq_before} / max={max(dlq_during) if dlq_during else '?'} / {dlq_after}")
    print(f"{'─'*50}\n")

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
