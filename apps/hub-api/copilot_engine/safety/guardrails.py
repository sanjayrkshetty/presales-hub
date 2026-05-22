"""
Safety guardrails for copilot I/O.

Input validation:
  - Length capping (truncate to MAX_QUERY_LENGTH)
  - Prompt injection pattern detection (hard block)

Output validation:
  - Absolute compliance claims (warning, not block)
  - Fabricated financial claims (warning)

Violations are always returned to the caller for logging and audit.
Hard blocks apply only to prompt injection on the input path.
"""
import re
from dataclasses import dataclass, field

from copilot_engine.config import MAX_QUERY_LENGTH

# ── Input patterns ────────────────────────────────────────────────────────────
_INJECTION_PATTERNS = [
    (r"ignore\s+(all\s+)?(?:previous|above)?\s*instructions?", True, "Prompt injection: ignore instructions"),
    (r"you\s+are\s+now\s+(?:a|an|the)\s+\w+", True, "Prompt injection: role override"),
    (r"forget\s+(?:everything|all)\s+(?:you\s+know|previous)", True, "Prompt injection: context wipe"),
    (r"<\|(?:im_start|im_end|endoftext)\|>", True, "Prompt injection: special token"),
    (r"DAN\s+mode", True, "Prompt injection: jailbreak attempt"),
]

# ── Output patterns ───────────────────────────────────────────────────────────
_UNSAFE_OUTPUT_PATTERNS = [
    (r"\bguaranteed\s+compliant\b", "Absolute compliance guarantee not safe to claim"),
    (r"\b100%\s+(?:secure|compliant|safe)\b", "Absolute security/compliance claim"),
    (r"\bno\s+vulnerabilities?\b", "Absolute vulnerability-free claim"),
    (r"\bwe\s+guarantee\b", "Unqualified guarantee claim"),
]


@dataclass
class SafetyResult:
    passed: bool
    violations: list[str] = field(default_factory=list)
    sanitized_input: str = ""

    def to_dict(self) -> dict:
        return {"passed": self.passed, "violations": self.violations}


def validate_input(query: str) -> SafetyResult:
    violations: list[str] = []
    hard_blocked = False

    # Length cap
    if len(query) > MAX_QUERY_LENGTH:
        violations.append(f"Query truncated from {len(query)} to {MAX_QUERY_LENGTH} chars")
        query = query[:MAX_QUERY_LENGTH]

    # Injection detection
    for pattern, is_hard_block, message in _INJECTION_PATTERNS:
        if re.search(pattern, query, re.IGNORECASE):
            violations.append(message)
            if is_hard_block:
                hard_blocked = True

    return SafetyResult(
        passed=not hard_blocked,
        violations=violations,
        sanitized_input=query,
    )


def validate_output(response: str) -> SafetyResult:
    violations: list[str] = []
    for pattern, message in _UNSAFE_OUTPUT_PATTERNS:
        if re.search(pattern, response, re.IGNORECASE):
            violations.append(message)
    # Output violations are warnings only — never hard block LLM output
    return SafetyResult(passed=True, violations=violations, sanitized_input=response)
