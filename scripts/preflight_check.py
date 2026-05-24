#!/usr/bin/env python3
"""
Pre-deployment readiness check for Presales Hub.

Usage:
    python scripts/preflight_check.py            # human-readable output
    python scripts/preflight_check.py --json     # JSON output for CI

Exit codes:
    0  All checks pass
    1  One or more warnings (non-blocking)
    2  One or more failures (blocking)
"""
import argparse
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"
ENV_EXAMPLE = ROOT / ".env.full.example"

REQUIRED_PORTS = [8003, 3002, 5432, 6379, 7233]
REQUIRED_ENV_VARS = [
    "SECRET_KEY",
    "DATABASE_URL",
    "ALLOWED_ORIGINS",
]
MIN_DISK_GB = 5.0
MIN_PYTHON = (3, 11)
MIN_NODE = (18, 0)


@dataclass
class CheckResult:
    name: str
    status: Literal["pass", "warn", "fail"]
    detail: str
    hint: str = ""


@dataclass
class Report:
    checks: list[CheckResult] = field(default_factory=list)

    def add(self, name: str, status: Literal["pass", "warn", "fail"], detail: str, hint: str = "") -> None:
        self.checks.append(CheckResult(name, status, detail, hint))

    def exit_code(self) -> int:
        statuses = {c.status for c in self.checks}
        if "fail" in statuses:
            return 2
        if "warn" in statuses:
            return 1
        return 0


def _check_docker(report: Report) -> None:
    if shutil.which("docker") is None:
        report.add("docker-cli", "fail", "docker not found in PATH", "Install Docker Desktop")
        return
    try:
        subprocess.run(["docker", "info"], capture_output=True, timeout=10, check=True)
        report.add("docker-daemon", "pass", "daemon reachable")
    except subprocess.CalledProcessError:
        report.add("docker-daemon", "fail", "docker daemon not running", "Run: Docker Desktop → Start")
    except subprocess.TimeoutExpired:
        report.add("docker-daemon", "warn", "docker info timed out after 10s")


def _check_compose(report: Report) -> None:
    try:
        result = subprocess.run(
            ["docker", "compose", "version"],
            capture_output=True, text=True, timeout=10,
        )
        version_line = result.stdout.strip()
        report.add("docker-compose-v2", "pass", version_line or "v2 detected")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        report.add("docker-compose-v2", "fail", "docker compose v2 not available",
                   "Upgrade to Docker Desktop ≥ 4.x for compose v2")


def _check_ports(report: Report) -> None:
    for port in REQUIRED_PORTS:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                report.add(f"port-{port}", "warn",
                            f"port {port} already in use — another service may conflict",
                            "Check: netstat -ano | findstr :{port}")
        except (ConnectionRefusedError, socket.timeout, OSError):
            report.add(f"port-{port}", "pass", f"port {port} free")


def _check_env_file(report: Report) -> None:
    if ENV_FILE.exists():
        report.add("env-file", "pass", ".env found")
    else:
        hint = f"cp {ENV_EXAMPLE.name} .env  (then fill in values)" if ENV_EXAMPLE.exists() else "Create .env from template"
        report.add("env-file", "fail", ".env not found", hint)
        return

    missing = []
    env_contents = ENV_FILE.read_text(encoding="utf-8")
    for var in REQUIRED_ENV_VARS:
        if f"{var}=" not in env_contents or f"{var}=\n" in env_contents or f"{var}=" not in env_contents:
            # check more precisely
            found = any(line.startswith(f"{var}=") and len(line) > len(var) + 1
                        for line in env_contents.splitlines())
            if not found:
                missing.append(var)

    if missing:
        report.add("env-vars", "fail",
                   f"Missing or empty required vars: {', '.join(missing)}",
                   "Set these in .env before deploying")
    else:
        report.add("env-vars", "pass", f"All {len(REQUIRED_ENV_VARS)} required vars present")


def _check_python_version(report: Report) -> None:
    current = sys.version_info[:2]
    if current >= MIN_PYTHON:
        report.add("python-version", "pass", f"Python {sys.version.split()[0]} (≥{MIN_PYTHON[0]}.{MIN_PYTHON[1]} required)")
    else:
        report.add("python-version", "fail",
                   f"Python {sys.version.split()[0]} < {MIN_PYTHON[0]}.{MIN_PYTHON[1]}",
                   f"Install Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+")


def _check_node_version(report: Report) -> None:
    node = shutil.which("node")
    if not node:
        report.add("node-version", "warn", "node not found in PATH — dashboard build will fail",
                   "Install Node.js 18+")
        return
    try:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True, timeout=5)
        version_str = result.stdout.strip().lstrip("v")
        major, minor, *_ = (int(x) for x in version_str.split("."))
        if (major, minor) >= MIN_NODE:
            report.add("node-version", "pass", f"Node.js v{version_str} (≥{MIN_NODE[0]}.{MIN_NODE[1]} required)")
        else:
            report.add("node-version", "fail",
                       f"Node.js v{version_str} < {MIN_NODE[0]}.{MIN_NODE[1]}",
                       "Upgrade to Node.js 18+")
    except Exception as exc:
        report.add("node-version", "warn", f"Could not determine Node.js version: {exc}")


def _check_disk_space(report: Report) -> None:
    try:
        usage = shutil.disk_usage(ROOT)
        free_gb = usage.free / (1024 ** 3)
        if free_gb >= MIN_DISK_GB:
            report.add("disk-space", "pass", f"{free_gb:.1f} GB free (≥{MIN_DISK_GB} GB required)")
        else:
            report.add("disk-space", "fail",
                       f"Only {free_gb:.1f} GB free — Docker images need ≥{MIN_DISK_GB} GB",
                       "Free up disk space before building images")
    except OSError as exc:
        report.add("disk-space", "warn", f"Could not check disk space: {exc}")


def _print_human(report: Report) -> None:
    icons = {"pass": "✓", "warn": "⚠", "fail": "✗"}
    colors = {
        "pass": "\033[32m",
        "warn": "\033[33m",
        "fail": "\033[31m",
    }
    reset = "\033[0m"
    use_color = sys.stdout.isatty() and platform.system() != "Windows"

    print("\n  Presales Hub — Pre-flight Check\n")
    for c in report.checks:
        icon = icons[c.status]
        label = c.name.ljust(22)
        detail = c.detail
        if use_color:
            line = f"  {colors[c.status]}{icon}{reset}  {label}  {detail}"
        else:
            line = f"  [{c.status.upper():4}]  {label}  {detail}"
        print(line)
        if c.hint:
            print(f"          {'':22}  → {c.hint}")

    totals = {s: sum(1 for c in report.checks if c.status == s) for s in ("pass", "warn", "fail")}
    print(f"\n  {totals['pass']} pass  {totals['warn']} warn  {totals['fail']} fail\n")
    code = report.exit_code()
    if code == 0:
        print("  Stack is ready to deploy.\n")
    elif code == 1:
        print("  Deploy with caution — review warnings above.\n")
    else:
        print("  DO NOT deploy — fix failures above first.\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Presales Hub pre-deploy readiness check")
    parser.add_argument("--json", action="store_true", help="Output JSON (for CI)")
    args = parser.parse_args()

    report = Report()
    _check_python_version(report)
    _check_node_version(report)
    _check_docker(report)
    _check_compose(report)
    _check_disk_space(report)
    _check_env_file(report)
    _check_ports(report)

    if args.json:
        output = {
            "exit_code": report.exit_code(),
            "checks": [
                {"name": c.name, "status": c.status, "detail": c.detail, "hint": c.hint}
                for c in report.checks
            ],
            "summary": {
                s: sum(1 for c in report.checks if c.status == s)
                for s in ("pass", "warn", "fail")
            },
        }
        print(json.dumps(output, indent=2))
    else:
        _print_human(report)

    sys.exit(report.exit_code())


if __name__ == "__main__":
    main()
