"""
Response quality evaluator — deterministic, no LLM calls.

Checks:
  - JSON validity and field completeness
  - Response length (too short = incomplete)
  - Structured formatting presence
  - Composite quality score (0.0–1.0)
"""
import json
import re
from dataclasses import dataclass, field


@dataclass
class ResponseEvaluation:
    json_valid: bool
    json_fields_present: list[str]
    json_fields_missing: list[str]
    response_length: int
    has_structured_output: bool
    quality_score: float
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "json_valid": self.json_valid,
            "json_fields_present": self.json_fields_present,
            "json_fields_missing": self.json_fields_missing,
            "response_length": self.response_length,
            "has_structured_output": self.has_structured_output,
            "quality_score": self.quality_score,
            "notes": self.notes,
        }


def evaluate_response(
    response: str,
    expected_json_fields: list[str] = None,
) -> ResponseEvaluation:
    expected = expected_json_fields or []

    # Extract and validate JSON
    json_valid = False
    parsed: dict = {}
    json_block = _extract_json(response)
    if json_block:
        try:
            parsed = json.loads(json_block)
            json_valid = True
        except (json.JSONDecodeError, ValueError):
            pass

    present = [f for f in expected if f in parsed]
    missing = [f for f in expected if f not in parsed]

    length = len(response)
    has_structure = json_valid or bool(
        re.search(r"(?:^#+\s|^\d+\.\s|^\*\s|^-\s)", response, re.MULTILINE)
    )

    # Quality score
    field_score = len(present) / len(expected) if expected else 1.0
    length_score = min(length / 300, 1.0)   # ≥300 chars is a reasonable response
    json_score = 1.0 if json_valid else 0.5
    quality = (field_score * 0.5) + (json_score * 0.3) + (length_score * 0.2)

    notes: list[str] = []
    if missing:
        notes.append(f"Missing expected fields: {', '.join(missing)}")
    if length < 50:
        notes.append("Response too short — likely incomplete")
    if not has_structure:
        notes.append("No structured formatting detected")

    return ResponseEvaluation(
        json_valid=json_valid,
        json_fields_present=present,
        json_fields_missing=missing,
        response_length=length,
        has_structured_output=has_structure,
        quality_score=round(quality, 3),
        notes=notes,
    )


def _extract_json(text: str) -> str:
    """Extract JSON block from a response that may have prose around it."""
    # Try fenced block first
    m = re.search(r"```json\s*([\s\S]+?)\s*```", text)
    if m:
        return m.group(1)
    # Try bare JSON object (outermost braces)
    start = text.find("{")
    if start == -1:
        return ""
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return ""
