from __future__ import annotations

import re

from agent_engine.config import AGENT_MAX_INPUT_LENGTH
from agent_engine.execution.task_contract import TaskContract

_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(?:previous|above)?\s*instructions?", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(?:a|an|the)\s+\w+", re.IGNORECASE),
    re.compile(r"forget\s+(?:everything|all)\s+(?:you\s+know|previous)", re.IGNORECASE),
    re.compile(r"<\|(?:im_start|im_end|endoftext)\|>"),
    re.compile(r"DAN\s+mode", re.IGNORECASE),
]

_FORBIDDEN_ACTIONS = [
    "delete", "drop table", "rm -rf", "format", "wipe", "destroy",
    "override approval", "bypass", "skip review",
]


def validate_task_contract(contract: TaskContract) -> tuple[bool, list[str]]:
    """Returns (safe, list_of_violations)."""
    violations: list[str] = []

    # Input length cap
    for key, val in contract.input_data.items():
        text = str(val)
        if len(text) > AGENT_MAX_INPUT_LENGTH:
            violations.append(f"input_data[{key!r}] exceeds max length ({len(text)} > {AGENT_MAX_INPUT_LENGTH})")

    # Injection scan across all string input values
    combined = " ".join(str(v) for v in contract.input_data.values())
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(combined):
            violations.append(f"Injection pattern detected: {pattern.pattern[:40]}")

    # Forbidden action keywords
    combined_lower = combined.lower()
    for forbidden in _FORBIDDEN_ACTIONS:
        if forbidden in combined_lower:
            violations.append(f"Forbidden action keyword: {forbidden!r}")

    return len(violations) == 0, violations


def validate_agent_output(output: dict) -> tuple[bool, list[str]]:
    """Output validation — warnings only, never block."""
    warnings: list[str] = []
    output_text = " ".join(str(v) for v in output.values()).lower()

    _ABSOLUTE_CLAIMS = [
        (r"\b100%\s+(?:secure|compliant|guaranteed)\b", "Absolute compliance/security claim"),
        (r"\bno vulnerabilities?\b", "Absolute vulnerability-free claim"),
        (r"\bzero\s+risk\b", "Absolute zero-risk claim"),
    ]
    for pattern, label in _ABSOLUTE_CLAIMS:
        if re.search(pattern, output_text, re.IGNORECASE):
            warnings.append(label)

    return True, warnings  # output validation never blocks
