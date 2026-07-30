---
name: hub-api-senior-review
description: >-
  Senior coding and testing engineer for apps/hub-api. Runs full pytest, Cursor
  browser Generate .docx smoke, triages failures, and fixes bugs/tests itself
  then stops before commit. Use when the user asks for hub-api senior review,
  post-G1 reliability review, /loop hub-api review, or continuous hub-api QA.
---

# Hub API Senior Review

Project skill for a stay-in-the-loop senior engineer over pps/hub-api.

## Locked policy

1. **Scope:** all of pps/hub-api. Touch pps/hub-dashboard only when browser smoke requires it (clicks/navigation). Never Session 4 UI redesign work.
2. **Autonomy:** diagnose -> fix tests/bugs -> re-run quality bar -> **STOP and ask before commit**. Never push unless the user explicitly asks.
3. **Secrets:** never commit .env, keys, or raw/unscrubbed proposals.
4. **Do not revert** landed G1 work:
   - pps/hub-api/tests/test_draft_graph_g1.py
   - pps/hub-api/tests/test_knowledge_graph_expand.py
   - grounding empty-context hard gate in grounding/validator.py
5. **Parallel implementers:** do **not** fight in-flight pgvector / generate-docx timeout / related implementer edits.

## Model preference

When launching a review subagent via Task:

1. Prefer claude-opus-5-thinking-high
2. Else inherit

## Implementer-busy vs clear-to-edit

### Detect "implementers busy"

Treat as busy if **any** of these are true:

- Other agents/subagents are actively editing hub-api (user says so, or parallel Task agents still running on pgvector/timeout/migrations)
- Uncommitted diffs under hot zones you did not author this turn, especially:
  - pps/hub-api/**/middleware*
  - pgvector / embedding migration files
  - generate-docx timeout / route timeout wiring
  - files clearly mid-edit by another agent
- Sentinel file exists: .cursor/hooks/state/implementers-busy (optional; create empty file to force read-only)

### While busy -> READ / REVIEW ONLY

Allowed:

- Read code, git status/diff (non-destructive)
- Run pytest (read-only against code; do not "fix" by editing)
- Browser Generate smoke
- Report findings, failing tests, suggested patches (as text only)

Forbidden:

- Write / StrReplace / edit any files
- Commit, push, force-push
- Rework or revert implementer WIP

End the turn with a short status: pass/fail pytest, smoke result, top issues, and "waiting for implementers to finish before edit mode".

### When clear -> EDIT mode

Allowed after implementers finish (user confirms, or busy signals gone):

1. Fix failing tests and clear hub-api bugs in scope
2. Re-run full quality bar
3. Summarize changes
4. **Ask before commit** — never commit or push unprompted

## Quality bar (every review cycle)

Both must run each cycle when the stack allows.

### 1) Full hub-api pytest

From repo root (PowerShell):

`powershell
Set-Location apps/hub-api
python -m pytest tests/ -x -q --tb=short
`

Prefer the same env pattern as CI when available (EMBEDDING_PROVIDER=hash, LLM_PROVIDER=mock, local Postgres/Redis). If DB/Redis are down, report blocker clearly; do not invent a green result.

### 2) Cursor browser Generate smoke

Target proposal: d3619384-9d59-48c8-b64a-59354ad1b685

1. Ensure stack is up: API http://localhost:8003/api/health, dashboard http://localhost:3002
2. Open dashboard login -> rjun@sisa.demo / Demo@1234
3. Navigate to proposal d3619384-9d59-48c8-b64a-59354ad1b685 (war-room / proposal detail)
4. Trigger **Generate .docx**
5. Pass criteria: request succeeds (HTTP 200, not 504/5xx), download or successful completion UI — note grounding/mode if shown
6. On failure: capture status, console/network error, and whether cause looks like timeout vs pgvector/embedding vs auth

Use Cursor browser tools (rowser_navigate, snapshot, click). Do not commit smoke artifacts or raw proposal content.

## Review workflow

Copy and track:

`
Hub-api senior review:
- [ ] Mode: busy (read-only) OR clear (edit)
- [ ] git status / hot-zone conflict check
- [ ] Full pytest apps/hub-api
- [ ] Browser Generate smoke (d3619384-…)
- [ ] Triage failures (root cause)
- [ ] Fixes applied (edit mode only)
- [ ] Retest pytest + smoke
- [ ] STOP — ask user before commit
`

### Bug triage -> fix -> retest

1. Classify: test bug, product bug, infra/env blocker, or implementer WIP collision
2. If WIP collision -> stay read-only; report only
3. If clear and fixable in hub-api -> minimal fix; no drive-by refactors
4. Re-run pytest; re-smoke if generate-docx / drafting / grounding / retrieval touched
5. Present summary + ask: commit? (default no)

## Continuous cadence (/loop)

User starts a recurring review (~10–15 min). Exact command:

`	ext
/loop 15m /hub-api-senior-review
`

Alternate: /loop 10m /hub-api-senior-review

On each tick:

1. Re-check implementer-busy protocol
2. Run quality bar
3. Edit only if clear; otherwise report-only
4. Never push; ask before commit after fixes

Optional busy sentinel:

`powershell
New-Item -ItemType File -Force .cursor/hooks/state/implementers-busy
# when implementers done:
Remove-Item -Force .cursor/hooks/state/implementers-busy
`

## Optional advisory hook

Project hook .cursor/hooks/hub-api-senior-review-advisory.py (wired in .cursor/hooks.json) fires on agent stop and may emit a **one-shot** follow-up reminder to run this skill. It is advisory only: no edits, no blocks, fail-open. See hook script header for behavior.

## Out of scope

- Session 4 UI redesign
- Fighting pgvector / timeout implementers
- Committing secrets or raw corpus/proposals
- Pushing without explicit user request
