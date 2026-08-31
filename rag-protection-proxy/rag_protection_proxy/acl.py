"""Identity resolution and document ACL enforcement."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Set

import jwt
from jwt import PyJWKClient

from rag_protection_proxy.config import ACLPolicy, OIDCConfig

_jwks_clients: Dict[str, PyJWKClient] = {}


@dataclass(frozen=True)
class AuthContext:
    subject: str
    groups: List[str]
    auth_method: str
    tenant_id: str = "default"
    # Optional human-readable email from token claims (display / /v1/auth/me).
    email: Optional[str] = None


def _email_from_claims(payload: Dict[str, object]) -> Optional[str]:
    for key in ("email", "preferred_username", "upn"):
        raw = payload.get(key)
        if not isinstance(raw, str):
            continue
        value = raw.strip()
        if value and "@" in value:
            return value
    # Auth0 custom claims must be namespaced (e.g. https://rag-protection.local/email).
    for key, raw in payload.items():
        if not isinstance(key, str) or not key.endswith("/email"):
            continue
        if not isinstance(raw, str):
            continue
        value = raw.strip()
        if value and "@" in value:
            return value
    return None


def resolve_auth(authorization: Optional[str], acl: ACLPolicy) -> Optional[AuthContext]:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        return None

    for user in acl.demo_users:
        if token == user.token:
            groups = _expand_groups(user.groups, acl)
            groups = _merge_scim_groups(user.subject, groups, acl)
            return AuthContext(
                subject=user.subject,
                groups=groups,
                auth_method="demo_token",
                tenant_id=user.tenant_id or "default",
                email=user.subject if "@" in user.subject else None,
            )

    if acl.oidc.enabled:
        oidc_ctx = _resolve_oidc(token, acl.oidc, acl)
        if oidc_ctx is not None:
            return oidc_ctx

    if acl.jwt_secret:
        try:
            payload = jwt.decode(
                token,
                acl.jwt_secret,
                algorithms=acl.jwt_algorithms,
                options={"verify_aud": False},
            )
        except jwt.PyJWTError:
            return None
        raw_groups = payload.get(acl.jwt_groups_claim) or payload.get("roles") or []
        if isinstance(raw_groups, str):
            raw_groups = raw_groups.split()
        groups = _expand_groups([str(g) for g in raw_groups], acl)
        subject = str(payload.get("sub") or payload.get("email") or "jwt-user")
        tenant_id = str(payload.get(acl.jwt_tenant_claim) or "default")
        groups = _merge_scim_groups(subject, groups, acl)
        return AuthContext(
            subject=subject,
            groups=groups,
            auth_method="jwt",
            tenant_id=tenant_id,
            email=_email_from_claims(payload),
        )

    return None


def _resolve_oidc(token: str, oidc: OIDCConfig, acl: ACLPolicy) -> Optional[AuthContext]:
    if not oidc.jwks_uri:
        return None
    try:
        client = _get_jwks_client(oidc.jwks_uri)
        signing_key = client.get_signing_key_from_jwt(token)
        decode_kwargs: Dict[str, object] = {
            "algorithms": oidc.algorithms,
            "options": {"verify_aud": bool(oidc.audience)},
        }
        if oidc.audience:
            decode_kwargs["audience"] = oidc.audience
        if oidc.issuer:
            decode_kwargs["issuer"] = oidc.issuer
        payload = jwt.decode(token, signing_key.key, **decode_kwargs)
    except jwt.PyJWTError:
        return None

    raw_groups = (
        payload.get(oidc.groups_claim)
        or payload.get(oidc.roles_claim)
        or payload.get("roles")
        or []
    )
    if isinstance(raw_groups, str):
        raw_groups = raw_groups.split()
    groups = _expand_groups([str(group) for group in raw_groups], acl)
    subject = str(payload.get("sub") or payload.get("email") or payload.get("preferred_username") or "oidc-user")
    tenant_id = str(payload.get(oidc.tenant_claim) or "default")
    groups = _merge_scim_groups(subject, groups, acl)
    return AuthContext(
        subject=subject,
        groups=groups,
        auth_method="oidc",
        tenant_id=tenant_id,
        email=_email_from_claims(payload),
    )


def _get_jwks_client(uri: str) -> PyJWKClient:
    if uri not in _jwks_clients:
        _jwks_clients[uri] = PyJWKClient(uri, cache_keys=True)
    return _jwks_clients[uri]


def _merge_scim_groups(subject: str, groups: List[str], acl: ACLPolicy) -> List[str]:
    if not acl.scim.enabled:
        return groups
    try:
        from rag_protection_enterprise.connectors.scim import get_scim_cache
    except ImportError:
        return groups

    scim_groups = get_scim_cache().groups_for(subject)
    if not scim_groups:
        return groups
    merged: Set[str] = set(groups)
    merged.update(scim_groups)
    return sorted(_expand_groups(sorted(merged), acl))


def _expand_groups(groups: List[str], acl: ACLPolicy) -> List[str]:
    expanded: Set[str] = set(groups or acl.default_groups)
    for group in list(expanded):
        for inherited in acl.group_hierarchy.get(group, []):
            expanded.add(inherited)
    return sorted(expanded)


def user_can_access_document(user_groups: List[str], document_groups: List[str]) -> bool:
    if not document_groups:
        return False
    allowed = set(document_groups)
    if "public" in allowed or "all-staff" in allowed:
        return True
    return bool(set(user_groups) & allowed)
