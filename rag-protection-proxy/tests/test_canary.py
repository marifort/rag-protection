"""Lab 10 — canary / honeypot document tripwire.

Unit coverage for the trap + registry, plus an end-to-end check that a retrieved
canary is scrubbed from the response and recorded as ``canary_triggered``.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from rag_protection_proxy.app import app
from rag_protection_proxy.config import CanaryPolicy
from rag_protection_proxy.guardrails.canary import (
    CANARY_GROUP,
    filter_canaries,
    generate_canary_token,
    inspect_candidates,
    is_authorized_auditor,
    list_canaries,
    seed_canary,
)
from rag_protection_proxy.store import DocumentStore, StoredChunk

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
ADMIN_KEY = "test-admin-key"


class _Auth:
    def __init__(self, subject, groups, tenant_id="default"):
        self.subject = subject
        self.groups = groups
        self.tenant_id = tenant_id


def _canary_chunk(metadata=None):
    return StoredChunk(
        chunk_id="canary-abc::0",
        document_id="canary-abc",
        title="2099 Executive Comp — DO NOT DISTRIBUTE",
        text="bait",
        allowed_groups=[CANARY_GROUP],
        score=1.0,
        metadata=metadata if metadata is not None else {"canary": True, "canary_token": "RAGCANARY-x"},
    )


def _plain_chunk():
    return StoredChunk(
        chunk_id="doc-1::0",
        document_id="doc-1",
        title="Handbook",
        text="normal",
        allowed_groups=["all-staff"],
        score=0.5,
        metadata={},
    )


def test_generate_canary_token_unique():
    assert generate_canary_token() != generate_canary_token()


def test_seed_and_list_canary(tmp_path):
    store = DocumentStore(tmp_path / "docs.db")
    record = seed_canary(store, title="Restricted Comp Sheet")
    assert record["document_id"].startswith("canary-")
    assert record["allowed_groups"] == [CANARY_GROUP]
    listed = list_canaries(store)
    assert len(listed) == 1
    assert listed[0]["canary_token"] == record["canary_token"]


def test_inspect_candidates_disabled_returns_none():
    policy = CanaryPolicy(enabled=False)
    auth = _Auth("alice", ["engineering"])
    assert inspect_candidates([_canary_chunk()], auth, policy) is None


def test_inspect_candidates_trips_for_non_auditor():
    policy = CanaryPolicy(enabled=True)
    auth = _Auth("alice", ["engineering"])
    hit = inspect_candidates([_plain_chunk(), _canary_chunk()], auth, policy)
    assert hit is not None
    assert hit.document_id == "canary-abc"
    assert hit.stage == "retrieval"


def test_auditor_bypasses_trap():
    policy = CanaryPolicy(enabled=True, auditor_subjects=["security-bot"])
    auth = _Auth("security-bot", ["engineering"])
    assert is_authorized_auditor(auth, policy) is True
    assert inspect_candidates([_canary_chunk()], auth, policy) is None


def test_auditor_group_bypasses_trap():
    policy = CanaryPolicy(enabled=True, auditor_groups=["canary-admin"])
    auth = _Auth("alice", ["engineering", "canary-admin"])
    assert inspect_candidates([_canary_chunk()], auth, policy) is None


def test_filter_canaries_drops_marked_chunks():
    filtered = filter_canaries([_plain_chunk(), _canary_chunk()])
    assert len(filtered) == 1
    assert filtered[0].document_id == "doc-1"


@pytest.fixture
def client(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setenv("RAG_DATA_DIR", str(data_dir))
    monkeypatch.setenv("RAG_POLICY_FILE", str(CONFIG_DIR / "policy.yaml"))
    monkeypatch.setenv("RAG_ACL_FILE", str(CONFIG_DIR / "acl_policy.yaml"))
    monkeypatch.setenv("RAG_SAMPLE_DOCS", str(CONFIG_DIR / "sample_documents.json"))
    monkeypatch.setenv("RAG_ADMIN_API_KEY", ADMIN_KEY)
    monkeypatch.setenv("RAG_CANARY_ENABLED", "1")
    with TestClient(app) as test_client:
        yield test_client


def test_canary_seed_requires_title(client: TestClient):
    resp = client.post(
        "/admin/canary/seed",
        headers={"Authorization": f"Bearer {ADMIN_KEY}"},
        json={},
    )
    assert resp.status_code == 422


def test_retrieved_canary_scrubbed_and_recorded(client: TestClient):
    # Reachable honeypot: seed with a group the employee holds + distinctive tokens
    # unlikely to collide with the sample corpus, so only the canary matches.
    seed = client.post(
        "/admin/canary/seed",
        headers={"Authorization": f"Bearer {ADMIN_KEY}"},
        json={
            "title": "Zephyr Phantom Ledger",
            "body": "zephyrphantom ledger quokka canary marker xyzzyq",
            "allowed_groups": ["engineering"],
        },
    )
    assert seed.status_code == 200
    canary_doc_id = seed.json()["document_id"]

    resp = client.post(
        "/v1/query",
        headers={"Authorization": "Bearer employee-demo-token"},
        json={"query": "zephyrphantom quokka xyzzyq ledger", "top_k": 4},
    )
    assert resp.status_code == 200
    body = resp.json()

    # The canary must never be returned in the response chunk set.
    assert all(c["document_id"] != canary_doc_id for c in body.get("chunks", []))

    # A canary_triggered event must have been recorded.
    events = client.get(
        "/admin/audit/events",
        headers={"Authorization": f"Bearer {ADMIN_KEY}"},
        params={"kind": "canary_triggered"},
    )
    assert events.status_code == 200
    payload = events.json()
    assert payload["total"] >= 1
    assert payload["events"][0]["decision"] == "block"


def test_retire_canary(client: TestClient):
    seed = client.post(
        "/admin/canary/seed",
        headers={"Authorization": f"Bearer {ADMIN_KEY}"},
        json={"title": "Retire Me"},
    )
    doc_id = seed.json()["document_id"]
    resp = client.post(
        "/admin/canary/retire",
        headers={"Authorization": f"Bearer {ADMIN_KEY}"},
        json={"document_id": doc_id},
    )
    assert resp.status_code == 200
    assert resp.json()["retired"] is True

    listed = client.get(
        "/admin/canary/list",
        headers={"Authorization": f"Bearer {ADMIN_KEY}"},
    )
    assert all(c["document_id"] != doc_id for c in listed.json()["canaries"])


def test_retire_rejects_non_canary_document(client: TestClient):
    """canary/retire must not delete ordinary documents (no backdoor purge)."""
    ingest = client.post(
        "/v1/ingest",
        headers={"Authorization": f"Bearer {ADMIN_KEY}"},
        json={
            "document_id": "regular-doc",
            "title": "Regular",
            "content": "Ordinary engineering notes.",
            "allowed_groups": ["engineering"],
        },
    )
    assert ingest.status_code == 200
    resp = client.post(
        "/admin/canary/retire",
        headers={"Authorization": f"Bearer {ADMIN_KEY}"},
        json={"document_id": "regular-doc"},
    )
    assert resp.status_code == 404
    # Document survives the failed retire.
    visible = client.get(
        "/v1/documents",
        headers={"Authorization": "Bearer employee-demo-token"},
    )
    ids = {doc["document_id"] for doc in visible.json()["documents"]}
    assert "regular-doc" in ids


def test_generic_delete_refuses_canary(client: TestClient):
    """DELETE /v1/documents/{id} must not remove tripwires — use canary/retire."""
    seed = client.post(
        "/admin/canary/seed",
        headers={"Authorization": f"Bearer {ADMIN_KEY}"},
        json={"title": "Protected Tripwire"},
    )
    doc_id = seed.json()["document_id"]
    resp = client.delete(
        f"/v1/documents/{doc_id}",
        headers={"Authorization": f"Bearer {ADMIN_KEY}"},
    )
    assert resp.status_code == 409
    listed = client.get(
        "/admin/canary/list",
        headers={"Authorization": f"Bearer {ADMIN_KEY}"},
    )
    assert any(c["document_id"] == doc_id for c in listed.json()["canaries"])
