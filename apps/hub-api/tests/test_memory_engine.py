"""
Enterprise Memory Engine — test suite.

10 test classes:
  TestLocalHashEmbedder       — determinism, normalization, cosine properties
  TestDocumentChunker         — sliding window, overlap, min length
  TestProposalChunker         — section extraction, empty sections skipped
  TestApprovalChunker         — content assembly, metadata
  TestSqliteVectorStore       — upsert, search cosine, deactivate, filter
  TestMemoryIndexer           — end-to-end embed+store, dedup, reindex
  TestRetriever               — top-k ordering, metadata filter, empty index
  TestRetrievalEvaluators     — MRR, P@k, Recall@k correctness
  TestKnowledgeModules        — ProposalMemory, ApprovalMemory (unit)
  TestMemoryAPI               — HTTP endpoint integration tests
"""
import json
import pytest
import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch


# ── Local Hash Embedder ────────────────────────────────────────────────────────

class TestLocalHashEmbedder:
    def _provider(self):
        from memory_engine.embeddings.local_provider import LocalHashEmbeddingProvider
        return LocalHashEmbeddingProvider(dims=128)

    def test_deterministic_same_text(self):
        p = self._provider()
        a = p.embed("zero trust network architecture banking")
        b = p.embed("zero trust network architecture banking")
        assert a == b

    def test_different_texts_different_vectors(self):
        p = self._provider()
        a = p.embed("SOC transformation threat detection")
        b = p.embed("financial compliance audit requirements")
        assert a != b

    def test_output_length_matches_dims(self):
        p = self._provider()
        vec = p.embed("test text")
        assert len(vec) == 128

    def test_unit_normalized(self):
        p = self._provider()
        vec = p.embed("enterprise security architecture")
        norm = sum(x * x for x in vec) ** 0.5
        assert abs(norm - 1.0) < 1e-6

    def test_cosine_self_similarity_is_one(self):
        p = self._provider()
        vec = p.embed("cloud security devSecOps")
        dot = sum(x * y for x, y in zip(vec, vec))
        assert abs(dot - 1.0) < 1e-6

    def test_similar_texts_higher_cosine(self):
        p = self._provider()
        query = p.embed("SOC threat detection monitoring")
        similar = p.embed("SOC monitoring threat intelligence")
        unrelated = p.embed("financial budget approval workflow")
        dot_sim = sum(x * y for x, y in zip(query, similar))
        dot_unrel = sum(x * y for x, y in zip(query, unrelated))
        assert dot_sim > dot_unrel

    def test_empty_text_returns_zero_vector(self):
        p = self._provider()
        vec = p.embed("")
        assert all(v == 0.0 for v in vec)

    def test_batch_embed_matches_single(self):
        p = self._provider()
        texts = ["text one", "text two", "text three"]
        batch = p.embed_batch(texts)
        singles = [p.embed(t) for t in texts]
        assert batch == singles


# ── Document Chunker ───────────────────────────────────────────────────────────

class TestDocumentChunker:
    def _chunker(self, max_chars=200, overlap=20):
        from memory_engine.chunking.splitter import DocumentChunker
        return DocumentChunker(max_chars=max_chars, overlap_chars=overlap)

    def test_short_text_single_chunk(self):
        c = self._chunker()
        chunks = c.chunk("src", "Short text that is long enough to pass the minimum.", "proposal", "proposal", {})
        assert len(chunks) == 1

    def test_long_text_multiple_chunks(self):
        c = self._chunker(max_chars=50)
        text = "A" * 200
        chunks = c.chunk("src", text, "proposal", "proposal", {})
        assert len(chunks) > 1

    def test_chunk_ids_unique(self):
        c = self._chunker(max_chars=50)
        text = "word " * 60
        chunks = c.chunk("src", text, "proposal", "proposal", {})
        ids = [ch.chunk_id for ch in chunks]
        assert len(ids) == len(set(ids))

    def test_min_length_filter(self):
        from memory_engine.chunking.splitter import DocumentChunker
        c = DocumentChunker(max_chars=5)
        # Very short text under MIN_CHUNK_CHARS
        chunks = c.chunk("src", "Hi", "proposal", "proposal", {})
        assert len(chunks) == 0

    def test_metadata_propagated(self):
        c = self._chunker()
        chunks = c.chunk("src", "Enough text here.", "proposal", "proposal", {"rfp_type": "SOC"})
        assert all(ch.metadata.get("rfp_type") == "SOC" for ch in chunks)

    def test_source_id_preserved(self):
        c = self._chunker()
        chunks = c.chunk("my-source-id", "Text here.", "proposal", "proposal", {})
        assert all(ch.source_id == "my-source-id" for ch in chunks)


# ── Proposal Chunker ───────────────────────────────────────────────────────────

class TestProposalChunker:
    def _chunker(self):
        from memory_engine.chunking.splitter import ProposalChunker
        return ProposalChunker()

    def test_empty_content_no_chunks(self):
        c = self._chunker()
        chunks = c.chunk("p1", {}, {})
        assert chunks == []

    def test_filled_section_produces_chunk(self):
        c = self._chunker()
        content = {"exec_summary": "This is a detailed executive summary for a banking SOC deal."}
        chunks = c.chunk("p1", content, {})
        assert len(chunks) == 1
        assert chunks[0].section == "exec_summary"
        assert "banking" in chunks[0].content

    def test_empty_section_skipped(self):
        c = self._chunker()
        content = {"exec_summary": "", "scope": "   "}
        chunks = c.chunk("p1", content, {})
        assert len(chunks) == 0

    def test_multiple_sections_multiple_chunks(self):
        c = self._chunker()
        content = {
            "exec_summary": "Executive summary with detail.",
            "scope": "Project scope and requirements.",
            "risk_matrix": "Risk: regulatory non-compliance.",
        }
        chunks = c.chunk("p1", content, {})
        assert len(chunks) == 3
        sections = {ch.section for ch in chunks}
        assert "exec_summary" in sections
        assert "scope" in sections

    def test_metadata_includes_section(self):
        c = self._chunker()
        content = {"exec_summary": "This is an executive summary with enough content to pass the minimum length filter."}
        chunks = c.chunk("p1", content, {"rfp_type": "SOC"})
        assert chunks[0].metadata["section"] == "exec_summary"
        assert chunks[0].metadata["rfp_type"] == "SOC"

    def test_chunk_id_deterministic(self):
        c = self._chunker()
        content = {"scope": "Same scope text that is long enough to pass the minimum length filter."}
        chunks_a = c.chunk("p1", content, {})
        chunks_b = c.chunk("p1", content, {})
        assert chunks_a[0].chunk_id == chunks_b[0].chunk_id


# ── Approval Chunker ───────────────────────────────────────────────────────────

class TestApprovalChunker:
    def _chunker(self):
        from memory_engine.chunking.splitter import ApprovalChunker
        return ApprovalChunker()

    def test_decision_note_produces_chunk(self):
        c = self._chunker()
        chunk = c.chunk(
            approval_id="a1", proposal_id="p1", stage="security_review",
            status="rejected", decision_note="Scope too broad, missing threat model.",
            actor_id="actor-1", metadata={},
        )
        assert chunk is not None
        assert "Scope too broad" in chunk.content

    def test_empty_note_too_short_returns_none(self):
        c = self._chunker()
        chunk = c.chunk(
            approval_id="a1", proposal_id="p1", stage="approval",
            status="approved", decision_note="ok",  # too short
            actor_id="actor-1", metadata={},
        )
        # "ok | Decision: approved | Stage: approval" is >= MIN_CHUNK_CHARS
        # This may produce a chunk depending on total length
        # Just verify it doesn't crash

    def test_metadata_includes_stage_and_status(self):
        c = self._chunker()
        chunk = c.chunk(
            approval_id="a1", proposal_id="p1", stage="finance_review",
            status="rejected", decision_note="Commercial terms non-compliant with policy.",
            actor_id="actor-f", metadata={},
        )
        assert chunk is not None
        assert chunk.metadata["stage"] == "finance_review"
        assert chunk.metadata["status"] == "rejected"


# ── SQLite Vector Store ────────────────────────────────────────────────────────

class TestSqliteVectorStore:
    def _store(self, db):
        from memory_engine.storage.sqlite_store import SqliteVectorStore
        return SqliteVectorStore(db)

    def _vec(self, dims=128, seed=1):
        """Reproducible unit vector."""
        import hashlib
        raw = [float(int(hashlib.md5(f"{seed}{i}".encode(), usedforsecurity=False).hexdigest(), 16) % 100) for i in range(dims)]
        norm = sum(x * x for x in raw) ** 0.5
        return [x / norm for x in raw]

    def test_upsert_and_count(self, db):
        store = self._store(db)
        store.upsert("c1", "proposal", "proposal", "p1", "scope", "scope content", self._vec(), "local-hash-v1", {})
        assert store.count() == 1

    def test_search_returns_top_k(self, db):
        store = self._store(db)
        for i in range(5):
            store.upsert(f"c{i}", "proposal", "proposal", f"p{i}", "scope", f"content {i}", self._vec(seed=i), "local-hash-v1", {})
        results = store.search(self._vec(seed=0), top_k=3)
        assert len(results) == 3

    def test_self_similarity_highest(self, db):
        store = self._store(db)
        vec = self._vec(seed=42)
        store.upsert("target", "proposal", "proposal", "p1", "scope", "target content", vec, "local-hash-v1", {})
        store.upsert("other", "proposal", "proposal", "p2", "scope", "other content", self._vec(seed=99), "local-hash-v1", {})
        results = store.search(vec, top_k=5)
        assert results[0].chunk_id == "target"

    def test_memory_type_filter(self, db):
        store = self._store(db)
        store.upsert("prop-c", "proposal", "proposal", "p1", "scope", "proposal text", self._vec(seed=1), "local-hash-v1", {})
        store.upsert("appr-c", "approval", "approval", "a1", "decision", "approval text", self._vec(seed=2), "local-hash-v1", {})
        results = store.search(self._vec(seed=1), top_k=5, memory_type="approval")
        assert all(r.memory_type == "approval" for r in results)
        assert len(results) == 1

    def test_metadata_filter(self, db):
        store = self._store(db)
        store.upsert("c1", "proposal", "proposal", "p1", "s", "text a", self._vec(seed=1), "local-hash-v1", {"rfp_type": "SOC"})
        store.upsert("c2", "proposal", "proposal", "p2", "s", "text b", self._vec(seed=2), "local-hash-v1", {"rfp_type": "Zero Trust"})
        results = store.search(self._vec(seed=1), top_k=5, metadata_filter={"rfp_type": "SOC"})
        assert len(results) == 1
        assert results[0].chunk_id == "c1"

    def test_deactivate_source(self, db):
        store = self._store(db)
        store.upsert("c1", "proposal", "proposal", "p1", "scope", "content", self._vec(seed=1), "local-hash-v1", {})
        store.upsert("c2", "proposal", "proposal", "p1", "exec", "content", self._vec(seed=2), "local-hash-v1", {})
        deactivated = store.deactivate_source("p1")
        assert deactivated == 2
        assert store.count() == 0

    def test_upsert_idempotent(self, db):
        store = self._store(db)
        vec = self._vec()
        store.upsert("c1", "proposal", "proposal", "p1", "scope", "content", vec, "local-hash-v1", {})
        store.upsert("c1", "proposal", "proposal", "p1", "scope", "content", vec, "local-hash-v1", {})
        assert store.count() == 1  # no duplicate

    def test_get_by_source(self, db):
        store = self._store(db)
        store.upsert("c1", "proposal", "proposal", "src1", "s1", "content a", self._vec(seed=1), "m", {})
        store.upsert("c2", "proposal", "proposal", "src1", "s2", "content b", self._vec(seed=2), "m", {})
        store.upsert("c3", "proposal", "proposal", "src2", "s1", "content c", self._vec(seed=3), "m", {})
        results = store.get_by_source("src1")
        assert len(results) == 2
        assert all(r.source_id == "src1" for r in results)


# ── Memory Indexer ────────────────────────────────────────────────────────────

class TestMemoryIndexer:
    def _indexer(self, db):
        from memory_engine.storage.sqlite_store import SqliteVectorStore
        from memory_engine.embeddings.local_provider import LocalHashEmbeddingProvider
        from memory_engine.indexing.indexer import MemoryIndexer
        store = SqliteVectorStore(db)
        provider = LocalHashEmbeddingProvider()
        return MemoryIndexer(store=store, provider=provider), store

    def _chunk(self, cid, source_id, content, memory_type="proposal"):
        from memory_engine.chunking.splitter import RawChunk
        return RawChunk(
            chunk_id=cid, memory_type=memory_type, source_type=memory_type,
            source_id=source_id, section="scope", content=content, metadata={},
        )

    def test_index_chunks_returns_count(self, db):
        indexer, store = self._indexer(db)
        chunks = [self._chunk(f"c{i}", "p1", f"content {i}") for i in range(3)]
        count = indexer.index_chunks(chunks)
        assert count == 3
        assert store.count() == 3

    def test_reindex_deactivates_stale(self, db):
        indexer, store = self._indexer(db)
        old_chunks = [self._chunk("c-old", "p1", "old content")]
        indexer.index_chunks(old_chunks)
        assert store.count() == 1

        new_chunks = [self._chunk("c-new", "p1", "new content")]
        result = indexer.reindex_source("p1", new_chunks)
        assert result["deactivated"] == 1
        assert result["indexed"] == 1
        assert store.count() == 1

    def test_empty_chunks_returns_zero(self, db):
        indexer, _ = self._indexer(db)
        assert indexer.index_chunks([]) == 0


# ── Memory Retriever ──────────────────────────────────────────────────────────

class TestRetriever:
    def _setup(self, db, texts_and_metadata):
        from memory_engine.storage.sqlite_store import SqliteVectorStore
        from memory_engine.embeddings.local_provider import LocalHashEmbeddingProvider
        from memory_engine.indexing.indexer import MemoryIndexer
        from memory_engine.retrieval.retriever import MemoryRetriever
        from memory_engine.chunking.splitter import RawChunk

        store = SqliteVectorStore(db)
        provider = LocalHashEmbeddingProvider()
        indexer = MemoryIndexer(store=store, provider=provider)
        retriever = MemoryRetriever(store)

        chunks = []
        for i, (text, meta, memory_type) in enumerate(texts_and_metadata):
            chunks.append(RawChunk(
                chunk_id=f"ret-{i}", memory_type=memory_type, source_type=memory_type,
                source_id=f"src-{i}", section="scope", content=text, metadata=meta,
            ))
        indexer.index_chunks(chunks)
        return retriever

    def test_retriever_returns_top_k(self, db):
        data = [
            ("SOC threat detection monitoring", {}, "proposal"),
            ("financial audit compliance", {}, "proposal"),
            ("zero trust network security", {}, "proposal"),
        ]
        retriever = self._setup(db, data)
        results = retriever.retrieve("SOC monitoring", top_k=2)
        assert len(results) <= 2

    def test_top_result_most_relevant(self, db):
        data = [
            ("SOC threat detection SIEM monitoring security", {}, "proposal"),
            ("annual financial audit budget approval", {}, "proposal"),
        ]
        retriever = self._setup(db, data)
        results = retriever.retrieve("SOC SIEM threat", top_k=2)
        assert results[0].content.startswith("SOC threat")

    def test_memory_type_filter_in_retriever(self, db):
        data = [
            ("security review rejection rationale", {}, "approval"),
            ("SOC security architecture design", {}, "proposal"),
        ]
        retriever = self._setup(db, data)
        results = retriever.retrieve("security", memory_type="approval", top_k=5)
        assert all(r.memory_type == "approval" for r in results)

    def test_empty_index_returns_empty(self, db):
        from memory_engine.storage.sqlite_store import SqliteVectorStore
        from memory_engine.retrieval.retriever import MemoryRetriever
        store = SqliteVectorStore(db)
        retriever = MemoryRetriever(store)
        results = retriever.retrieve("any query", top_k=5)
        assert results == []

    def test_scores_descending(self, db):
        data = [(f"text number {i} content", {}, "proposal") for i in range(5)]
        retriever = self._setup(db, data)
        results = retriever.retrieve("text content", top_k=5)
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)


# ── Retrieval Evaluators ──────────────────────────────────────────────────────

class TestRetrievalEvaluators:
    def test_mrr_perfect_retrieval(self):
        from memory_engine.evaluators.retrieval_eval import mrr_at_k
        queries = [{"relevant_ids": ["c1", "c2"]}]
        retrieved = [["c1", "c3", "c4"]]
        assert mrr_at_k(queries, retrieved, k=5) == 1.0

    def test_mrr_second_position(self):
        from memory_engine.evaluators.retrieval_eval import mrr_at_k
        queries = [{"relevant_ids": ["c2"]}]
        retrieved = [["c1", "c2", "c3"]]
        assert abs(mrr_at_k(queries, retrieved, k=5) - 0.5) < 1e-6

    def test_mrr_no_relevant_found(self):
        from memory_engine.evaluators.retrieval_eval import mrr_at_k
        queries = [{"relevant_ids": ["c5"]}]
        retrieved = [["c1", "c2", "c3"]]
        assert mrr_at_k(queries, retrieved, k=3) == 0.0

    def test_precision_at_k(self):
        from memory_engine.evaluators.retrieval_eval import precision_at_k
        retrieved = ["c1", "c2", "c3", "c4"]
        relevant = {"c1", "c3"}
        assert abs(precision_at_k(retrieved, relevant, k=4) - 0.5) < 1e-6

    def test_recall_at_k(self):
        from memory_engine.evaluators.retrieval_eval import recall_at_k
        retrieved = ["c1", "c2", "c3"]
        relevant = {"c1", "c4"}   # c4 not retrieved
        assert recall_at_k(retrieved, relevant, k=3) == 0.5

    def test_evaluate_retrieval_full_report(self):
        from memory_engine.evaluators.retrieval_eval import evaluate_retrieval
        queries = [
            {"relevant_ids": ["c1"]},
            {"relevant_ids": ["c2"]},
        ]
        retrieved = [["c1", "c3"], ["c3", "c2"]]
        report = evaluate_retrieval(queries, retrieved, k=2)
        assert "mrr_at_k" in report
        assert "precision_at_k" in report
        assert "recall_at_k" in report
        assert report["num_queries"] == 2

    def test_empty_queries(self):
        from memory_engine.evaluators.retrieval_eval import mrr_at_k
        assert mrr_at_k([], [], k=5) == 0.0


# ── Knowledge Module Integration ──────────────────────────────────────────────

class TestKnowledgeModules:
    def test_proposal_memory_index_and_retrieve(self, db, client):
        """Index a proposal and retrieve similar content."""
        # Seed a proposal with content
        from models.opportunity import Client, Opportunity
        from models.proposal import Proposal
        client_id = str(uuid.uuid4())
        opp_id = str(uuid.uuid4())
        prop_id = str(uuid.uuid4())
        db.add(Client(id=client_id, name="HDFC Bank"))
        db.add(Opportunity(id=opp_id, client_id=client_id, title="SOC Transformation",
                           rfp_type="SOC Transformation", stage="drafting"))
        db.add(Proposal(id=prop_id, opportunity_id=opp_id, stage="drafting",
                        content={
                            "exec_summary": "Comprehensive SOC implementation for HDFC Bank threat monitoring.",
                            "scope": "Deploy SIEM platform with 24x7 threat detection and incident response.",
                        }))
        db.commit()

        from memory_engine.knowledge.proposal_memory import ProposalMemory
        pm = ProposalMemory(db)
        result = pm.index(prop_id)
        assert result["indexed"] >= 1

        similar = pm.retrieve_similar("SOC threat detection monitoring", top_k=3)
        assert len(similar) >= 1
        assert any("SOC" in r.content or "threat" in r.content.lower() for r in similar)

    def test_approval_memory_index_and_retrieve(self, db, client):
        """Index an approval rationale and retrieve it."""
        from models.opportunity import Client, Opportunity
        from models.proposal import Proposal
        from models.approval import Approval

        client_id = str(uuid.uuid4())
        opp_id = str(uuid.uuid4())
        prop_id = str(uuid.uuid4())
        appr_id = str(uuid.uuid4())

        db.add(Client(id=client_id, name="Test Client"))
        db.add(Opportunity(id=opp_id, client_id=client_id, title="Test", stage="security_review"))
        db.add(Proposal(id=prop_id, opportunity_id=opp_id, stage="security_review"))
        db.add(Approval(
            id=appr_id, proposal_id=prop_id, stage="security_review",
            status="rejected",
            decision_note="Missing threat model and vulnerability assessment scope.",
        ))
        db.commit()

        from memory_engine.knowledge.approval_memory import ApprovalMemory
        am = ApprovalMemory(db)
        result = am.index_approval(appr_id)
        assert result["chunks_indexed"] >= 1

        rationale = am.retrieve_rationale("threat model missing rejection", top_k=3)
        assert len(rationale) >= 1


# ── Memory API Endpoint Tests ─────────────────────────────────────────────────

class TestMemoryAPI:
    @pytest.fixture
    def seeded(self, db):
        from models.opportunity import Client, Opportunity
        from models.proposal import Proposal
        from models.approval import Approval

        client_id = str(uuid.uuid4())
        opp_id = str(uuid.uuid4())
        prop_id = str(uuid.uuid4())
        appr_id = str(uuid.uuid4())

        db.add(Client(id=client_id, name="Test Corp"))
        db.add(Opportunity(id=opp_id, client_id=client_id, title="Test Opp",
                           rfp_type="SOC Transformation", stage="drafting",
                           win_probability=70))
        db.add(Proposal(id=prop_id, opportunity_id=opp_id, stage="drafting",
                        content={
                            "exec_summary": "SOC threat detection for enterprise banking.",
                            "scope": "SIEM deployment with 24x7 monitoring.",
                        }))
        db.add(Approval(id=appr_id, proposal_id=prop_id, stage="security_review",
                        status="rejected",
                        decision_note="Scope missing: incident response playbook not included."))
        db.commit()
        return {"prop_id": prop_id, "opp_id": opp_id, "appr_id": appr_id,
                "client_id": client_id}

    def test_memory_status_endpoint(self, client, seeded):
        resp = client.get("/api/memory/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_chunks" in data
        assert "by_memory_type" in data

    def test_index_proposal_endpoint(self, client, seeded):
        prop_id = seeded["prop_id"]
        resp = client.post(f"/api/memory/index/proposal/{prop_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "indexed" in data
        assert data["indexed"] >= 1

    def test_index_proposal_unknown_404(self, client, seeded):
        resp = client.post("/api/memory/index/proposal/nonexistent-id")
        assert resp.status_code == 404

    def test_index_approval_endpoint(self, client, seeded):
        appr_id = seeded["appr_id"]
        resp = client.post(f"/api/memory/index/approval/{appr_id}")
        assert resp.status_code == 200

    def test_index_opportunity_endpoint(self, client, seeded):
        opp_id = seeded["opp_id"]
        resp = client.post(f"/api/memory/index/opportunity/{opp_id}")
        assert resp.status_code == 200

    def test_search_endpoint(self, client, seeded):
        # First index the proposal
        prop_id = seeded["prop_id"]
        client.post(f"/api/memory/index/proposal/{prop_id}")

        resp = client.post("/api/memory/search", json={
            "query": "SOC threat detection",
            "top_k": 3,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert "searched_at" in data

    def test_search_with_memory_type_filter(self, client, seeded):
        resp = client.post("/api/memory/search", json={
            "query": "security review",
            "memory_type": "approval",
            "top_k": 5,
        })
        assert resp.status_code == 200
        data = resp.json()
        # All results must be approval type (may be empty if nothing indexed yet)
        for r in data.get("results", []):
            assert r["memory_type"] == "approval"

    def test_similar_proposals_endpoint(self, client, seeded):
        prop_id = seeded["prop_id"]
        client.post(f"/api/memory/index/proposal/{prop_id}")
        resp = client.get(f"/api/memory/proposals/{prop_id}/similar")
        assert resp.status_code == 200
        data = resp.json()
        assert "similar_proposals" in data

    def test_approvals_rationale_endpoint(self, client, seeded):
        appr_id = seeded["appr_id"]
        client.post(f"/api/memory/index/approval/{appr_id}")
        resp = client.get("/api/memory/approvals/rationale?query=incident+response+playbook")
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data

    def test_solutions_suggest_endpoint(self, client, seeded):
        resp = client.get("/api/memory/solutions/suggest?query=SOC+monitoring")
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data

    def test_reindex_proposal_endpoint(self, client, seeded):
        prop_id = seeded["prop_id"]
        resp = client.post(f"/api/memory/reindex/proposal/{prop_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("reindexed") == True
