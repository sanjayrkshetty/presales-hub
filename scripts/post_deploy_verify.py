#!/usr/bin/env python3
"""
Post-deployment smoke tests for Presales Hub.

Runs against a live stack and verifies all critical paths.

Usage:
    python scripts/post_deploy_verify.py                        # localhost defaults
    python scripts/post_deploy_verify.py --host http://10.0.0.1:8003
    python scripts/post_deploy_verify.py --host https://api.presaleshub.io

Exit codes:
    0  All checks pass
    1  One or more checks failed
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

DEFAULT_API = "http://localhost:8003"
DEFAULT_DASH = "http://localhost:3002"

DEMO_EMAIL = "arjun@sisa.demo"
DEMO_PASSWORD = "Demo@1234"


@dataclass
class Result:
    name: str
    passed: bool
    detail: str
    elapsed_ms: float = 0.0


@dataclass
class Suite:
    results: list[Result] = field(default_factory=list)
    _base: str = ""

    def record(self, name: str, passed: bool, detail: str, elapsed_ms: float = 0.0) -> None:
        status = "PASS" if passed else "FAIL"
        marker = "✓" if passed else "✗"
        elapsed = f"{elapsed_ms:.0f}ms"
        print(f"  [{status}]  {name.ljust(40)}  {elapsed}  {detail}")
        self.results.append(Result(name, passed, detail, elapsed_ms))

    def all_passed(self) -> bool:
        return all(r.passed for r in self.results)


def _request(
    url: str,
    method: str = "GET",
    body: Any = None,
    headers: dict | None = None,
    timeout: float = 10.0,
) -> tuple[int, dict | str]:
    data = json.dumps(body).encode() if body is not None else None
    hdrs = {"Content-Type": "application/json", **(headers or {})}
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body_bytes = resp.read()
            try:
                return resp.status, json.loads(body_bytes)
            except json.JSONDecodeError:
                return resp.status, body_bytes.decode(errors="replace")
    except urllib.error.HTTPError as e:
        body_bytes = e.read()
        try:
            return e.code, json.loads(body_bytes)
        except json.JSONDecodeError:
            return e.code, body_bytes.decode(errors="replace")
    except urllib.error.URLError as e:
        raise ConnectionError(f"Cannot reach {url}: {e.reason}") from e


def check_health(suite: Suite, base: str) -> None:
    t0 = time.monotonic()
    try:
        status, body = _request(f"{base}/api/health")
        elapsed = (time.monotonic() - t0) * 1000
        if status == 200 and isinstance(body, dict):
            overall = body.get("status", "unknown")
            suite.record("GET /api/health", overall in ("ok", "degraded"),
                         f"status={overall}", elapsed)
        else:
            suite.record("GET /api/health", False, f"HTTP {status}", elapsed)
    except ConnectionError as exc:
        suite.record("GET /api/health", False, str(exc))


def check_metrics(suite: Suite, base: str) -> None:
    t0 = time.monotonic()
    try:
        status, body = _request(f"{base}/metrics")
        elapsed = (time.monotonic() - t0) * 1000
        if status == 200 and body:
            suite.record("GET /metrics", True, f"HTTP {status}, non-empty", elapsed)
        else:
            suite.record("GET /metrics", False, f"HTTP {status} or empty body", elapsed)
    except ConnectionError as exc:
        suite.record("GET /metrics", False, str(exc))


def check_login(suite: Suite, base: str) -> str:
    """Returns the access token on success, empty string on failure."""
    t0 = time.monotonic()
    try:
        status, body = _request(
            f"{base}/auth/login",
            method="POST",
            body={"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
        )
        elapsed = (time.monotonic() - t0) * 1000
        if status == 200 and isinstance(body, dict):
            token = body.get("access_token", "")
            suite.record("POST /auth/login (demo user)", bool(token),
                         f"HTTP {status}, token={'✓' if token else '✗'}", elapsed)
            return token
        else:
            suite.record("POST /auth/login (demo user)", False, f"HTTP {status}", elapsed)
            return ""
    except ConnectionError as exc:
        suite.record("POST /auth/login (demo user)", False, str(exc))
        return ""


def check_analytics(suite: Suite, base: str, token: str) -> None:
    hdrs = {"Authorization": f"Bearer {token}"} if token else {}
    for path in ("/api/analytics/pipeline", "/api/analytics/sla"):
        t0 = time.monotonic()
        try:
            status, _ = _request(f"{base}{path}", headers=hdrs)
            elapsed = (time.monotonic() - t0) * 1000
            suite.record(f"GET {path}", status == 200, f"HTTP {status}", elapsed)
        except ConnectionError as exc:
            suite.record(f"GET {path}", False, str(exc))


def check_ws_connect(suite: Suite, base: str, token: str) -> None:
    """WebSocket upgrade check using raw HTTP upgrade request."""
    ws_base = base.replace("http://", "ws://").replace("https://", "wss://")
    url = f"{ws_base}/ws/activity"
    if token:
        url += f"?token={token}"

    t0 = time.monotonic()
    try:
        import websocket  # type: ignore[import]
        ws = websocket.create_connection(url, timeout=5)
        elapsed = (time.monotonic() - t0) * 1000
        # Try to receive at least one message within 5s
        ws.settimeout(5)
        try:
            msg = ws.recv()
            suite.record("WS /ws/activity (first message)", True,
                         f"connected + message received ({len(msg)} bytes)", elapsed)
        except websocket.WebSocketTimeoutException:
            suite.record("WS /ws/activity (first message)", False,
                         "connected but no message within 5s", elapsed)
        finally:
            ws.close()
    except ImportError:
        suite.record("WS /ws/activity", False,
                     "websocket-client not installed (pip install websocket-client)")
    except Exception as exc:
        elapsed = (time.monotonic() - t0) * 1000
        suite.record("WS /ws/activity", False, str(exc)[:100], elapsed)


def check_rate_limit(suite: Suite, base: str) -> None:
    """21 bad logins should trigger 429."""
    statuses: list[int] = []
    t0 = time.monotonic()
    for i in range(22):
        try:
            status, _ = _request(
                f"{base}/auth/login",
                method="POST",
                body={"email": f"ratelimit{i}@test.invalid", "password": "wrong"},
                timeout=5,
            )
            statuses.append(status)
        except ConnectionError:
            break
    elapsed = (time.monotonic() - t0) * 1000
    hit_429 = 429 in statuses
    suite.record("rate-limit (21× bad login → 429)", hit_429,
                 f"statuses seen: {sorted(set(statuses))}", elapsed)


def check_body_size_limit(suite: Suite, base: str) -> None:
    """11 MB POST body should return 413."""
    payload = b"x" * (11 * 1024 * 1024)
    t0 = time.monotonic()
    req = urllib.request.Request(
        f"{base}/api/proposals",
        data=payload,
        headers={"Content-Type": "application/octet-stream"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            elapsed = (time.monotonic() - t0) * 1000
            suite.record("11 MB body → 413", resp.status == 413,
                         f"HTTP {resp.status} (expected 413)", elapsed)
    except urllib.error.HTTPError as e:
        elapsed = (time.monotonic() - t0) * 1000
        suite.record("11 MB body → 413", e.code == 413,
                     f"HTTP {e.code} (expected 413)", elapsed)
    except ConnectionError as exc:
        suite.record("11 MB body → 413", False, str(exc))


def main() -> None:
    parser = argparse.ArgumentParser(description="Presales Hub post-deploy smoke tests")
    parser.add_argument("--host", default=DEFAULT_API, help="API base URL")
    args = parser.parse_args()

    base = args.host.rstrip("/")
    suite = Suite(_base=base)

    print(f"\n  Presales Hub — Post-Deploy Verification")
    print(f"  Target: {base}\n")

    check_health(suite, base)
    check_metrics(suite, base)
    token = check_login(suite, base)
    check_analytics(suite, base, token)
    check_ws_connect(suite, base, token)
    check_rate_limit(suite, base)
    check_body_size_limit(suite, base)

    passed = sum(1 for r in suite.results if r.passed)
    total = len(suite.results)
    print(f"\n  {passed}/{total} checks passed\n")
    if suite.all_passed():
        print("  Stack is healthy.\n")
        sys.exit(0)
    else:
        failed = [r.name for r in suite.results if not r.passed]
        print(f"  Failed: {', '.join(failed)}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
