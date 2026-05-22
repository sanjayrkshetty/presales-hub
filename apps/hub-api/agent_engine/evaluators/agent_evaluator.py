from __future__ import annotations

from agent_engine.execution.task_contract import AgentResult


def evaluate_result(result: AgentResult, expected_fields: list[str] | None = None) -> dict:
    """
    Score an AgentResult. Returns an eval dict that gets merged into the result metadata.
    """
    field_score = 0.0
    if expected_fields and result.output:
        content = result.output.get("content", "")
        hit = sum(1 for f in expected_fields if f in content)
        field_score = hit / len(expected_fields) if expected_fields else 1.0

    status_score = 1.0 if result.status in ("completed", "pending_approval") else 0.0
    grounding_score = result.grounding_score
    confidence_score = result.confidence

    overall = (
        field_score * 0.3
        + status_score * 0.2
        + grounding_score * 0.3
        + confidence_score * 0.2
    )

    return {
        "field_score": round(field_score, 3),
        "status_score": round(status_score, 3),
        "grounding_score": round(grounding_score, 3),
        "confidence_score": round(confidence_score, 3),
        "overall_score": round(overall, 3),
        "expected_fields": expected_fields or [],
    }


def passed_quality_gate(eval_result: dict, threshold: float = 0.4) -> bool:
    return eval_result.get("overall_score", 0.0) >= threshold
