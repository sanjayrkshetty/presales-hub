"""
Grounding validator — ensures LLM responses are anchored in retrieved context.

Three signals:
  1. Citation presence — [Source: X], [Context N], [Pattern: X], [Approval: X]
  2. Keyword overlap — vocabulary shared between response and context
  3. Fabrication patterns — suspicious absolute claims or unsupported specifics

Score = citation(0.3) + overlap*0.7 - fabrication_penalty*0.1 per flag
Clamped to [0.0, 1.0].

Hard gate (D-014): use `passes_hard_gate` / `GROUNDING_HARD_MIN` inside the
draft LangGraph — warn-only remains the default for legacy CopilotRunner calls.
"""
import re
from dataclasses import dataclass, field

from memory_engine.storage.base import SearchResult

# Minimum composite score to accept a Groq draft without repair/fallback.
GROUNDING_HARD_MIN = 0.35

_CITATION_RE = re.compile(
    r"\[(?:Source|Context|Pattern|Approval)[\s:][^\]]{1,80}\]",
    re.IGNORECASE,
)

_FABRICATION_PATTERNS = [
    (r"\bISO \d{5}\b", "Specific ISO standard not verified against context"),
    (r"\b\$[\d,]+\b", "Specific dollar amount not sourced from context"),
    (r"\b\d{1,3}%\s+(?:guarantee|guaranteed|SLA)\b", "Percentage guarantee claim"),
    (r"\b100%\s+(?:secure|compliant|complied)\b", "Absolute security/compliance claim"),
    (r"\bno vulnerabilities?\b", "Absolute vulnerability-free claim"),
]


@dataclass
class GroundingReport:
    grounding_score: float
    has_citations: bool
    keyword_overlap: float
    fabrication_flags: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "grounding_score": self.grounding_score,
            "has_citations": self.has_citations,
            "keyword_overlap": round(self.keyword_overlap, 3),
            "fabrication_flags": self.fabrication_flags,
            "warnings": self.warnings,
        }


def validate_grounding(
    response: str,
    context_chunks: list[SearchResult],
    require_citations: bool = False,
) -> GroundingReport:
    # 1. Citation presence
    has_citations = bool(_CITATION_RE.search(response))

    # 2. Keyword overlap with context
    context_text = " ".join(c.content for c in context_chunks) if context_chunks else ""
    if context_text:
        ctx_words = set(re.findall(r"\b[a-z]{4,}\b", context_text.lower()))
        resp_words = set(re.findall(r"\b[a-z]{4,}\b", response.lower()))
        overlap = len(resp_words & ctx_words) / len(resp_words) if resp_words else 0.0
    else:
        overlap = 0.0

    # 3. Fabrication patterns
    fabrication_flags = []
    for pattern, message in _FABRICATION_PATTERNS:
        if re.search(pattern, response, re.IGNORECASE):
            fabrication_flags.append(message)

    # 4. Warnings
    warnings: list[str] = []
    if not context_chunks:
        warnings.append("No context chunks provided — response is ungrounded")
    if require_citations and not has_citations:
        warnings.append("CITATION_REQUIRED: no citations found in response")

    # 5. Composite score
    citation_score = 0.3 if has_citations else 0.0
    overlap_score = min(overlap * 0.7, 0.7)
    penalty = len(fabrication_flags) * 0.1
    score = max(0.0, min(1.0, citation_score + overlap_score - penalty))

    return GroundingReport(
        grounding_score=round(score, 3),
        has_citations=has_citations,
        keyword_overlap=overlap,
        fabrication_flags=fabrication_flags,
        warnings=warnings,
    )


def passes_hard_gate(
    report: GroundingReport,
    *,
    min_score: float = GROUNDING_HARD_MIN,
    allow_empty_context: bool = False,
) -> bool:
    """True when draft is grounded enough to emit (no repair/fallback required)."""
    if not allow_empty_context and any(
        "No context chunks provided" in w for w in (report.warnings or [])
    ):
        return False
    if report.fabrication_flags:
        return False
    return report.grounding_score >= min_score
