"""
War-room Generate → editable .docx.

Pipeline:
  1. Load proposal + opportunity context
  2. Retrieve scrubbed DFIR / proposal chunks (bu filter)
  3. Scrub any user brief / retrieved content before cloud LLM
  4. Call Groq on scrubbed text when GROQ_API_KEY is set
  5. Fallback: stitch retrieved chunks into a grounded template docx

Langfuse: traces retrieval + generation when LANGFUSE_* keys are set.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Proposal, Opportunity
from memory_engine.scrub.scrubber import scrub_text
from memory_engine.docx_gen.builder import build_proposal_docx
from copilot_engine.graphs.draft_graph import run_draft_graph
from telemetry.context import set_proposal_id
from telemetry.langfuse_client import observe_pipeline, log_span, update_observation

logger = logging.getLogger("memory_engine.generate_docx")

_DEFAULT_SECTIONS = [
    "exec_summary",
    "scope",
    "technical_approach",
    "methodology",
    "timeline",
    "assumptions",
]


def _split_sections(text: str) -> dict[str, str]:
    """Parse LLM markdown output into a section map."""
    if not text or not text.strip():
        return {}
    parts = re.split(r"\n(?=##\s+)", text.strip())
    sections: dict[str, str] = {}
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if part.startswith("##"):
            lines = part.split("\n", 1)
            heading = lines[0].lstrip("#").strip()
            body = lines[1].strip() if len(lines) > 1 else ""
            key = re.sub(r"[^a-z0-9]+", "_", heading.lower()).strip("_") or "section"
            if body:
                sections[key] = body
        else:
            sections.setdefault("exec_summary", part)
    return sections or {"exec_summary": text.strip()}


def _template_from_chunks(chunks, brief: str) -> dict[str, str]:
    if not chunks:
        return {
            "exec_summary": (
                "No scrubbed DFIR corpus chunks were available. "
                "Ingest corpus/scrubbed (or seed/scrubbed_demo) then retry Generate."
            ),
            "scope": brief or "Add engagement scope after retrieving exemplars.",
        }
    joined = "\n\n".join(
        f"[{c.section or 'excerpt'}]\n{c.content[:800]}" for c in chunks[:6]
    )
    return {
        "exec_summary": (
            "Draft assembled from scrubbed historical DFIR exemplars "
            "(Groq unavailable — template fallback).\n\n" + joined[:1500]
        ),
        "scope": brief or "Scope derived from retrieved scrubbed patterns — refine with SME.",
        "technical_approach": joined[1500:3500] or chunks[0].content[:1200],
        "methodology": (
            "Follow incident response retainership / DFIR engagement patterns "
            "from retrieved context."
        ),
        "assumptions": (
            "Client environment access, evidence preservation, and out-of-scope "
            "items to be confirmed."
        ),
    }


async def generate_proposal_docx(
    db: Session,
    proposal_id: str,
    *,
    brief: str = "",
    bu: str = "dfir",
    sections: Optional[list[str]] = None,
) -> tuple[bytes, dict]:
    """Returns (docx_bytes, meta)."""
    set_proposal_id(proposal_id)

    with observe_pipeline(
        "generate-proposal-docx",
        as_type="chain",
        input={"proposal_id": proposal_id, "bu": bu, "brief_len": len(brief or "")},
        metadata={"proposal_id": proposal_id, "bu": bu},
        tags=["war-room", "rag", "docx"],
        feature="generate-docx",
    ) as lf:
        proposal = db.scalar(select(Proposal).where(Proposal.id == proposal_id))
        if not proposal:
            raise ValueError("Proposal not found")

        opp = db.scalar(select(Opportunity).where(Opportunity.id == proposal.opportunity_id))
        title = (opp.title if opp else None) or f"Proposal {proposal_id[:8]}"
        rfp_type = (opp.rfp_type if opp else None) or "DFIR"

        scrubbed_brief = scrub_text(brief or "")
        wanted = sections or _DEFAULT_SECTIONS
        draft = await run_draft_graph(
            db,
            proposal_id=proposal_id,
            brief=scrubbed_brief.text,
            user_query=scrubbed_brief.text,
            bu=bu,
            sections=wanted,
            lf=lf,
        )
        section_map = draft.section_map
        chunks = draft.chunks
        mode = draft.meta.get("mode", "template_fallback")
        provider_name = draft.meta.get("provider", "none")
        model_name = draft.meta.get("model", "none")

        docx_bytes = build_proposal_docx(
            title=title,
            sections=section_map,
            subtitle=f"{rfp_type} · pack={bu} · mode={mode}",
        )
        meta = {
            "proposal_id": proposal_id,
            "mode": mode,
            "provider": provider_name,
            "model": model_name,
            "retrieved_chunks": len(chunks),
            "bu": bu,
            "scrub_flags": list(set(scrubbed_brief.flags)),
            "sections": list(section_map.keys()),
            "bytes": len(docx_bytes),
            "langfuse": lf is not None,
            "grounding": draft.meta.get("grounding", {}),
            "repair_count": draft.meta.get("repair_count", 0),
        }
        log_span(
            lf,
            name="build-docx",
            as_type="span",
            output_data={"bytes": len(docx_bytes), "sections": list(section_map.keys()), "mode": mode},
        )
        update_observation(
            lf,
            output={
                "mode": mode,
                "sections": list(section_map.keys()),
                "retrieved_chunks": len(chunks),
                "bytes": len(docx_bytes),
            },
        )
        return docx_bytes, meta
