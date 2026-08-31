"""ACL configuration checks (ACL001–ACL003)."""

from __future__ import annotations

from typing import List

from ..context import ScanContext
from ..models import Finding, Severity

# Groups that mean "effectively everyone" — never valid on confidential data.
BROAD_GROUPS = {"*", "all-staff", "public", "everyone", "all"}

# Substrings in a document's classification that mark it as sensitive.
CONFIDENTIAL_MARKERS = ("confidential", "secret", "restricted", "pii", "phi", "pci")


def check_demo_tokens_in_prod(ctx: ScanContext) -> List[Finding]:
    """ACL001 — demo bearer tokens must not ship in a production ACL file."""
    if ctx.acl is None or not ctx.is_prod:
        return []
    demo = [u for u in ctx.acl.demo_users if u.token]
    if not demo:
        return []
    names = ", ".join(sorted({u.token for u in demo})[:5])
    return [
        Finding(
            rule_id="ACL001",
            severity=Severity.CRITICAL,
            title="Demo bearer tokens present in production ACL",
            message=(
                f"{len(demo)} static demo token(s) defined while --env=prod "
                f"(e.g. {names}). Anyone with the token bypasses the IdP."
            ),
            location=str(ctx.acl_path or "acl_policy.yaml"),
            remediation="Remove `demo_users` in production and rely on OIDC bearer tokens.",
        )
    ]


def check_confidential_world_readable(ctx: ScanContext) -> List[Finding]:
    """ACL002 — confidential documents must not be readable by broad groups."""
    findings: List[Finding] = []
    for doc in ctx.sample_docs:
        metadata = doc.get("metadata") or {}
        classification = str(metadata.get("classification") or "").lower()
        if not any(marker in classification for marker in CONFIDENTIAL_MARKERS):
            continue
        allowed = {str(g).strip().lower() for g in (doc.get("allowed_groups") or [])}
        leaking = allowed & BROAD_GROUPS
        if not leaking:
            continue
        doc_id = doc.get("document_id") or doc.get("title") or "<unknown>"
        findings.append(
            Finding(
                rule_id="ACL002",
                severity=Severity.CRITICAL,
                title="Confidential document readable by broad group",
                message=(
                    f"Document {doc_id!r} (classification={classification!r}) grants "
                    f"access to broad group(s): {sorted(leaking)}."
                ),
                location=str(ctx.sample_docs_path or "sample_documents.json"),
                remediation="Restrict `allowed_groups` to least-privilege groups (e.g. hr, executives).",
            )
        )
    return findings


def check_overbroad_default_groups(ctx: ScanContext) -> List[Finding]:
    """ACL003 — wildcard in default_groups grants every caller universal access."""
    if ctx.acl is None:
        return []
    defaults = {str(g).strip().lower() for g in ctx.acl.default_groups}
    if "*" not in defaults:
        return []
    return [
        Finding(
            rule_id="ACL003",
            severity=Severity.WARNING,
            title="Wildcard in default_groups",
            message="`default_groups` contains `*`, granting every caller access to all chunks.",
            location=str(ctx.acl_path or "acl_policy.yaml"),
            remediation="Set `default_groups` to a least-privilege baseline such as [all-staff].",
        )
    ]
