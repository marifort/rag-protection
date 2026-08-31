"""CE/EE plugin seam tests — Community Edition (no enterprise package required).

These tests guard the optional-install boundary between ``rag-protection-proxy`` (CE)
and ``rag-protection-enterprise`` (EE). They assert that a CE-only install does not
expose EE routes, health fields, or store backends.

**When they run**

- **CE-only** (public CI, ``pip install -e .`` without EE): all ``@_ce_only`` tests execute.
- **CE + EE** (local dev via ``tools/dev_install_ee.sh``): the ``@_ce_only`` tests are skipped
  because ``app.state.enterprise_registered`` is already ``True``.
  ``test_pgvector_requires_enterprise`` always runs — it simulates a missing EE wheel.

**Fixture**

``client`` starts the FastAPI lifespan (``with TestClient(app)``) and points config
at the repo ``config/`` tree so ``app.state.acl`` and policy are loaded before requests.

See also: ``docs/qa/test-plans/CE_EE_SEAM_TEST_PLAN.md`` (TC-CEEE-001–008).
See also: ``docs/commercial/CE_EE_PLUGIN_SEAMS.md`` (Validation → Test cases).
"""

from __future__ import annotations

import builtins
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from rag_protection_proxy.app import app
from rag_protection_proxy.store import create_document_store

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
ADMIN_KEY = "test-admin-key"

_ENTERPRISE_INSTALLED = getattr(app.state, "enterprise_registered", False)
_ce_only = pytest.mark.skipif(
    _ENTERPRISE_INSTALLED,
    reason="rag-protection-enterprise is installed — CE-only seam test",
)


@pytest.fixture
def client(tmp_path, monkeypatch) -> TestClient:
    data_dir = tmp_path / "data"
    monkeypatch.setenv("RAG_DATA_DIR", str(data_dir))
    monkeypatch.setenv("RAG_POLICY_FILE", str(CONFIG_DIR / "policy.yaml"))
    monkeypatch.setenv("RAG_ACL_FILE", str(CONFIG_DIR / "acl_policy.yaml"))
    monkeypatch.setenv("RAG_SAMPLE_DOCS", str(CONFIG_DIR / "sample_documents.json"))
    monkeypatch.setenv("RAG_ADMIN_API_KEY", ADMIN_KEY)
    with TestClient(app) as test_client:
        yield test_client


@_ce_only
def test_enterprise_not_registered_in_ce_only_install():
    """``register_enterprise()`` did not run at import time (no EE wheel on PYTHONPATH)."""
    assert getattr(app.state, "enterprise_registered", False) is False


@_ce_only
def test_connector_routes_absent_without_enterprise(client: TestClient):
    """Connector admin API is not mounted — EE-only ``/admin/connectors/*`` returns 404."""
    resp = client.get(
        "/admin/connectors/status",
        headers={"Authorization": "Bearer rag-admin-demo-key"},
    )
    assert resp.status_code == 404


@_ce_only
def test_health_ce_only_shape(client: TestClient):
    """``GET /health`` omits EE-only fields (``enterprise_installed``, Drive OAuth, etc.)."""
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("enterprise_installed") is False
    assert "google_drive_oauth" not in body
    assert "policy_version" in body


@_ce_only
@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/admin/challenges"),
        ("GET", "/admin/documents/quarantined"),
        ("GET", "/admin/policy-config"),
        ("PATCH", "/admin/policy-knobs"),
        ("GET", "/admin/policy-backups"),
        ("POST", "/admin/policy/preview-patterns"),
        ("GET", "/admin/tenants"),
        ("GET", "/admin/documents/test-id/inspect"),
        ("GET", "/admin/auth/oidc/login/start"),
        ("GET", "/admin/auth/oidc/login/status"),
    ],
)
def test_tier2_routes_absent_without_enterprise(client: TestClient, method: str, path: str):
    """Tier 2 operator admin routes are not mounted in CE-only installs (404)."""
    headers = {"Authorization": "Bearer rag-admin-demo-key"}
    if method == "GET":
        resp = client.get(path, headers=headers)
    elif method == "PATCH":
        resp = client.patch(path, headers=headers, json={"input_challenge_threshold": 0.5})
    else:
        resp = client.post(path, headers=headers, json={"sample_text": "test"})
    assert resp.status_code == 404


@_ce_only
def test_health_omits_oidc_ui_login_without_enterprise(client: TestClient):
    """OIDC UI Sign-in availability is an EE health field."""
    body = client.get("/health").json()
    assert "oidc_ui_login_available" not in body


def test_pgvector_requires_enterprise(monkeypatch, tmp_path):
    """``RAG_STORE_BACKEND=pgvector`` without EE raises ``ImportError`` with install hint."""
    monkeypatch.setenv("RAG_STORE_BACKEND", "pgvector")
    real_import = builtins.__import__

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "rag_protection_enterprise.store_backends" or (
            name == "rag_protection_enterprise"
            and fromlist
            and "store_backends" in fromlist
        ):
            raise ImportError("simulated missing EE package")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    with pytest.raises(ImportError, match="rag-protection-enterprise"):
        create_document_store(tmp_path / "data")
