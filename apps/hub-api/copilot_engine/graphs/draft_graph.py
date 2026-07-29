"""
Draft LangGraph (D-014): shared drafting graph for
 - war-room Generate (.docx)
 - copilot draft-section
 - agent_engine proposal_drafting
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional, TypedDict

from sqlalchemy import select
from sqlalchemy.orm import Session
from langgraph.graph import END, StateGraph

from models import Proposal, Opportunity
from memory_engine.scrub.scrubber import scrub_text
from memory_engine.retrieval.retriever import MemoryRetriever
from memory_engine.storage.factory import get_vector_store
from memory_engine.storage.base import SearchResult
from memory_engine.graph import expand_with_store_search
from copilot_engine.config import GROQ_API_KEY
from copilot_engine.providers.base import LLMProvider
from copilot_engine.providers.groq_provider import GroqProvider
from copilot_engine.grounding.validator import validate_grounding, passes_hard_gate
from telemetry.langfuse_client import log_generation, log_span, update_observation


_DEFAULT_SECTIONS = [
    "exec_summary",
    "scope",
    "technical_approach",
    "methodology",
    "timeline",
    "assumptions",
]


class DraftState(TypedDict, total=False):
    proposal_id: str
    title: str
    rfp_type: str
    bu: str
    section: str
    wanted_sections: list[str]
    user_brief: str
    user_query: str
    query: str
    chunks: list[SearchResult]
    context_block: str
    scrubbed_brief: str
    scrub_flags: list[str]
    llm_output: str
    section_map: dict[str, str]
    mode: str
    repair_count: int
    grounding: dict
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    error: str


@dataclass
class DraftResult:
    content: str
    section_map: dict[str, str]
    chunks: list[SearchResult]
    meta: dict[str, Any]


def _split_sections(text: str) -> dict[str, str]:
    if not text or not text.strip():
        return {}
    parts = re.split(r"\n(?=##\s+)", text.strip())
    out: dict[str, str] = {}
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
                out[key] = body
        else:
            out.setdefault("exec_summary", part)
    return out or {"exec_summary": text.strip()}


def _template_from_chunks(chunks: list[SearchResult], brief: str) -> dict[str, str]:
    if not chunks:
        return {
            "exec_summary": (
                "No scrubbed DFIR corpus chunks were available. "
                "Ingest corpus/scrubbed (or seed/scrubbed_demo) then retry Generate."
            ),
            "scope": brief or "Add engagement scope after retrieving exemplars.",
        }
    joined = "\n\n".join(f"[{c.section or 'excerpt'}]\n{c.content[:800]}" for c in chunks[:6])
    return {
        "exec_summary": (
            "Draft assembled from scrubbed historical DFIR exemplars "
            "(fallback mode).\n\n" + joined[:1500]
        ),
        "scope": brief or "Scope derived from retrieved scrubbed patterns — refine with SME.",
        "technical_approach": joined[1500:3500] or chunks[0].content[:1200],
        "methodology": "Follow incident response / DFIR patterns from retrieved context.",
        "assumptions": "Client environment access, evidence preservation, out-of-scope to confirm.",
    }


def _as_context(chunks: list[SearchResult]) -> str:
    return "\n\n".join(
        f"[Source {i+1} | {c.section} | score={c.score:.3f}]\n{c.content[:700]}"
        for i, c in enumerate(chunks)
    ) or "No retrieved context."


def _build_graph(
    db: Session,
    provider: Optional[LLMProvider],
    lf,
):
    retriever = MemoryRetriever(get_vector_store(db))
    llm = provider or (GroqProvider() if GROQ_API_KEY else None)

    async def load_context(state: DraftState) -> DraftState:
        proposal = db.scalar(select(Proposal).where(Proposal.id == state["proposal_id"]))
        if not proposal:
            return {"error": "Proposal not found", "mode": "template_fallback"}
        opp = db.scalar(select(Opportunity).where(Opportunity.id == proposal.opportunity_id))
        title = (opp.title if opp else None) or f"Proposal {state['proposal_id'][:8]}"
        rfp_type = (opp.rfp_type if opp else None) or "DFIR"
        return {"title": title, "rfp_type": rfp_type}

    async def scrub_inputs(state: DraftState) -> DraftState:
        sr = scrub_text((state.get("user_brief") or state.get("user_query") or "").strip())
        query = f"{state.get('section','')} {state.get('rfp_type','')} {sr.text} DFIR proposal".strip()
        return {"scrubbed_brief": sr.text, "scrub_flags": sr.flags, "query": query}

    async def retrieve(state: DraftState) -> DraftState:
        query = (state.get("query") or "")[:500]
        bu = state.get("bu") or "dfir"
        chunks = retriever.retrieve(
            query=query,
            top_k=8,
            memory_type="proposal",
            metadata_filter={"bu": bu} if bu else None,
        )
        if not chunks:
            chunks = retriever.retrieve(query=query, top_k=8, memory_type="proposal")
        log_span(
            lf,
            name="retrieve-context",
            as_type="retriever",
            input_data={"query": query[:200], "bu": bu},
            output_data={"chunk_count": len(chunks), "sources": [c.source_id for c in chunks[:5]]},
            metadata={"memory_type": "proposal"},
        )
        return {"chunks": chunks}

    async def graph_expand(state: DraftState) -> DraftState:
        try:
            expanded = expand_with_store_search(
                state.get("chunks", []),
                store_search_fn=retriever.retrieve,
                query=(state.get("query") or "")[:500],
                bu=state.get("bu"),
                top_k=12,
                max_extra=4,
            )
        except Exception:
            expanded = state.get("chunks", [])
        return {"chunks": expanded}

    async def draft(state: DraftState) -> DraftState:
        chunks = state.get("chunks", [])
        context_block = _as_context(chunks)
        context_scrubbed = scrub_text(context_block)
        log_span(
            lf,
            name="scrub-pii",
            as_type="guardrail",
            input_data={"context_len": len(context_block)},
            output_data={
                "context_flags": context_scrubbed.flags,
                "replacement_count": context_scrubbed.replacements,
            },
        )
        wanted = state.get("wanted_sections") or _DEFAULT_SECTIONS
        if not llm:
            sections = _template_from_chunks(chunks, state.get("scrubbed_brief", ""))
            return {
                "context_block": context_scrubbed.text,
                "section_map": sections,
                "mode": "template_fallback",
                "provider": "none",
                "model": "none",
            }
        system = (
            "You draft cybersecurity DFIR pre-sales proposal sections. "
            "Use ONLY the scrubbed historical context. Do not invent client names, prices, or people. "
            "Add source citations like [Source: ...] or [Context N]. "
            "Output markdown with ## headings for: " + ", ".join(wanted)
        )
        user = (
            f"Opportunity: {state.get('title')}\n"
            f"RFP type: {state.get('rfp_type')}\n"
            f"Brief (scrubbed): {state.get('scrubbed_brief') or '(none)'}\n\n"
            f"Retrieved scrubbed context:\n{context_scrubbed.text}\n\n"
            "Write a complete draft with the requested section headings."
        )
        resp = await llm.complete(system, user, max_tokens=2000)
        log_generation(
            lf,
            name="generate-response",
            model=llm.model_name,
            input_text=f"SYSTEM:\n{system}\n\nUSER:\n{user}",
            output_text=resp.content,
            provider=llm.provider_name,
            input_tokens=resp.input_tokens,
            output_tokens=resp.output_tokens,
            latency_ms=resp.latency_ms,
        )
        return {
            "context_block": context_scrubbed.text,
            "llm_output": resp.content,
            "section_map": _split_sections(resp.content),
            "mode": "groq",
            "provider": llm.provider_name,
            "model": llm.model_name,
            "input_tokens": resp.input_tokens,
            "output_tokens": resp.output_tokens,
            "latency_ms": resp.latency_ms,
        }

    async def validate(state: DraftState) -> DraftState:
        text = state.get("llm_output") or "\n\n".join(
            f"## {k}\n{v}" for k, v in (state.get("section_map") or {}).items()
        )
        report = validate_grounding(text, state.get("chunks", []), require_citations=True)
        gd = report.to_dict()
        gd["score"] = gd.get("grounding_score", 0.0)
        return {"grounding": gd}

    def after_validate(state: DraftState) -> str:
        if state.get("mode") == "template_fallback":
            return "emit"
        report = state.get("grounding") or {}
        if passes_hard_gate(
            type("R", (), {
                "grounding_score": report.get("grounding_score", 0.0),
                "fabrication_flags": report.get("fabrication_flags", []),
                "warnings": report.get("warnings", []),
            })(),
        ):
            return "emit"
        if int(state.get("repair_count") or 0) < 1:
            return "repair"
        return "fallback"

    async def repair(state: DraftState) -> DraftState:
        if not llm:
            return {"mode": "template_fallback"}
        chunks = state.get("chunks", [])
        brief = state.get("scrubbed_brief") or ""
        prev = state.get("llm_output") or ""
        user = (
            "Revise the draft to remove unsupported claims and include citations.\n"
            f"Brief: {brief}\n"
            f"Context:\n{state.get('context_block') or _as_context(chunks)}\n\n"
            f"Previous draft:\n{prev}\n"
        )
        system = (
            "Fix grounding issues. Use only provided context. "
            "No fabricated names/prices/guarantees. Keep requested headings."
        )
        resp = await llm.complete(system, user, max_tokens=1800)
        return {
            "repair_count": int(state.get("repair_count") or 0) + 1,
            "llm_output": resp.content,
            "section_map": _split_sections(resp.content),
            "mode": "repaired",
            "input_tokens": int(state.get("input_tokens") or 0) + resp.input_tokens,
            "output_tokens": int(state.get("output_tokens") or 0) + resp.output_tokens,
        }

    async def fallback(state: DraftState) -> DraftState:
        sections = _template_from_chunks(state.get("chunks", []), state.get("scrubbed_brief", ""))
        return {"section_map": sections, "mode": "template_fallback"}

    async def emit(state: DraftState) -> DraftState:
        out = state.get("section_map") or {}
        if not out:
            out = _template_from_chunks(state.get("chunks", []), state.get("scrubbed_brief", ""))
        update_observation(
            lf,
            output={
                "mode": state.get("mode", "template_fallback"),
                "sections": list(out.keys()),
                "retrieved_chunks": len(state.get("chunks", [])),
                "grounding_score": (state.get("grounding") or {}).get("grounding_score", 0.0),
                "repair_count": int(state.get("repair_count") or 0),
            },
        )
        return {"section_map": out}

    g = StateGraph(DraftState)
    g.add_node("load_context", load_context)
    g.add_node("scrub_inputs", scrub_inputs)
    g.add_node("retrieve", retrieve)
    g.add_node("graph_expand", graph_expand)
    g.add_node("draft", draft)
    g.add_node("validate", validate)
    g.add_node("repair", repair)
    g.add_node("fallback", fallback)
    g.add_node("emit", emit)

    g.set_entry_point("load_context")
    g.add_edge("load_context", "scrub_inputs")
    g.add_edge("scrub_inputs", "retrieve")
    g.add_edge("retrieve", "graph_expand")
    g.add_edge("graph_expand", "draft")
    g.add_edge("draft", "validate")
    g.add_conditional_edges("validate", after_validate, {"emit": "emit", "repair": "repair", "fallback": "fallback"})
    g.add_edge("repair", "validate")
    g.add_edge("fallback", "emit")
    g.add_edge("emit", END)
    return g.compile()


async def run_draft_graph(
    db: Session,
    *,
    proposal_id: str,
    brief: str = "",
    user_query: str = "",
    section: str = "",
    bu: str = "dfir",
    sections: Optional[list[str]] = None,
    provider: Optional[LLMProvider] = None,
    lf=None,
) -> DraftResult:
    app = _build_graph(db, provider, lf)
    init: DraftState = {
        "proposal_id": proposal_id,
        "bu": bu,
        "section": section,
        "wanted_sections": sections or _DEFAULT_SECTIONS,
        "user_brief": brief,
        "user_query": user_query,
        "repair_count": 0,
    }
    out = await app.ainvoke(init)
    section_map = out.get("section_map") or {}
    content = "\n\n".join(f"## {k}\n{v}" for k, v in section_map.items())
    meta = {
        "mode": out.get("mode", "template_fallback"),
        "provider": out.get("provider", "none"),
        "model": out.get("model", "none"),
        "retrieved_chunks": len(out.get("chunks", [])),
        "grounding": out.get("grounding", {}),
        "repair_count": int(out.get("repair_count") or 0),
        "input_tokens": int(out.get("input_tokens") or 0),
        "output_tokens": int(out.get("output_tokens") or 0),
        "latency_ms": float(out.get("latency_ms") or 0.0),
    }
    return DraftResult(content=content, section_map=section_map, chunks=out.get("chunks", []), meta=meta)


async def run_section_draft_graph(
    db: Session,
    *,
    proposal_id: str,
    section: str,
    user_query: str = "",
    provider: Optional[LLMProvider] = None,
    lf=None,
) -> DraftResult:
    result = await run_draft_graph(
        db,
        proposal_id=proposal_id,
        brief=user_query,
        user_query=user_query,
        section=section,
        sections=[section],
        provider=provider,
        lf=lf,
    )
    # Keep one-section content for copilot response readability.
    if section in result.section_map:
        result.content = result.section_map[section]
    elif result.section_map:
        result.content = next(iter(result.section_map.values()))
    return result
