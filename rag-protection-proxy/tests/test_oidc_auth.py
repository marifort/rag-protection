import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from rag_protection_proxy.acl import resolve_auth
from rag_protection_proxy.config import ACLPolicy, DemoUser, OIDCConfig


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
def oidc_acl(rsa_keys, monkeypatch) -> ACLPolicy:
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
        demo_users=[DemoUser(token="employee-demo-token", subject="alice", groups=["engineering"])],
        oidc=OIDCConfig(
            enabled=True,
            issuer="https://login.example.com",
            audience="rag-protection-api",
            jwks_uri="https://login.example.com/.well-known/jwks.json",
            algorithms=["RS256"],
            groups_claim="groups",
            roles_claim="roles",
        ),
    )


def test_hs256_jwt_resolves_groups():
    acl = ACLPolicy(
        jwt_secret="test-secret",
        jwt_algorithms=["HS256"],
        jwt_groups_claim="groups",
    )
    token = jwt.encode(
        {"sub": "bob.hr", "groups": ["hr", "all-staff"]},
        "test-secret",
        algorithm="HS256",
    )
    ctx = resolve_auth(f"Bearer {token}", acl)
    assert ctx is not None
    assert ctx.subject == "bob.hr"
    assert ctx.auth_method == "jwt"
    assert "hr" in ctx.groups


def test_oidc_jwt_resolves_groups(oidc_acl: ACLPolicy, rsa_keys):
    private_pem, _ = rsa_keys
    token = jwt.encode(
        {
            "sub": "carol.exec@example.com",
            "iss": "https://login.example.com",
            "aud": "rag-protection-api",
            "groups": ["executives"],
            "exp": int(time.time()) + 3600,
        },
        private_pem,
        algorithm="RS256",
    )
    ctx = resolve_auth(f"Bearer {token}", oidc_acl)
    assert ctx is not None
    assert ctx.auth_method == "oidc"
    assert ctx.subject == "carol.exec@example.com"
    assert "executives" in ctx.groups


def test_oidc_jwt_exposes_email_claim(oidc_acl: ACLPolicy, rsa_keys):
    private_pem, _ = rsa_keys
    token = jwt.encode(
        {
            "sub": "auth0|abc123",
            "email": "marina@example.com",
            "iss": "https://login.example.com",
            "aud": "rag-protection-api",
            "groups": ["engineering"],
            "exp": int(time.time()) + 3600,
        },
        private_pem,
        algorithm="RS256",
    )
    ctx = resolve_auth(f"Bearer {token}", oidc_acl)
    assert ctx is not None
    assert ctx.subject == "auth0|abc123"
    assert ctx.email == "marina@example.com"
    assert "engineering" in ctx.groups


def test_oidc_jwt_exposes_namespaced_email_claim(oidc_acl: ACLPolicy, rsa_keys):
    private_pem, _ = rsa_keys
    token = jwt.encode(
        {
            "sub": "auth0|xyz",
            "https://rag-protection.local/email": "serguei@example.com",
            "iss": "https://login.example.com",
            "aud": "rag-protection-api",
            "groups": ["hr"],
            "exp": int(time.time()) + 3600,
        },
        private_pem,
        algorithm="RS256",
    )
    ctx = resolve_auth(f"Bearer {token}", oidc_acl)
    assert ctx is not None
    assert ctx.email == "serguei@example.com"


def test_oidc_roles_claim_fallback(oidc_acl: ACLPolicy, rsa_keys, monkeypatch):
    private_pem, _ = rsa_keys
    oidc_acl_roles = ACLPolicy(
        oidc=OIDCConfig(
            enabled=True,
            issuer="https://login.example.com",
            audience="rag-protection-api",
            jwks_uri="https://login.example.com/.well-known/jwks.json",
            algorithms=["RS256"],
            groups_claim="groups",
            roles_claim="roles",
        )
    )

    class FakeJWKClient:
        def get_signing_key_from_jwt(self, _token):
            class SigningKey:
                key = rsa_keys[1]

            return SigningKey()

    monkeypatch.setattr(
        "rag_protection_proxy.acl._get_jwks_client",
        lambda _uri: FakeJWKClient(),
    )

    token = jwt.encode(
        {
            "sub": "bob.hr",
            "iss": "https://login.example.com",
            "aud": "rag-protection-api",
            "roles": ["hr"],
            "exp": int(time.time()) + 3600,
        },
        private_pem,
        algorithm="RS256",
    )
    ctx = resolve_auth(f"Bearer {token}", oidc_acl_roles)
    assert ctx is not None
    assert ctx.auth_method == "oidc"
    assert "hr" in ctx.groups
