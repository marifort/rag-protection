"""Shared helpers for the rag-score test suite."""

from __future__ import annotations

from pathlib import Path

import rag_scan
from rag_scan.models import Finding, Severity

# Reuse rag-scan's golden fixtures so the scorecard is exercised on the same
# bad/good configs the scanner itself is tested against.
FIXTURES = Path(rag_scan.__file__).resolve().parent / "tests" / "fixtures"

# All rule IDs the scanner can emit (the rag-scan rule catalog). Kept here so a
# new scanner rule that is not mapped to an OWASP risk fails the consistency test.
SCANNER_RULE_IDS = {
    "ACL001", "ACL002", "ACL003",
    "POL001", "POL002", "POL003",
    "CON001",
    "SEC001", "SEC002",
    "VEC001",
}


def finding(
    rule_id: str,
    severity: Severity,
    *,
    title: str = "t",
    message: str = "m",
    location: str = "loc",
    remediation: str = "fix",
) -> Finding:
    """Construct a :class:`Finding` with sensible defaults for tests."""
    return Finding(rule_id, severity, title, message, location, remediation)
