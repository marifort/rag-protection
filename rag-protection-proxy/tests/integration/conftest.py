"""Shared fixtures for integration tests (v1 P2)."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import httpx
import pytest
from fastapi.testclient import TestClient

from rag_protection_proxy.app import app
from rag_protection_proxy.audit import reset_for_tests

CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"
ADMIN_KEY = "test-admin-key"


def configure_backend_env(data_dir: Path, backend: str, monkeypatch: pytest.MonkeyPatch) -> None:
    reset_for_tests()
    monkeypatch.setenv("RAG_DATA_DIR", str(data_dir))
    monkeypatch.setenv("RAG_POLICY_FILE", str(CONFIG_DIR / "policy.yaml"))
    monkeypatch.setenv("RAG_ACL_FILE", str(CONFIG_DIR / "acl_policy.yaml"))
    monkeypatch.setenv("RAG_SAMPLE_DOCS", str(CONFIG_DIR / "sample_documents.json"))
    monkeypatch.setenv("RAG_ADMIN_API_KEY", ADMIN_KEY)
    monkeypatch.setenv("RAG_STORE_BACKEND", backend)
    if backend == "vector":
        monkeypatch.setenv("RAG_QDRANT_URL", ":memory:")
        monkeypatch.setenv("RAG_QDRANT_COLLECTION", f"integration-{data_dir.name}")
        monkeypatch.setenv("RAG_EMBEDDING_BACKEND", "hash")
    if backend == "hybrid":
        monkeypatch.setenv("RAG_QDRANT_URL", ":memory:")
        monkeypatch.setenv("RAG_QDRANT_COLLECTION", f"integration-hybrid-{data_dir.name}")
        monkeypatch.setenv("RAG_EMBEDDING_BACKEND", "hash")


@contextmanager
def backend_client(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    backend: str,
) -> Iterator[TestClient]:
    data_dir = tmp_path / backend
    configure_backend_env(data_dir, backend, monkeypatch)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def live_base_url() -> str:
    return os.getenv("RAG_BASE_URL", "http://localhost:8090").rstrip("/")


@pytest.fixture
def live_stack_available(live_base_url: str) -> str:
    if os.getenv("RUN_INTEGRATION", "").strip().lower() not in {"1", "true", "yes"}:
        pytest.skip("Set RUN_INTEGRATION=1 to run live-stack integration tests")
    try:
        resp = httpx.get(f"{live_base_url}/health", timeout=5.0)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        pytest.skip(f"Live stack unavailable at {live_base_url}: {exc}")
    return live_base_url
