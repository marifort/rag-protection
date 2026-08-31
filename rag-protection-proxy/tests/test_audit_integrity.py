"""Tamper-evident audit hash chain (T0.4 / master list #9)."""

from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient

from rag_protection_proxy import audit_integrity
from rag_protection_proxy.app import app
from rag_protection_proxy.audit import (
    configure_audit,
    configure_audit_policy,
    record,
    reset_for_tests,
    verify_audit_integrity,
)
from rag_protection_proxy.models import AuditEvent, Decision

ADMIN_KEY = "test-admin-key"


@pytest.fixture(autouse=True)
def _clean():
    reset_for_tests()
    yield
    reset_for_tests()


def _event(kind: str = "scan_input") -> AuditEvent:
    return AuditEvent(
        timestamp=time.time(),
        kind=kind,
        decision=Decision.ALLOW,
        risk_score=0.1,
        source="test",
    )


def test_append_chain_fields_links_events():
    audit_integrity.configure_integrity_chain(enabled=True)
    first = audit_integrity.append_chain_fields({"kind": "a", "decision": "allow"})
    second = audit_integrity.append_chain_fields({"kind": "b", "decision": "block"})
    assert first["prev_hash"] == audit_integrity.GENESIS_HASH
    assert second["prev_hash"] == first["event_hash"]


def test_record_writes_chained_jsonl(tmp_path, monkeypatch):
    audit_file = tmp_path / "audit.jsonl"
    monkeypatch.setenv("RAG_AUDIT_FILE", str(audit_file))
    configure_audit()
    configure_audit_policy(integrity_chain=True)

    record(_event("scan_input"))
    record(_event("query_completed"))

    lines = [json.loads(line) for line in audit_file.read_text().strip().splitlines()]
    assert len(lines) == 2
    assert lines[0]["prev_hash"] == audit_integrity.GENESIS_HASH
    assert lines[1]["prev_hash"] == lines[0]["event_hash"]
    assert (tmp_path / "audit.jsonl.chain").is_file()


def test_verify_audit_file_valid_chain(tmp_path, monkeypatch):
    audit_file = tmp_path / "audit.jsonl"
    monkeypatch.setenv("RAG_AUDIT_FILE", str(audit_file))
    configure_audit()
    configure_audit_policy(integrity_chain=True)
    record(_event())
    record(_event())

    result = verify_audit_integrity()
    assert result["valid"] is True
    assert result["events_checked"] == 2
    assert result["integrity_chain_enabled"] is True


def test_verify_detects_tampered_line(tmp_path, monkeypatch):
    audit_file = tmp_path / "audit.jsonl"
    monkeypatch.setenv("RAG_AUDIT_FILE", str(audit_file))
    configure_audit()
    configure_audit_policy(integrity_chain=True)
    record(_event())
    record(_event())

    lines = audit_file.read_text().strip().splitlines()
    payload = json.loads(lines[0])
    payload["detail"] = "tampered"
    audit_file.write_text(json.dumps(payload) + "\n" + lines[1] + "\n", encoding="utf-8")

    result = verify_audit_integrity()
    assert result["valid"] is False
    assert result["error"] == "event_hash mismatch"


def test_admin_integrity_verify_endpoint(tmp_path, monkeypatch):
    audit_file = tmp_path / "audit.jsonl"
    data_dir = tmp_path / "data"
    monkeypatch.setenv("RAG_AUDIT_FILE", str(audit_file))
    monkeypatch.setenv("RAG_DATA_DIR", str(data_dir))
    monkeypatch.setenv("RAG_POLICY_FILE", str(__import__("pathlib").Path(__file__).resolve().parent.parent / "config" / "policy.yaml"))
    monkeypatch.setenv("RAG_ACL_FILE", str(__import__("pathlib").Path(__file__).resolve().parent.parent / "config" / "acl_policy.yaml"))
    monkeypatch.setenv("RAG_SAMPLE_DOCS", str(__import__("pathlib").Path(__file__).resolve().parent.parent / "config" / "sample_documents.json"))
    monkeypatch.setenv("RAG_ADMIN_API_KEY", ADMIN_KEY)
    configure_audit()
    configure_audit_policy(integrity_chain=True)
    record(_event())

    with TestClient(app) as client:
        resp = client.get(
            "/admin/audit/integrity/verify",
            headers={"Authorization": f"Bearer {ADMIN_KEY}"},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is True
    assert body["events_checked"] == 1


def test_rotation_resets_chain_to_genesis(tmp_path, monkeypatch):
    from rag_protection_proxy import audit as audit_mod

    audit_file = tmp_path / "audit.jsonl"
    monkeypatch.setenv("RAG_AUDIT_FILE", str(audit_file))
    configure_audit()
    configure_audit_policy(integrity_chain=True)
    record(_event("scan_input"))
    record(_event("query_completed"))
    assert verify_audit_integrity()["valid"] is True

    marker = audit_file.parent / f"{audit_file.name}.rotation"
    marker.write_text("20000101", encoding="utf-8")
    audit_mod._maybe_rotate_audit_file()

    assert audit_file.read_text(encoding="utf-8").strip() == ""
    assert audit_integrity.chain_tip() == audit_integrity.GENESIS_HASH

    record(_event("after_rotate"))
    lines = [json.loads(line) for line in audit_file.read_text().strip().splitlines()]
    assert lines[0]["prev_hash"] == audit_integrity.GENESIS_HASH
    assert verify_audit_integrity()["valid"] is True


def test_load_chain_tip_heals_non_genesis_segment(tmp_path, monkeypatch):
    audit_file = tmp_path / "audit.jsonl"
    monkeypatch.setenv("RAG_AUDIT_FILE", str(audit_file))
    configure_audit()
    configure_audit_policy(integrity_chain=True)
    record(_event())
    record(_event())

    # Simulate legacy rotation: keep chained events but drop the genesis-rooted prefix.
    lines = audit_file.read_text().strip().splitlines()
    audit_file.write_text(lines[1] + "\n", encoding="utf-8")
    assert verify_audit_integrity()["valid"] is False
    assert verify_audit_integrity()["error"] == "prev_hash mismatch"

    audit_integrity.load_chain_tip(audit_file)
    result = verify_audit_integrity()
    assert result["valid"] is True
    assert result["events_checked"] == 1
    first = json.loads(audit_file.read_text().strip().splitlines()[0])
    assert first["prev_hash"] == audit_integrity.GENESIS_HASH


def test_retention_prune_rechains_kept_events(tmp_path, monkeypatch):
    from rag_protection_proxy import audit as audit_mod

    audit_file = tmp_path / "audit.jsonl"
    monkeypatch.setenv("RAG_AUDIT_FILE", str(audit_file))
    configure_audit()
    configure_audit_policy(integrity_chain=True, retention_days=7)

    old = _event("old").model_copy(update={"timestamp": time.time() - (10 * 86400)})
    record(old)
    record(_event("new"))

    removed = audit_mod.apply_retention()
    assert removed >= 1
    result = verify_audit_integrity()
    assert result["valid"] is True
    first = json.loads(audit_file.read_text().strip().splitlines()[0])
    assert first["prev_hash"] == audit_integrity.GENESIS_HASH
    assert first["kind"] == "new"
