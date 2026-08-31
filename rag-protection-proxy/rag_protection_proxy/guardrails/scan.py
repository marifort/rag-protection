"""Stateless scan API disposition — maps scan_input() output to caller actions.

Mirrors evaluate_ingest_scan() rules without ingest-specific status names.
Docs: docs/enterprise/e7/E7_1_SCAN_API.md
"""

from __future__ import annotations

from typing import Literal

from rag_protection_proxy.config import Policy
from rag_protection_proxy.guardrails.risk_scoring import is_effective_block
from rag_protection_proxy.models import Decision, InputScanResponse

SCAN_MAX_TEXT_BYTES = 512 * 1024

ScanDisposition = Literal[
    "reject",
    "quarantine",
    "pass_with_warning",
    "pass",
    "pass_with_redactions",
]


def scan_disposition(scan: InputScanResponse, policy: Policy) -> ScanDisposition:
    """Return caller action hint for POST /v1/scan."""
    verdict = scan.verdict
    mode = policy.input.challenge_mode

    if is_effective_block(verdict.decision, mode):
        return "reject"

    if verdict.decision == Decision.ALLOW:
        return "pass"

    if verdict.decision == Decision.CHALLENGE:
        if scan.redactions > 0 and mode in ("allow", "audit_only"):
            return "pass_with_redactions"
        if mode == "allow":
            return "quarantine"
        if mode == "audit_only":
            return "pass_with_warning"

    return "pass"
