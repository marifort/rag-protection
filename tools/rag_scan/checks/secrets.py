"""Secret / auth posture checks (SEC001–SEC002)."""

from __future__ import annotations

from typing import List

from ..context import ScanContext
from ..models import Finding, Severity

# Shipped demo admin keys — must never appear in a production ACL file.
DEFAULT_ADMIN_KEYS = {
    "rag-admin-demo-key",
    "rag-audit-reader-key",
    "rag-audit-debug-key",
    "rag-ingest-admin-key",
}


def check_default_admin_key(ctx: ScanContext) -> List[Finding]:
    """SEC001 — default/demo admin API keys present in a production ACL file."""
    if ctx.acl is None or not ctx.is_prod:
        return []
    hits = sorted({u.token for u in ctx.acl.admin_users if u.token in DEFAULT_ADMIN_KEYS})
    if not hits:
        return []
    return [
        Finding(
            rule_id="SEC001",
            severity=Severity.CRITICAL,
            title="Default admin key in production ACL",
            message=f"Shipped demo admin key(s) present while --env=prod: {hits}.",
            location=str(ctx.acl_path or "acl_policy.yaml"),
            remediation="Rotate to unique secrets supplied via env/secret manager; remove demo keys.",
        )
    ]


def check_no_auth_configured(ctx: ScanContext) -> List[Finding]:
    """SEC002 — no usable caller authentication is configured for production."""
    if ctx.acl is None or not ctx.is_prod:
        return []
    oidc_ready = ctx.acl.oidc.enabled and bool(ctx.acl.oidc.jwks_uri)
    jwt_ready = bool(ctx.acl.jwt_secret)
    if oidc_ready or jwt_ready:
        return []
    if ctx.acl.demo_users:
        # Auth "works" but only via static demo tokens — already flagged by ACL001.
        return []
    return [
        Finding(
            rule_id="SEC002",
            severity=Severity.WARNING,
            title="No caller authentication configured",
            message=(
                "No OIDC (jwks_uri) and no jwt_secret configured for production; "
                "callers cannot be authenticated against an IdP."
            ),
            location=str(ctx.acl_path or "acl_policy.yaml"),
            remediation="Enable `oidc` with a jwks_uri, or set a jwt_secret for signed tokens.",
        )
    ]
