"""Integration tests against in-process TestClient (optional live proxy)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from redteam.runner import run_scenario
from redteam.scenario import load_scenario

REPO_ROOT = Path(__file__).resolve().parents[3]
PROXY_DIR = REPO_ROOT / "rag-protection-proxy"
CONFIG_DIR = PROXY_DIR / "config"
ADMIN_KEY = "rag-admin-demo-key"

sys.path.insert(0, str(PROXY_DIR))


@pytest.fixture()
def proxy_client(tmp_path, monkeypatch):
    monkeypatch.setenv("RAG_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("RAG_POLICY_FILE", str(CONFIG_DIR / "policy.yaml"))
    monkeypatch.setenv("RAG_ACL_FILE", str(CONFIG_DIR / "acl_policy.yaml"))
    monkeypatch.setenv("RAG_TOOL_POLICY_FILE", str(CONFIG_DIR / "tool_policy.yaml"))
    monkeypatch.setenv("RAG_SAMPLE_DOCS", str(CONFIG_DIR / "sample_documents.json"))
    monkeypatch.setenv("RAG_ADMIN_API_KEY", ADMIN_KEY)
    monkeypatch.setenv("RAG_EMBEDDING_BACKEND", "hash")
    from rag_protection_proxy.app import app

    with TestClient(app) as client:
        yield client


class _TestClientAdapter:
    """Minimal adapter so runner code can use TestClient in integration tests."""

    def __init__(self, client: TestClient) -> None:
        self._client = client

    def health(self):
        resp = self._client.get("/health")
        assert resp.status_code == 200
        return resp.json()

    def ingest(self, document_id, title, content, *, allowed_groups=None, tenant_id="default"):
        resp = self._client.post(
            "/v1/ingest",
            headers={"Authorization": f"Bearer {ADMIN_KEY}"},
            params={"tenant_id": tenant_id},
            json={
                "document_id": document_id,
                "title": title,
                "content": content,
                "allowed_groups": allowed_groups or ["all-staff"],
                "metadata": {},
            },
        )
        if resp.status_code == 422:
            body = resp.json()
            detail = body.get("detail")
            if isinstance(detail, dict):
                return {"status": "rejected", **detail}
        assert resp.status_code == 200, resp.text
        return resp.json()

    def query(self, query, *, token, top_k=4, include_audit=False):
        resp = self._client.post(
            "/v1/query",
            headers={"Authorization": f"Bearer {token}"},
            json={"query": query, "top_k": top_k, "include_audit": include_audit},
        )
        assert resp.status_code == 200, resp.text
        return resp.json()

    def export_audit(self, *, limit=1000, scrub=None):
        params = {"limit": str(limit)}
        if scrub is not None:
            params["scrub"] = "true" if scrub else "false"
        resp = self._client.get(
            "/admin/audit/export",
            headers={"Authorization": f"Bearer {ADMIN_KEY}"},
            params=params,
        )
        assert resp.status_code == 200
        return resp.text


@pytest.mark.integration
@pytest.mark.parametrize(
    "scenario_id",
    ["acl_bypass_attempt", "indirect_injection_ticket"],
)
def test_scenario_passes_on_demo_stack(proxy_client, scenario_id: str) -> None:
    adapter = _TestClientAdapter(proxy_client)
    path = Path(__file__).resolve().parents[1] / "scenarios" / f"{scenario_id}.yaml"
    scenario = load_scenario(path)
    result = run_scenario(adapter, scenario)
    assert result.passed, result.messages
