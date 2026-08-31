"""Tests for OIDC/JWT-mapped admin roles and tenant-scoped operator RBAC.

``GET /admin/tenants`` tests use ``@ee_required`` (Tier 2 route).
"""

from __future__ import annotations

import time
from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from rag_protection_proxy.admin_auth import (
    AUDIT_READER,
    INGEST_ADMIN,
    POLICY_ADMIN,
    admin_can_access_tenant,
    resolve_admin,
)
from rag_protection_proxy.app import app
from rag_protection_proxy.config import ACLPolicy, OIDCConfig, load_acl_policy

from tests.conftest import ee_required

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


@pytest.fixture(scope="module")
def rsa_keys():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return private_pem, public_key


@pytest.fixture
def oidc_admin_acl(rsa_keys, monkeypatch) -> ACLPolicy:
    _, public_key = rsa_keys

    class FakeJWKClient:
        def get_signing_key_from_jwt(self, _token):
            class SigningKey:
                key = public_key

            return SigningKey()

    monkeypatch.setattr(
        "rag_protection_proxy.acl._get_jwks_client",
        lambda _uri: FakeJWKClient(),
    )
    return ACLPolicy(
        oidc=OIDCConfig(
            enabled=True,
            issuer="https://login.example.com",
            audience="rag-protection-api",
            jwks_uri="https://login.example.com/.well-known/jwks.json",
            algorithms=["RS256"],
            groups_claim="groups",
            roles_claim="roles",
            tenant_claim="tenant_id",
            admin_role_map={
                POLICY_ADMIN: ["rag-platform-admins"],
                AUDIT_READER: ["rag-soc-readers"],
                INGEST_ADMIN: ["rag-ingest-admins"],
            },
            admin_global_groups=["rag-platform-admins"],
        ),
    )


def _encode_oidc(private_pem, public_key, payload_extra: dict) -> str:
    payload = {
        "sub": "oidc.admin@example.com",
        "iss": "https://login.example.com",
        "aud": "rag-protection-api",
        "exp": int(time.time()) + 3600,
        **payload_extra,
    }
    return jwt.encode(payload, private_pem, algorithm="RS256")


def test_oidc_admin_role_map_grants_audit_reader(oidc_admin_acl, rsa_keys):
    private_pem, _ = rsa_keys
    token = _encode_oidc(private_pem, _, {"groups": ["rag-soc-readers"]})
    admin = resolve_admin(f"Bearer {token}", oidc_admin_acl)
    assert admin is not None
    assert admin.auth_method == "oidc"
    assert AUDIT_READER in admin.roles
    assert POLICY_ADMIN not in admin.roles
    assert admin.tenant_scope is None


def test_oidc_admin_global_group_is_not_tenant_scoped(oidc_admin_acl, rsa_keys):
    private_pem, _ = rsa_keys
    token = _encode_oidc(
        private_pem,
        _,
        {"groups": ["rag-platform-admins"], "tenant_id": "acme"},
    )
    admin = resolve_admin(f"Bearer {token}", oidc_admin_acl)
    assert admin is not None
    assert POLICY_ADMIN in admin.roles
    assert admin.tenant_scope is None


def test_oidc_admin_tenant_scoped_ingest(oidc_admin_acl, rsa_keys):
    private_pem, _ = rsa_keys
    token = _encode_oidc(
        private_pem,
        _,
        {"groups": ["rag-ingest-admins"], "tenant_id": "acme"},
    )
    admin = resolve_admin(f"Bearer {token}", oidc_admin_acl)
    assert admin is not None
    assert INGEST_ADMIN in admin.roles
    assert admin.tenant_scope == "acme"
    assert admin_can_access_tenant(admin, "acme")
    assert not admin_can_access_tenant(admin, "globex")


def test_oidc_token_without_admin_groups_is_not_admin(oidc_admin_acl, rsa_keys):
    private_pem, _ = rsa_keys
    token = _encode_oidc(private_pem, _, {"groups": ["engineering"]})
    assert resolve_admin(f"Bearer {token}", oidc_admin_acl) is None


def test_jwt_admin_role_map(tmp_path, monkeypatch):
    secret = "jwt-admin-secret"
    acl_path = tmp_path / "acl.yaml"
    acl_path.write_text(
        f"""
jwt_secret: "{secret}"
jwt_groups_claim: groups
jwt_tenant_claim: tenant_id
oidc:
  admin_role_map:
    audit_reader: [jwt-audit-team]
  admin_global_groups: []
""",
        encoding="utf-8",
    )
    acl = load_acl_policy(str(acl_path))
    token = jwt.encode(
        {"sub": "jwt.auditor", "groups": ["jwt-audit-team"], "tenant_id": "globex"},
        secret,
        algorithm="HS256",
    )
    admin = resolve_admin(f"Bearer {token}", acl)
    assert admin is not None
    assert admin.auth_method == "jwt"
    assert AUDIT_READER in admin.roles
    assert admin.tenant_scope == "globex"


@pytest.fixture
def tenant_scoped_client(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    acl_file = tmp_path / "acl.yaml"
    acl_file.write_text(
        """
admin_users:
  - token: acme-ingest-admin
    subject: acme.ingest
    tenant_id: acme
    roles: [ingest_admin]
  - token: global-audit
    subject: audit.global
    roles: [audit_reader]
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("RAG_DATA_DIR", str(data_dir))
    monkeypatch.setenv("RAG_POLICY_FILE", str(CONFIG_DIR / "policy.yaml"))
    monkeypatch.setenv("RAG_ACL_FILE", str(acl_file))
    monkeypatch.setenv("RAG_SAMPLE_DOCS", str(CONFIG_DIR / "sample_documents.json"))
    monkeypatch.delenv("RAG_ADMIN_API_KEY", raising=False)
    with TestClient(app) as client:
        yield client


def test_tenant_scoped_admin_cannot_ingest_other_tenant(tenant_scoped_client: TestClient):
    denied = tenant_scoped_client.post(
        "/v1/ingest",
        headers={"Authorization": "Bearer acme-ingest-admin"},
        params={"tenant_id": "globex"},
        json={
            "document_id": "wrong-tenant",
            "title": "Wrong",
            "content": "Should fail.",
            "allowed_groups": ["engineering"],
        },
    )
    assert denied.status_code == 403

    allowed = tenant_scoped_client.post(
        "/v1/ingest",
        headers={"Authorization": "Bearer acme-ingest-admin"},
        params={"tenant_id": "acme"},
        json={
            "document_id": "acme-doc",
            "title": "Acme",
            "content": "Scoped ingest works.",
            "allowed_groups": ["engineering"],
        },
    )
    assert allowed.status_code == 200
    assert allowed.json()["tenant_id"] == "acme"


@ee_required
def test_admin_tenants_endpoint_lists_scope(tenant_scoped_client: TestClient):
    scoped = tenant_scoped_client.get(
        "/admin/tenants",
        headers={"Authorization": "Bearer acme-ingest-admin"},
    )
    assert scoped.status_code == 200
    body = scoped.json()
    assert body["tenant_scope"] == "acme"
    assert body["tenants"] == ["acme"]
    assert body["global_admin"] is False

    global_resp = tenant_scoped_client.get(
        "/admin/tenants",
        headers={"Authorization": "Bearer global-audit"},
    )
    assert global_resp.status_code == 200
    assert global_resp.json()["global_admin"] is True
    assert "default" in global_resp.json()["tenants"]


def test_admin_auth_me_includes_tenant_scope(tenant_scoped_client: TestClient):
    resp = tenant_scoped_client.get(
        "/admin/auth/me",
        headers={"Authorization": "Bearer acme-ingest-admin"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["tenant_scope"] == "acme"
    assert body["global_admin"] is False
    assert body["allowed_tenants"] == ["acme"]
