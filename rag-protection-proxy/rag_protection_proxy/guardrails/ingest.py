"""Ingest-time security — scan documents before they enter the corpus.

Combines title + content and runs scan_input() (shared input pipeline).
Maps scan verdict + challenge_mode to ok, quarantined, or rejected.

Detection heuristics live in scanners/ (especially prompt_injection.py);
this module only orchestrates ingest-specific disposition.

Docs: docs/guardrails/P1_INGEST_SECURITY.md
"""

from __future__ import annotations

from typing import Literal, Optional, Tuple

from rag_protection_proxy.config import Policy
from rag_protection_proxy.guardrails.input_pipeline import scan_input
from rag_protection_proxy.guardrails.risk_scoring import apply_challenge_mode, is_effective_block
from rag_protection_proxy.models import Decision, InputScanRequest, InputScanResponse

IngestStatus = Literal["ok", "quarantined", "rejected"]


def scan_ingest_content(
    document_id: str,
    title: str,
    content: str,
    policy: Policy,
    *,
    tenant_id: str = "default",
    subject: Optional[str] = None,
    audit_debug: bool = False,
) -> InputScanResponse:
    combined = f"{title}\n\n{content}".strip()
    return scan_input(
        InputScanRequest(
            text=combined,
            source=f"rag:ingest:{document_id}",
            trusted=False,
            tenant_id=tenant_id,
            subject=subject,
            context={"audit_debug": bool(audit_debug)},
        ),
        policy,
    )


def evaluate_ingest_scan(scan: InputScanResponse, policy: Policy) -> Tuple[IngestStatus, str]:
    """Return ingest disposition: ok, quarantined (mid-risk), or rejected (block)."""
    verdict = scan.verdict
    if is_effective_block(verdict.decision, policy.input.challenge_mode):
        return "rejected", verdict.reason

    effective = apply_challenge_mode(verdict.decision, policy.input.challenge_mode)
    if verdict.decision == Decision.CHALLENGE and effective == Decision.CHALLENGE:
        if policy.input.challenge_mode == "allow":
            return "quarantined", verdict.reason
        # audit_only: ingest normally; scan_input already recorded the event
        return "ok", verdict.reason

    return "ok", verdict.reason


def split_sanitized_ingest_text(title: str, content: str, sanitized: str) -> Tuple[str, str]:
    """Map combined scan output back to title and content for storage."""
    title = title or ""
    content = content or ""
    if not title.strip():
        return "", sanitized
    if not content.strip():
        return sanitized, ""
    separator = "\n\n"
    idx = sanitized.find(separator)
    if idx == -1:
        return sanitized, ""
    return sanitized[:idx], sanitized[idx + len(separator) :]


def quarantine_metadata(scan: InputScanResponse) -> dict:
    scanners: list[str] = []
    categories: list[str] = []
    seen_scanners: set[str] = set()
    seen_categories: set[str] = set()
    for finding in scan.verdict.findings:
        scanner = (finding.scanner or "").strip()
        category = (finding.category or "").strip()
        if scanner and scanner not in seen_scanners:
            seen_scanners.add(scanner)
            scanners.append(scanner)
        if category and category not in seen_categories:
            seen_categories.add(category)
            categories.append(category)
    return {
        "status": "quarantined",
        "quarantine_decision": scan.verdict.decision.value,
        "quarantine_reason": scan.verdict.reason,
        "quarantine_risk_score": scan.verdict.risk_score,
        "quarantine_scanners": scanners,
        "quarantine_categories": categories,
    }
