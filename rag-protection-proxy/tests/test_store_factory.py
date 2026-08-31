import pytest

from rag_protection_proxy.store import create_document_store


def test_create_document_store_defaults_to_sqlite(tmp_path, monkeypatch):
    monkeypatch.delenv("RAG_STORE_BACKEND", raising=False)
    store = create_document_store(tmp_path / "data")
    assert store.count_documents() == 0


def test_create_document_store_vector_backend(tmp_path, monkeypatch):
    monkeypatch.setenv("RAG_STORE_BACKEND", "vector")
    monkeypatch.setenv("RAG_QDRANT_URL", ":memory:")
    monkeypatch.setenv("RAG_EMBEDDING_BACKEND", "hash")
    store = create_document_store(tmp_path / "data")
    store.ingest("doc-1", "Doc", "hello world", ["all-staff"])
    assert store.count_documents() == 1


def test_create_document_store_hybrid_backend(tmp_path, monkeypatch):
    monkeypatch.setenv("RAG_STORE_BACKEND", "hybrid")
    monkeypatch.setenv("RAG_QDRANT_URL", ":memory:")
    monkeypatch.setenv("RAG_EMBEDDING_BACKEND", "hash")
    store = create_document_store(tmp_path / "data")
    store.ingest("doc-1", "Doc", "hello hybrid world", ["all-staff"])
    assert store.count_documents() == 1
