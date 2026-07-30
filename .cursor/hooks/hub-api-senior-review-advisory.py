#!/usr/bin/env python3
"""Advisory hub-api senior-review reminder (read-only / fail-open).

Event: stop
Behavior:
  - Never blocks the agent (always exit 0; no deny).
  - Never edits the repo.
  - Emits followup_message at most once per stop (hooks.json loop_limit: 1) when:
      * .cursor/hooks/state/implementers-busy exists, or
      * stop payload mentions hub-api, or
      * git status shows dirty paths under apps/hub-api
  - Fail-open on any parse/IO error (empty JSON object).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def repo_root() -> Path:
    # Script lives at <repo>/.cursor/hooks/<this-file>
    return Path(__file__).resolve().parents[2]


def hub_api_dirty(root: Path) -> bool:
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain", "--", "apps/hub-api"],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception:
        return False
    return bool(proc.stdout.strip())


def main() -> int:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        print("{}")
        return 0

    root = repo_root()
    busy = (root / ".cursor" / "hooks" / "state" / "implementers-busy").exists()
    blob = json.dumps(payload, ensure_ascii=False).lower()
    hub_api_signal = (
        "hub-api" in blob
        or "apps/hub-api" in blob
        or "apps\\hub-api" in blob
        or hub_api_dirty(root)
    )

    if not busy and not hub_api_signal:
        print("{}")
        return 0

    if busy:
        msg = (
            "Hub-api senior review reminder: implementers-busy sentinel is set. "
            "Run /hub-api-senior-review in READ/REVIEW ONLY mode "
            "(pytest + Generate smoke for proposal d3619384-9d59-48c8-b64a-59354ad1b685). "
            "Do not edit until implementers finish. Prefer model claude-opus-5-thinking-high."
        )
    else:
        msg = (
            "Hub-api senior review reminder: consider running /hub-api-senior-review "
            "(full apps/hub-api pytest + browser Generate smoke). "
            "Fix bugs/tests only if implementers are idle; then STOP and ask before commit. "
            "Prefer model claude-opus-5-thinking-high."
        )

    print(json.dumps({"followup_message": msg}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        # Fail open - never block agent stop.
        print("{}")
        raise SystemExit(0)
