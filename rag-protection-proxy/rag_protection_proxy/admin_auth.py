"""Admin RBAC — role-based access for operator endpoints (E2.4)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Optional, Set

import jwt

from rag_protection_proxy.acl import _expand_groups
from rag_protection_proxy.config import ACLPolicy, AdminUser

POLICY_ADMIN = "policy_admin"
AUDIT_READER = "audit_reader"
AUDIT_DEBUG_READER = "audit_debug_reader"
INGEST_ADMIN = "ingest_admin"

ALL_ADMIN_ROLES: FrozenSet[str] = frozenset(
    {POLICY_ADMIN, AUDIT_READER, AUDIT_DEBUG_READER, INGEST_ADMIN}
)


@dataclass(frozen=True)
class AdminContext:
    subject: str
    roles: FrozenSet[str]
    auth_method: str
    tenant_scope: Optional[str] = None


def _normalize_roles(roles: List[str]) -> FrozenSet[str]:
    return frozenset(role for role in roles if role in ALL_ADMIN_ROLES)


def _admin_roles_from_idp_groups(
    idp_groups: List[str],
    role_map: Dict[str, List[str]],
) -> FrozenSet[str]:
    if not role_map:
        return frozenset()
    idp_set = set(idp_groups)
    matched: Set[str] = set()
    for admin_role, mapped_groups in role_map.items():
        if admin_role not in ALL_ADMIN_ROLES:
            continue
        if idp_set.intersection(mapped_groups):
            matched.add(admin_role)
    return frozenset(matched)


def _tenant_scope_from_claims(
    idp_groups: List[str],
    tenant_id: str,
    tenant_claim_present: bool,
    global_groups: List[str],
) -> Optional[str]:
    if global_groups and set(idp_groups).intersection(global_groups):
        return None
    if tenant_claim_present:
        return tenant_id or "default"
    return None


def _resolve_oidc_admin(token: str, acl: ACLPolicy) -> Optional[AdminContext]:
    oidc = acl.oidc
    if not oidc.enabled or not oidc.admin_role_map:
        return None
    if not oidc.jwks_uri:
        return None

    try:
        from rag_protection_proxy.acl import _get_jwks_client

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
    roles = _admin_roles_from_idp_groups(groups, oidc.admin_role_map)
    if not roles:
        return None

    subject = str(
        payload.get("sub")
        or payload.get("email")
        or payload.get("preferred_username")
        or "oidc-admin"
    )
    tenant_claim_present = oidc.tenant_claim in payload
    tenant_id = str(payload.get(oidc.tenant_claim) or "default")
    tenant_scope = _tenant_scope_from_claims(
        groups,
        tenant_id,
        tenant_claim_present,
        oidc.admin_global_groups,
    )
    return AdminContext(
        subject=subject,
        roles=roles,
        auth_method="oidc",
        tenant_scope=tenant_scope,
    )


def _resolve_jwt_admin(token: str, acl: ACLPolicy) -> Optional[AdminContext]:
    role_map = acl.oidc.admin_role_map
    if not acl.jwt_secret or not role_map:
        return None
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
    groups = _expand_groups([str(group) for group in raw_groups], acl)
    roles = _admin_roles_from_idp_groups(groups, role_map)
    if not roles:
        return None

    subject = str(payload.get("sub") or payload.get("email") or "jwt-admin")
    tenant_claim_present = acl.jwt_tenant_claim in payload
    tenant_id = str(payload.get(acl.jwt_tenant_claim) or "default")
    tenant_scope = _tenant_scope_from_claims(
        groups,
        tenant_id,
        tenant_claim_present,
        acl.oidc.admin_global_groups,
    )
    return AdminContext(
        subject=subject,
        roles=roles,
        auth_method="jwt",
        tenant_scope=tenant_scope,
    )


def _admin_from_user(admin: AdminUser) -> AdminContext:
    tenant_scope = admin.tenant_id if admin.tenant_id else None
    return AdminContext(
        subject=admin.subject,
        roles=_normalize_roles(admin.roles),
        auth_method="admin_token",
        tenant_scope=tenant_scope,
    )


def resolve_admin(authorization: Optional[str], acl: ACLPolicy) -> Optional[AdminContext]:
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        return None

    for admin in acl.admin_users:
        if token == admin.token:
            return _admin_from_user(admin)

    env_key = os.getenv("RAG_ADMIN_API_KEY", "")
    if env_key and token == env_key:
        return AdminContext(
            subject="admin.api_key",
            roles=ALL_ADMIN_ROLES,
            auth_method="api_key",
            tenant_scope=None,
        )

    oidc_admin = _resolve_oidc_admin(token, acl)
    if oidc_admin is not None:
        return oidc_admin

    jwt_admin = _resolve_jwt_admin(token, acl)
    if jwt_admin is not None:
        return jwt_admin

    return None


def admin_has_role(admin: AdminContext, role: str) -> bool:
    return role in admin.roles


def admin_has_any_role(admin: AdminContext, roles: Set[str]) -> bool:
    return bool(admin.roles & roles)


def admin_can_view_audit_debug(admin: AdminContext) -> bool:
    """True when admin API responses may include AuditEvent.debug previews."""
    if admin.auth_method in {"open", "api_key"}:
        return True
    return admin_has_any_role(admin, {AUDIT_DEBUG_READER, POLICY_ADMIN})


def admin_is_global(admin: AdminContext) -> bool:
    return admin.tenant_scope is None


def admin_allowed_tenant_ids(admin: AdminContext, known_tenant_ids: List[str]) -> List[str]:
    if admin_is_global(admin):
        merged = set(known_tenant_ids or [])
        merged.add("default")
        return sorted(merged)
    return [admin.tenant_scope or "default"]


def admin_can_access_tenant(admin: AdminContext, tenant_id: str) -> bool:
    if admin_is_global(admin):
        return True
    requested = tenant_id or "default"
    return requested == (admin.tenant_scope or "default")


def admin_effective_tenant_filter(
    admin: AdminContext,
    requested_tenant_id: Optional[str],
) -> Optional[str]:
    """Resolve optional tenant filter for audit endpoints."""
    if admin_is_global(admin):
        return requested_tenant_id
    return admin.tenant_scope or "default"
