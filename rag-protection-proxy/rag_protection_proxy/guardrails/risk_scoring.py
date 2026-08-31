"""Risk score aggregation across scanner findings."""

from __future__ import annotations

from typing import Iterable, List, Literal

from rag_protection_proxy.models import Decision, Finding

ChallengeMode = Literal["allow", "block", "audit_only"]

# PII/DLP scanners replace matches in sanitized_text. They must not withhold the
# rest of an authorized chunk (SSN+SIN bump must not BLOCK payroll). Injection,
# secrets, and URL threats remain eligible to BLOCK.
REDACT_AND_PASS_SCANNERS = frozenset({"pii", "pii_ner", "custom_pattern"})


def aggregate_risk(findings: Iterable[Finding]) -> float:
    findings = list(findings)
    if not findings:
        return 0.0
    max_sev = max(f.severity for f in findings)
    n_high = sum(1 for f in findings if f.severity >= 0.7)
    bump = min(0.1 * (n_high - 1), 0.15) if n_high > 1 else 0.0
    return round(min(1.0, max_sev + bump), 2)


def findings_for_input_block(findings: Iterable[Finding]) -> List[Finding]:
    """Findings that may raise an input BLOCK (not redact-and-pass DLP)."""
    return [f for f in findings if (f.scanner or "") not in REDACT_AND_PASS_SCANNERS]


def decide(risk: float, challenge_threshold: float, block_threshold: float) -> Decision:
    if risk >= block_threshold:
        return Decision.BLOCK
    if risk >= challenge_threshold:
        return Decision.CHALLENGE
    return Decision.ALLOW


def apply_challenge_mode(decision: Decision, challenge_mode: str) -> Decision:
    """Map CHALLENGE to BLOCK when policy challenge_mode is 'block'."""
    if decision == Decision.CHALLENGE and challenge_mode == "block":
        return Decision.BLOCK
    return decision


def is_effective_block(decision: Decision, challenge_mode: str) -> bool:
    return apply_challenge_mode(decision, challenge_mode) == Decision.BLOCK
