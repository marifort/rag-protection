"""Live vector store probe (VEC001) — optional, requires --qdrant URL."""

from __future__ import annotations

from typing import List

from ..context import ScanContext
from ..models import Finding, Severity

SAMPLE_LIMIT = 50


def check_vector_payload_acl(ctx: ScanContext) -> List[Finding]:
    """VEC001 — sampled vector payloads are missing `allowed_groups` metadata.

    Best-effort: only runs when ``--qdrant`` is supplied. A chunk with no
    ``allowed_groups`` payload bypasses pre-retrieval ACL filtering entirely.
    """
    if not ctx.qdrant_url:
        return []

    try:
        from qdrant_client import QdrantClient
    except ImportError:
        return [
            Finding(
                rule_id="VEC001",
                severity=Severity.INFO,
                title="Vector probe skipped (qdrant-client not installed)",
                message="`--qdrant` was supplied but qdrant-client is not importable.",
                location=ctx.qdrant_url,
                remediation="pip install qdrant-client to enable live VEC001 probing.",
            )
        ]

    try:
        client = QdrantClient(url=ctx.qdrant_url, timeout=10)
        collections = [c.name for c in client.get_collections().collections]
    except Exception as exc:  # noqa: BLE001 — surface any transport error as a finding
        return [
            Finding(
                rule_id="VEC001",
                severity=Severity.WARNING,
                title="Vector store unreachable",
                message=f"Could not query Qdrant at {ctx.qdrant_url}: {exc}",
                location=ctx.qdrant_url,
                remediation="Verify the URL/network path; the gateway must reach the same store.",
            )
        ]

    findings: List[Finding] = []
    for name in collections:
        try:
            points, _ = client.scroll(
                collection_name=name,
                limit=SAMPLE_LIMIT,
                with_payload=True,
                with_vectors=False,
            )
        except Exception:  # noqa: BLE001
            continue
        missing = [
            str(p.id)
            for p in points
            if not (p.payload or {}).get("allowed_groups")
        ]
        if missing:
            findings.append(
                Finding(
                    rule_id="VEC001",
                    severity=Severity.CRITICAL,
                    title="Vector payloads missing allowed_groups",
                    message=(
                        f"Collection {name!r}: {len(missing)}/{len(points)} sampled points have "
                        "no `allowed_groups` payload and bypass pre-retrieval ACL filtering."
                    ),
                    location=f"{ctx.qdrant_url}#{name}",
                    remediation="Re-ingest chunks with `allowed_groups` metadata on every payload.",
                )
            )
    return findings
