"""
Content splitters for the memory engine ingestion pipeline.

Three splitters:
  ProposalChunker   — splits proposal.content JSON into section chunks
  DocumentChunker   — sliding window over free-form text (markdown, notes)
  ApprovalChunker   — wraps an approval comment as a single chunk with metadata

Design invariants:
  - Every chunk has a deterministic chunk_id (SHA-256 of source+section+content)
  - Chunks shorter than MIN_CHUNK_CHARS are discarded (no signal)
  - Overlapping chunks share context across boundary (DocumentChunker only)
"""
from dataclasses import dataclass, field
from typing import Optional

from models.memory import make_chunk_id
from memory_engine.config import CHUNK_MAX_CHARS, CHUNK_OVERLAP_CHARS, MIN_CHUNK_CHARS


@dataclass
class RawChunk:
    """A chunk ready for embedding — no vector yet."""
    chunk_id: str
    memory_type: str
    source_type: str
    source_id: str
    section: Optional[str]
    content: str
    metadata: dict = field(default_factory=dict)
    source_version: int = 1


# ── ProposalChunker ───────────────────────────────────────────────────────────

# Sections we index from proposal.content
_PROPOSAL_SECTIONS = [
    "exec_summary", "scope", "technical_approach", "methodology",
    "timeline", "team", "pricing", "risk_matrix", "compliance",
    "appendix", "references",
]


class ProposalChunker:
    """
    Splits proposal.content (JSON dict) into one chunk per section.
    Large sections are further split with DocumentChunker.
    """

    def __init__(self, max_chars: int = CHUNK_MAX_CHARS):
        self._max = max_chars
        self._doc_chunker = DocumentChunker(max_chars=max_chars)

    def chunk(
        self,
        proposal_id: str,
        content: dict,
        metadata: dict,
        source_version: int = 1,
    ) -> list[RawChunk]:
        chunks: list[RawChunk] = []
        for section in _PROPOSAL_SECTIONS:
            text = content.get(section)
            if not text or not str(text).strip():
                continue
            text = str(text).strip()
            if len(text) <= self._max:
                cid = make_chunk_id(proposal_id, section, text)
                if len(text) >= MIN_CHUNK_CHARS:
                    chunks.append(RawChunk(
                        chunk_id=cid,
                        memory_type="proposal",
                        source_type="proposal",
                        source_id=proposal_id,
                        section=section,
                        content=text,
                        metadata={**metadata, "section": section},
                        source_version=source_version,
                    ))
            else:
                # Split large sections with overlap
                sub_chunks = self._doc_chunker.chunk(
                    source_id=proposal_id,
                    text=text,
                    memory_type="proposal",
                    source_type="proposal",
                    metadata={**metadata, "section": section},
                    section=section,
                    source_version=source_version,
                )
                chunks.extend(sub_chunks)
        return chunks


# ── DocumentChunker ───────────────────────────────────────────────────────────

class DocumentChunker:
    """
    Sliding window chunker for free-form text.
    Splits on sentence boundaries where possible (looks for '. ' or '\n').
    Falls back to hard character cut if no boundary found.
    """

    def __init__(
        self,
        max_chars: int = CHUNK_MAX_CHARS,
        overlap_chars: int = CHUNK_OVERLAP_CHARS,
    ):
        self._max = max_chars
        self._overlap = overlap_chars

    def _split_text(self, text: str) -> list[str]:
        segments: list[str] = []
        start = 0
        while start < len(text):
            end = start + self._max
            if end >= len(text):
                segment = text[start:]
                if len(segment) >= MIN_CHUNK_CHARS:
                    segments.append(segment)
                break
            # Try to find a clean break (sentence boundary)
            boundary = -1
            for sep in (". ", ".\n", "\n\n", "\n", " "):
                pos = text.rfind(sep, start + self._overlap, end)
                if pos != -1:
                    boundary = pos + len(sep)
                    break
            if boundary == -1 or boundary <= start:
                boundary = end
            segment = text[start:boundary].strip()
            if len(segment) >= MIN_CHUNK_CHARS:
                segments.append(segment)
            start = max(start + 1, boundary - self._overlap)
        return segments

    def chunk(
        self,
        source_id: str,
        text: str,
        memory_type: str,
        source_type: str,
        metadata: dict,
        section: Optional[str] = None,
        source_version: int = 1,
    ) -> list[RawChunk]:
        segments = self._split_text(text.strip())
        chunks: list[RawChunk] = []
        for i, seg in enumerate(segments):
            sec = f"{section}_part{i}" if section else f"part{i}"
            cid = make_chunk_id(source_id, sec, seg)
            chunks.append(RawChunk(
                chunk_id=cid,
                memory_type=memory_type,
                source_type=source_type,
                source_id=source_id,
                section=sec,
                content=seg,
                metadata={**metadata, "part_index": i},
                source_version=source_version,
            ))
        return chunks


# ── ApprovalChunker ───────────────────────────────────────────────────────────

class ApprovalChunker:
    """Wraps an approval decision note as a single chunk."""

    def chunk(
        self,
        approval_id: str,
        proposal_id: str,
        stage: Optional[str],
        status: str,
        decision_note: Optional[str],
        actor_id: Optional[str],
        metadata: dict,
        source_version: int = 1,
    ) -> Optional[RawChunk]:
        text_parts = []
        if decision_note and len(decision_note.strip()) >= MIN_CHUNK_CHARS:
            text_parts.append(decision_note.strip())
        if status:
            text_parts.append(f"Decision: {status}")
        if stage:
            text_parts.append(f"Stage: {stage}")
        text = " | ".join(text_parts)
        if len(text) < MIN_CHUNK_CHARS:
            return None
        section = f"approval_{stage or 'unknown'}"
        cid = make_chunk_id(approval_id, section, text)
        return RawChunk(
            chunk_id=cid,
            memory_type="approval",
            source_type="approval",
            source_id=approval_id,
            section=section,
            content=text,
            metadata={
                **metadata,
                "proposal_id": proposal_id,
                "stage": stage,
                "status": status,
                "actor_id": actor_id,
            },
            source_version=source_version,
        )
