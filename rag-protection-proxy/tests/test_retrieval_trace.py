"""Retrieval-decision explainability trace (T0.7 / master list #11)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from rag_protection_proxy.app import app
from rag_protection_proxy.audit import recent, reset_for_tests
from rag_protection_proxy.config import Policy, RetrievalPolicy
from rag_protection_proxy.retrieval_trace import explain_search, record_retrieval_trace
from rag_protection_proxy.store import DocumentStore

CONFIG_DIR = __import__("pathlib").Path(__file__).resolve().parent.parent / "config"
ADMIN_KEY = "test-admin-key"


@pytest.fixture(autouse=True)
def _clean():
    reset_for_tests()
    yield
    reset_for_tests()


def test_search_with_trace_acl_exclusion(tmp_path):
    store = DocumentStore(tmp_path / "docs.db")
    store.ingest("public-faq", "FAQ", "Support hours Monday through Friday.", ["all-staff"])
    store.ingest("hr-payroll", "Payroll", "Confidential payroll total 4.2M.", ["hr"])

    chunks, trace = store.search_with_trace(
        "payroll confidential total",
        ["engineering", "all-staff"],
        top_k=2,
    )
    outcomes = {row.document_id: row.outcome for row in trace}
    assert outcomes.get("hr-payroll") == "excluded_acl"
    assert all(chunk.document_id != "hr-payroll" for chunk in chunks)


def test_search_with_trace_quarantine_exclusion(tmp_path):
    store = DocumentStore(tmp_path / "docs.db")
    store.ingest(
        "quarantined-doc",
        "Quarantined",
        "secret material",
        ["all-staff"],
        metadata={"status": "quarantined"},
    )
    _, trace = store.search_with_trace("secret material", ["all-staff"], top_k=2)
    assert any(row.outcome == "excluded_quarantine" for row in trace)


def test_record_retrieval_trace_emits_audit_kind():
    from rag_protection_proxy.models import RetrievalDecision

    record_retrieval_trace(
        subject="alice",
        tenant_id="default",
        query="payroll policy",
        decisions=[
            RetrievalDecision(
                chunk_id="doc::0",
                document_id="doc",
                title="Handbook",
                score=0.8,
                outcome="selected",
                detail="top_4 by score",
            )
        ],
    )
    events = recent(5)
    assert any(event.kind == "retrieval_trace" for event in events)
    payload = json.loads(events[0].detail)
    assert payload["selected"] == 1


def test_query_returns_retrieval_trace_when_requested(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setenv("RAG_DATA_DIR", str(data_dir))
    monkeypatch.setenv("RAG_POLICY_FILE", str(CONFIG_DIR / "policy.yaml"))
    monkeypatch.setenv("RAG_ACL_FILE", str(CONFIG_DIR / "acl_policy.yaml"))
    monkeypatch.setenv("RAG_SAMPLE_DOCS", str(CONFIG_DIR / "sample_documents.json"))
    monkeypatch.setenv("RAG_ADMIN_API_KEY", ADMIN_KEY)

    with TestClient(app) as client:
        ingest = client.post(
            "/v1/ingest",
            headers={"Authorization": f"Bearer {ADMIN_KEY}"},
            json={
                "document_id": "trace-faq",
                "title": "Support FAQ",
                "content": "Support is available Monday through Friday, 9am to 6pm Eastern.",
                "allowed_groups": ["engineering", "all-staff"],
            },
        )
        assert ingest.status_code == 200

        with patch(
            "rag_protection_proxy.pipeline.LLMClient.chat",
            new=AsyncMock(
                return_value="Support hours are Monday through Friday, 9am to 6pm Eastern."
            ),
        ):
            resp = client.post(
                "/v1/query",
                headers={"Authorization": "Bearer employee-demo-token"},
                json={"query": "support hours weekdays", "include_retrieval_trace": True},
            )
    assert resp.status_code == 200
    body = resp.json()
    assert body["retrieval_trace"]
    assert any(row["outcome"] == "selected" for row in body["retrieval_trace"])


def test_query_omits_retrieval_trace_without_request_flag(tmp_path, monkeypatch):
    """Policy explainability_enabled audits traces but must not force them onto the response."""
    data_dir = tmp_path / "data"
    monkeypatch.setenv("RAG_DATA_DIR", str(data_dir))
    monkeypatch.setenv("RAG_POLICY_FILE", str(CONFIG_DIR / "policy.yaml"))
    monkeypatch.setenv("RAG_ACL_FILE", str(CONFIG_DIR / "acl_policy.yaml"))
    monkeypatch.setenv("RAG_SAMPLE_DOCS", str(CONFIG_DIR / "sample_documents.json"))
    monkeypatch.setenv("RAG_ADMIN_API_KEY", ADMIN_KEY)

    with TestClient(app) as client:
        with patch(
            "rag_protection_proxy.pipeline.LLMClient.chat",
            new=AsyncMock(return_value="Support hours are weekdays."),
        ):
            resp = client.post(
                "/v1/query",
                headers={"Authorization": "Bearer employee-demo-token"},
                json={"query": "support hours weekdays", "include_retrieval_trace": False},
            )
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("retrieval_trace") == []
    assert any(event.kind == "retrieval_trace" for event in recent(20))


def test_explain_search_respects_policy_flag(tmp_path):
    store = DocumentStore(tmp_path / "docs.db")
    store.ingest("doc", "Doc", "alpha beta gamma delta", ["all-staff"])
    rules = RetrievalPolicy(explainability_enabled=True, max_trace_candidates=10)
    chunks, trace = explain_search(store, "alpha beta", ["all-staff"], top_k=1, rules=rules)
    assert chunks
    assert trace
