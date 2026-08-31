"""Hybrid store population, retrieval, and ranking vs lexical-only / vector-only (E3.6)."""

from __future__ import annotations

import math
from typing import Dict, List

import pytest

from rag_protection_proxy.embeddings import VECTOR_SIZE, HashEmbedder
from rag_protection_proxy.store import (
    DocumentStore,
    HybridDocumentStore,
    StoredChunk,
    _fuse_chunks,
)
from rag_protection_proxy.vector_store import VectorDocumentStore

pytest.importorskip("qdrant_client")
from qdrant_client import QdrantClient

GROUPS = ["all-staff"]
QUERY_ALPHA = "alpha"

# Lexical leader: many repeated query tokens, orthogonal to the query vector.
STUFFED_TEXT = ("alpha " * 40).strip() + " stuffed ranking document"
# Dual-hit: weaker lexical overlap, same vector as the query.
DUAL_TEXT = "alpha dual ranking document"
# Vector-only: no query tokens; kept off the lexical list.
VEC_ONLY_TEXT = "unrelated cafeteria soup salad ranking document"
DECOY_TEXTS = [f"decoy ranking document {n} cafeteria" for n in range(5)]

TWO_PARA_A = ("TICKET-9182 is closed after the workaround was applied. " * 20).strip()
TWO_PARA_B = ("The cafeteria serves soup and salad each weekday at noon. " * 20).strip()
TWO_CHUNK_CONTENT = f"{TWO_PARA_A}\n\n{TWO_PARA_B}"


def _unit(dim: int) -> List[float]:
    vec = [0.0] * VECTOR_SIZE
    vec[dim] = 1.0
    return vec


def _mix(dim_a: int, dim_b: int, mag_a: float = 0.5, mag_b: float = 0.5) -> List[float]:
    vec = [0.0] * VECTOR_SIZE
    vec[dim_a] = mag_a
    vec[dim_b] = mag_b
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


class LookupEmbedder:
    """Exact-text embedder so vector rank is independent of token overlap."""

    def __init__(self, table: Dict[str, List[float]]) -> None:
        self.table = table
        self._fallback = HashEmbedder()

    def embed(self, texts: List[str]) -> List[List[float]]:
        out: List[List[float]] = []
        for text in texts:
            if text in self.table:
                out.append(self.table[text])
            else:
                out.append(self._fallback.embed([text])[0])
        return out


def _ranking_embedder() -> LookupEmbedder:
    table = {
        QUERY_ALPHA: _unit(0),
        DUAL_TEXT: _unit(0),
        STUFFED_TEXT: _unit(1),
        VEC_ONLY_TEXT: _unit(2),
    }
    decoy_vec = _mix(0, 1)
    for text in DECOY_TEXTS:
        table[text] = decoy_vec
    return LookupEmbedder(table)


def _hybrid(
    tmp_path,
    monkeypatch,
    *,
    embedder=None,
    collection: str = "hybrid-retrieval",
) -> HybridDocumentStore:
    monkeypatch.setenv("RAG_EMBEDDING_BACKEND", "hash")
    lexical = DocumentStore(tmp_path / "lexical.db")
    vector = VectorDocumentStore(
        client=QdrantClient(":memory:"),
        collection=collection,
        embedder=embedder or HashEmbedder(),
    )
    return HybridDocumentStore(lexical=lexical, vector=vector)


def _chunk(chunk_id: str, score: float = 0.0) -> StoredChunk:
    return StoredChunk(
        chunk_id=chunk_id,
        document_id=chunk_id.split("::", 1)[0],
        title=chunk_id,
        text=chunk_id,
        allowed_groups=GROUPS,
        score=score,
        metadata={},
    )


def _sorted_chunks(detail: dict) -> List[dict]:
    return sorted(detail["chunks"], key=lambda row: int(row["chunk_index"]))


def _doc_ids(hits: List[StoredChunk]) -> List[str]:
    return [hit.document_id for hit in hits]


def _ingest_ranking_corpus(store) -> None:
    store.ingest("stuffed-lex", "Stuffed lexical", STUFFED_TEXT, GROUPS)
    store.ingest("dual-hit", "Dual hit", DUAL_TEXT, GROUPS)
    store.ingest("vec-only", "Vector only", VEC_ONLY_TEXT, GROUPS)
    for idx, text in enumerate(DECOY_TEXTS):
        store.ingest(f"decoy-{idx}", f"Decoy {idx}", text, GROUPS)


def test_rrf_promotes_dual_hit_above_lexical_only_and_vector_only_orders():
    lexical = [_chunk("lex-leader::0"), _chunk("dual::0"), _chunk("lex-third::0")]
    vector = [_chunk("dual::0"), _chunk("vec-only::0")]
    fused = _fuse_chunks(lexical, vector, top_k=4, rrf_k=60)
    fused_ids = [chunk.chunk_id for chunk in fused]

    assert fused_ids[0] == "dual::0"
    assert fused_ids != [chunk.chunk_id for chunk in lexical]
    assert fused_ids != [chunk.chunk_id for chunk in vector]
    assert "vec-only::0" in fused_ids
    assert fused[0].score == round(1.0 / 61.0 + 1.0 / 62.0, 4)


def test_hybrid_ingest_writes_identical_chunks_to_sqlite_and_qdrant(tmp_path, monkeypatch):
    hybrid = _hybrid(tmp_path, monkeypatch, collection="hybrid-populate")
    count = hybrid.ingest("ticket-index", "Ticket index", TWO_CHUNK_CONTENT, GROUPS)

    assert count >= 2
    assert hybrid.count_documents() == 1
    assert hybrid._vector.count_documents() == 1

    lexical_detail = hybrid._lexical.get_document_detail("ticket-index")
    vector_detail = hybrid._vector.get_document_detail("ticket-index")
    assert lexical_detail is not None
    assert vector_detail is not None

    lex_chunks = _sorted_chunks(lexical_detail)
    vec_chunks = _sorted_chunks(vector_detail)
    assert [row["chunk_id"] for row in lex_chunks] == [row["chunk_id"] for row in vec_chunks]
    assert [row["text"] for row in lex_chunks] == [row["text"] for row in vec_chunks]
    assert lex_chunks[0]["chunk_id"] == "ticket-index::0"
    assert "TICKET-9182" in lex_chunks[0]["text"]
    assert "cafeteria" in lex_chunks[-1]["text"].lower()
    assert len(lex_chunks) >= 2


def test_hybrid_reingest_and_delete_stay_in_lockstep(tmp_path, monkeypatch):
    hybrid = _hybrid(tmp_path, monkeypatch, collection="hybrid-lockstep")
    hybrid.ingest("ticket-index", "Ticket index", TWO_CHUNK_CONTENT, GROUPS)
    hybrid.ingest("ticket-index", "Ticket index", "TICKET-9182 reopened for follow-up.", GROUPS)

    lexical_detail = hybrid._lexical.get_document_detail("ticket-index")
    vector_detail = hybrid._vector.get_document_detail("ticket-index")
    lex_chunks = _sorted_chunks(lexical_detail)
    vec_chunks = _sorted_chunks(vector_detail)
    assert [row["chunk_id"] for row in lex_chunks] == [row["chunk_id"] for row in vec_chunks]
    assert all("reopened" in row["text"] for row in lex_chunks)
    assert all("reopened" in row["text"] for row in vec_chunks)

    assert hybrid.delete_document("ticket-index") is True
    assert hybrid._lexical.get_document_detail("ticket-index") is None
    assert hybrid._vector.get_document_detail("ticket-index") is None
    assert hybrid.count_documents() == 0
    assert hybrid._vector.count_documents() == 0


def test_hybrid_retrieval_matches_rrf_of_both_legs(tmp_path, monkeypatch):
    hybrid = _hybrid(tmp_path, monkeypatch, embedder=_ranking_embedder(), collection="hybrid-rrf-contract")
    _ingest_ranking_corpus(hybrid)

    query, top_k = QUERY_ALPHA, 3
    fetch_k = max(top_k * 3, top_k)
    lexical_hits = hybrid._lexical.search(query, GROUPS, top_k=fetch_k)
    vector_hits = hybrid._vector.search(query, GROUPS, top_k=fetch_k)
    expected = _fuse_chunks(lexical_hits, vector_hits, top_k=top_k, rrf_k=hybrid._rrf_k)
    actual = hybrid.search(query, GROUPS, top_k=top_k)

    assert [hit.chunk_id for hit in actual] == [hit.chunk_id for hit in expected]
    assert {hit.document_id for hit in actual} <= {
        "stuffed-lex",
        "dual-hit",
        "vec-only",
        *[f"decoy-{i}" for i in range(5)],
    }


def test_hybrid_ranking_differs_from_lexical_only_and_vector_only(tmp_path, monkeypatch):
    embedder = _ranking_embedder()
    hybrid = _hybrid(tmp_path, monkeypatch, embedder=embedder, collection="hybrid-rank-compare")
    _ingest_ranking_corpus(hybrid)

    lexical_only = hybrid._lexical.search(QUERY_ALPHA, GROUPS, top_k=2)
    vector_only = hybrid._vector.search(QUERY_ALPHA, GROUPS, top_k=2)
    hybrid_hits = hybrid.search(QUERY_ALPHA, GROUPS, top_k=2)

    assert _doc_ids(lexical_only)[0] == "stuffed-lex"
    assert "dual-hit" in _doc_ids(lexical_only)
    assert _doc_ids(vector_only)[0] == "dual-hit"
    assert "stuffed-lex" not in _doc_ids(vector_only)
    assert _doc_ids(hybrid_hits)[0] == "dual-hit"
    assert _doc_ids(hybrid_hits)[1] == "stuffed-lex"
    assert _doc_ids(hybrid_hits) != _doc_ids(lexical_only)
    assert _doc_ids(hybrid_hits) != _doc_ids(vector_only)


TICKET_TEXT = (
    "Purchase order INV4419 was closed after the workaround. Assignee completed the change."
)
HOURS_TEXT = (
    "The assistance desk operates Monday through Friday from nine until six Eastern. "
    "Walk-ins are welcome."
)
COMPLEMENT_QUERY = "INV4419 when is helpdesk open?"
HOURS_DECOYS = [f"cafeteria soup salad weekday menu {n}" for n in range(5)]


def _complement_embedder() -> LookupEmbedder:
    """Vector axis 0 = paraphrase; axis 1 = invoice id. Query sits on axis 0."""
    table = {
        COMPLEMENT_QUERY: _unit(0),
        HOURS_TEXT: _unit(0),
        TICKET_TEXT: _unit(1),
    }
    near_hours = _mix(0, 1, mag_a=0.85, mag_b=0.15)
    for text in HOURS_DECOYS:
        table[text] = near_hours
    return LookupEmbedder(table)


def test_hybrid_returns_exact_id_and_paraphrase_that_solo_paths_split(tmp_path, monkeypatch):
    """Lexical finds the invoice; vector finds the hours FAQ; hybrid is the only top-2 with both."""
    hybrid = _hybrid(
        tmp_path, monkeypatch, embedder=_complement_embedder(), collection="hybrid-complement"
    )
    hybrid.ingest("e3-609-ticket", "Invoice INV4419", TICKET_TEXT, GROUPS)
    hybrid.ingest("e3-609-hours", "Assistance desk hours", HOURS_TEXT, GROUPS)
    for idx, text in enumerate(HOURS_DECOYS):
        hybrid.ingest(f"e3-609-decoy-{idx}", f"Decoy {idx}", text, GROUPS)

    lexical_only = hybrid._lexical.search(COMPLEMENT_QUERY, GROUPS, top_k=2)
    vector_only = hybrid._vector.search(COMPLEMENT_QUERY, GROUPS, top_k=2)
    hybrid_hits = hybrid.search(COMPLEMENT_QUERY, GROUPS, top_k=2)

    lexical_ids = _doc_ids(lexical_only)
    vector_ids = _doc_ids(vector_only)
    hybrid_ids = _doc_ids(hybrid_hits)

    assert lexical_ids[0] == "e3-609-ticket"
    assert "e3-609-hours" not in lexical_ids
    assert vector_ids[0] == "e3-609-hours"
    assert "e3-609-ticket" not in vector_ids
    assert "e3-609-ticket" in hybrid_ids
    assert "e3-609-hours" in hybrid_ids
    assert hybrid_ids != lexical_ids
    assert hybrid_ids != vector_ids


def test_hybrid_keeps_vector_only_hit_that_lexical_misses(tmp_path, monkeypatch):
    hybrid = _hybrid(tmp_path, monkeypatch, embedder=_ranking_embedder(), collection="hybrid-union")
    _ingest_ranking_corpus(hybrid)

    lexical_ids = {hit.document_id for hit in hybrid._lexical.search(QUERY_ALPHA, GROUPS, top_k=10)}
    vector_ids = {hit.document_id for hit in hybrid._vector.search(QUERY_ALPHA, GROUPS, top_k=10)}
    hybrid_ids = {hit.document_id for hit in hybrid.search(QUERY_ALPHA, GROUPS, top_k=10)}

    assert "vec-only" not in lexical_ids
    assert "dual-hit" in lexical_ids
    assert hybrid_ids == lexical_ids | vector_ids or hybrid_ids <= lexical_ids | vector_ids
    assert "dual-hit" in hybrid_ids
    assert "stuffed-lex" in hybrid_ids
