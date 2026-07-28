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
from memory_engine.retrieval.retriever import MemoryRetriever
from memory_engine.storage.factory import get_vector_store
from copilot_engine.config import GROQ_API_KEY
from telemetry.context import set_proposal_id
from telemetry.langfuse_client import langfuse_trace, log_generation, log_span

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

    with langfuse_trace(
        "warroom.generate_docx",
        metadata={"proposal_id": proposal_id, "bu": bu},
    ) as lf:
        proposal = db.scalar(select(Proposal).where(Proposal.id == proposal_id))
        if not proposal:
            raise ValueError("Proposal not found")

        opp = db.scalar(select(Opportunity).where(Opportunity.id == proposal.opportunity_id))
        title = (opp.title if opp else None) or f"Proposal {proposal_id[:8]}"
        rfp_type = (opp.rfp_type if opp else None) or "DFIR"

        scrubbed_brief = scrub_text(brief or "")
        query = f"{rfp_type} {scrubbed_brief.text} DFIR incident response proposal".strip()

        store = get_vector_store(db)
        retriever = MemoryRetriever(store)
        chunks = retriever.retrieve(
            query=query[:500],
            top_k=8,
            memory_type="proposal",
            metadata_filter={"bu": bu} if bu else None,
        )
        if not chunks:
            chunks = retriever.retrieve(query=query[:500], top_k=8, memory_type="proposal")

        log_span(
            lf,
            name="rag.retrieve",
            input_data={"query": query[:200], "bu": bu},
            output_data={
                "chunk_count": len(chunks),
                "top_scores": [round(c.score, 4) for c in chunks[:5]],
            },
            metadata={"memory_type": "proposal"},
        )

        context_block = "\n\n".join(
            f"[Source {i+1} | {c.section} | score={c.score:.3f}]\n{c.content[:700]}"
            for i, c in enumerate(chunks)
        ) or "No retrieved context."
        context_scrubbed = scrub_text(context_block)

        log_span(
            lf,
            name="scrub.pass",
            input_data={"brief_len": len(brief or ""), "context_len": len(context_block)},
            output_data={
                "brief_flags": scrubbed_brief.flags,
                "context_flags": context_scrubbed.flags,
                "replacements": scrubbed_brief.replacements + context_scrubbed.replacements,
            },
        )

        mode = "template_fallback"
        provider_name = "none"
        model_name = "none"
        wanted = sections or _DEFAULT_SECTIONS

        if GROQ_API_KEY:
            try:
                from copilot_engine.providers.groq_provider import GroqProvider

                provider = GroqProvider()
                system = (
                    "You draft cybersecurity DFIR pre-sales proposal sections. "
                    "Use ONLY the scrubbed historical context. Do not invent client names, "
                    "prices, or people. Output markdown with ## headings for: "
                    + ", ".join(wanted)
                )
                user = (
                    f"Opportunity: {title}\nRFP type: {rfp_type}\n"
                    f"Brief (scrubbed): {scrubbed_brief.text or '(none)'}\n\n"
                    f"Retrieved scrubbed context:\n{context_scrubbed.text}\n\n"
                    "Write a complete draft with the requested section headings."
                )
                resp = await provider.complete(system, user, max_tokens=2000)
                section_map = _split_sections(resp.content)
                mode = "groq"
                provider_name = provider.provider_name
                model_name = provider.model_name
                log_generation(
                    lf,
                    name="groq.generate_docx",
                    model=model_name,
                    input_text=f"SYSTEM:\n{system}\n\nUSER:\n{user}",
                    output_text=resp.content,
                    provider=provider_name,
                    input_tokens=resp.input_tokens,
                    output_tokens=resp.output_tokens,
                    latency_ms=resp.latency_ms,
                    metadata={"sections": list(section_map.keys())},
                )
            except Exception as exc:
                logger.warning("Groq generate failed, using template fallback: %s", exc)
                section_map = _template_from_chunks(chunks, scrubbed_brief.text)
                mode = "template_fallback"
                log_span(
                    lf,
                    name="generate.fallback",
                    output_data={"reason": str(exc)[:300]},
                    metadata={"mode": mode},
                )
        else:
            section_map = _template_from_chunks(chunks, scrubbed_brief.text)
            log_span(
                lf,
                name="generate.fallback",
                output_data={"reason": "GROQ_API_KEY unset"},
                metadata={"mode": mode},
            )

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
            "scrub_flags": list(set(scrubbed_brief.flags + context_scrubbed.flags)),
            "sections": list(section_map.keys()),
            "bytes": len(docx_bytes),
            "langfuse": lf is not None,
        }
        log_span(
            lf,
            name="docx.build",
            output_data={"bytes": len(docx_bytes), "sections": list(section_map.keys()), "mode": mode},
        )
        return docx_bytes, meta
