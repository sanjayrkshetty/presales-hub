"""
Corpus / DFIR pack ingestion into pgvector memory.

Reads scrubbed .txt / .md / .docx from a local directory (default: corpus/scrubbed
at repo root, or apps/hub-api/seed/scrubbed_demo for the committed demo pack).

Never indexes raw/unscrubbed trees. Applies scrub_text as a last pass.
Tags every chunk with bu=dfir|vapt|grc|shared (v1: dfir + optional shared).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from memory_engine.chunking.splitter import DocumentChunker, RawChunk
from memory_engine.indexing.indexer import MemoryIndexer
from memory_engine.scrub.scrubber import scrub_text
from memory_engine.storage.factory import get_vector_store
from telemetry.langfuse_client import observe_pipeline, log_span, update_observation

logger = logging.getLogger("memory_engine.ingestion.corpus")

_TEXT_SUFFIXES = {".txt", ".md", ".markdown"}
_DOCX_SUFFIXES = {".docx"}


def _repo_root() -> Path:
    # Local: .../presales-hub/apps/hub-api/memory_engine/ingestion/this.py -> parents[4]
    # Docker: /app/memory_engine/ingestion/this.py — walk up for corpus/ or apps/
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "corpus").is_dir() or (parent / "apps" / "hub-api").is_dir():
            return parent
    # Fall back to hub-api package root (/app in Docker)
    return here.parents[2]


def default_scrubbed_dirs() -> list[Path]:
    root = _repo_root()
    app_root = Path(__file__).resolve().parents[2]  # hub-api or /app
    return [
        root / "corpus" / "scrubbed",
        app_root / "seed" / "scrubbed_demo",
    ]


def _read_docx(path: Path) -> str:
    from docx import Document

    doc = Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs if p.text and p.text.strip())


def _read_file(path: Path) -> str:
    if path.suffix.lower() in _DOCX_SUFFIXES:
        return _read_docx(path)
    return path.read_text(encoding="utf-8", errors="replace")


def ingest_scrubbed_corpus(
    db: Session,
    *,
    source_dir: Optional[str] = None,
    bu: str = "dfir",
    memory_type: str = "proposal",
) -> dict:
    """
    Index scrubbed corpus files into memory_chunks.

    Args:
        source_dir: optional absolute/relative path; if None, scans default dirs.
        bu: content pack tag (dfir|vapt|grc|shared).
        memory_type: memory domain (proposal for DFIR exemplars).
    """
    if bu not in {"dfir", "vapt", "grc", "shared"}:
        return {"error": f"invalid bu={bu}", "indexed": 0}

    dirs: list[Path]
    if source_dir:
        dirs = [Path(source_dir)]
    else:
        dirs = [d for d in default_scrubbed_dirs() if d.is_dir()]

    if not dirs:
        return {
            "error": "No scrubbed corpus directory found. Place files under corpus/scrubbed/ (gitignored) or use seed/scrubbed_demo.",
            "indexed": 0,
            "dirs": [],
        }

    chunker = DocumentChunker()
    all_chunks: list[RawChunk] = []
    files_seen = 0
    scrub_hits = 0

    for d in dirs:
        for path in sorted(d.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in (_TEXT_SUFFIXES | _DOCX_SUFFIXES):
                continue
            if path.name.startswith("."):
                continue
            try:
                raw = _read_file(path)
            except Exception as exc:
                logger.warning("Skip %s: %s", path, exc)
                continue
            scrubbed = scrub_text(raw)
            if scrubbed.replacements:
                scrub_hits += 1
            text = scrubbed.text.strip()
            if not text:
                continue
            files_seen += 1
            rel = str(path.relative_to(d)) if path.is_relative_to(d) else path.name
            source_id = f"corpus:{bu}:{rel}"
            meta = {
                "bu": bu,
                "corpus_path": rel,
                "scrub_flags": scrubbed.flags,
                "rfp_type": "DFIR" if bu == "dfir" else bu.upper(),
            }
            chunks = chunker.chunk(
                source_id=source_id,
                text=text,
                memory_type=memory_type,
                source_type="document",
                metadata=meta,
                section="corpus",
            )
            all_chunks.extend(chunks)

    if not all_chunks:
        return {
            "indexed": 0,
            "files": files_seen,
            "dirs": [str(d) for d in dirs],
            "message": "No indexable scrubbed content found",
        }

    with observe_pipeline(
        "ingest-scrubbed-corpus",
        as_type="chain",
        input={"bu": bu, "memory_type": memory_type, "files": files_seen},
        metadata={"bu": bu, "memory_type": memory_type},
        tags=["corpus", "rag", bu],
        feature="corpus-ingest",
    ) as lf:
        store = get_vector_store(db)
        indexer = MemoryIndexer(store)

        # Reindex per source so re-runs are idempotent
        by_source: dict[str, list[RawChunk]] = {}
        for c in all_chunks:
            by_source.setdefault(c.source_id, []).append(c)

        indexed = 0
        deactivated = 0
        for source_id, chunks in by_source.items():
            result = indexer.reindex_source(source_id, chunks)
            indexed += result.get("indexed", 0)
            deactivated += result.get("deactivated", 0)

        result = {
            "bu": bu,
            "files": files_seen,
            "indexed": indexed,
            "deactivated": deactivated,
            "scrub_pass_hits": scrub_hits,
            "dirs": [str(d) for d in dirs],
            "langfuse": lf is not None,
        }
        log_span(
            lf,
            name="index-chunks",
            as_type="embedding",
            input_data={"dirs": [str(d) for d in dirs], "bu": bu},
            output_data=result,
        )
        update_observation(lf, output=result)
        logger.info(
            "Corpus ingest bu=%s files=%s chunks=%s",
            bu,
            files_seen,
            indexed,
        )
        return result
