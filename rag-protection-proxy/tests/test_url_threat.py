"""Tests for URL threat scanner and network.denied_domains policy wiring.

``PATCH /admin/policy-knobs`` persist test uses ``@ee_required`` (Tier 2 route).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from rag_protection_proxy.app import app
from rag_protection_proxy.config import load_policy
from rag_protection_proxy.guardrails.input_pipeline import scan_input
from rag_protection_proxy.models import InputScanRequest
from rag_protection_proxy.scanners.url_threat import URLThreatScanner

from tests.conftest import ee_required

CONFIG_DIR = __import__("pathlib").Path(__file__).resolve().parent.parent / "config"
ADMIN_KEY = "test-admin-key"


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("RAG_ADMIN_API_KEY", ADMIN_KEY)
    monkeypatch.setenv("RAG_POLICY_FILE", str(CONFIG_DIR / "policy.yaml"))
    monkeypatch.setenv("RAG_ACL_FILE", str(CONFIG_DIR / "acl_policy.yaml"))
    with TestClient(app) as test_client:
        yield test_client


def _auth():
    return {"Authorization": f"Bearer {ADMIN_KEY}"}


def test_url_threat_denied_domain_direct():
    scanner = URLThreatScanner(denylist=["evil.example"])
    result = scanner.scan("Visit http://evil.example/phish for details.")
    assert any(f.category == "denied_domain" for f in result.findings)
    assert result.findings[0].severity == 0.9


def test_url_threat_denied_subdomain_matches():
    scanner = URLThreatScanner(denylist=["evil.example"])
    result = scanner.scan("See https://sub.evil.example/path")
    assert any(f.category == "denied_domain" for f in result.findings)


def test_scan_input_flags_denied_domain_from_policy(tmp_path):
    policy_file = tmp_path / "policy.yaml"
    base = (CONFIG_DIR / "policy.yaml").read_text(encoding="utf-8")
    policy_file.write_text(
        base.replace(
            "denied_domains: []",
            "denied_domains:\n  - evil.example",
        ),
        encoding="utf-8",
    )
    policy = load_policy(str(policy_file))
    resp = scan_input(
        InputScanRequest(text="Open http://evil.example/login now", source="test"),
        policy,
    )
    assert any(
        f.scanner == "url_threat" and f.category == "denied_domain"
        for f in resp.verdict.findings
    )


@ee_required
def test_patch_policy_knobs_persists_denied_domains(client: TestClient, tmp_path, monkeypatch):
    policy_file = tmp_path / "policy.yaml"
    policy_file.write_text((CONFIG_DIR / "policy.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setenv("RAG_POLICY_FILE", str(policy_file))
    monkeypatch.setenv("RAG_POLICY_WRITABLE_FILE", str(policy_file))

    resp = client.patch(
        "/admin/policy-knobs",
        headers=_auth(),
        json={"network_denied_domains": ["evil.example", "phish.test"]},
    )
    assert resp.status_code == 200
    assert "network_denied_domains" in resp.json()["updated"]

    config = client.get("/admin/policy-config", headers=_auth()).json()
    assert "evil.example" in config["summary"]["network_denied_domains"]
    denied = (config.get("raw_policy") or {}).get("network", {}).get("denied_domains", [])
    assert "evil.example" in denied
    assert "phish.test" in denied

    written_path = config.get("policy_file")
    if written_path:
        reloaded = load_policy(written_path)
        assert "evil.example" in reloaded.network.denied_domains
