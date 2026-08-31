"""PII scanner — redacts emails, phones, SSNs, Canadian SINs, credit cards.

Regex patterns in _PATTERNS; each match is replaced in sanitized_text and
recorded as a Finding. Used inside scan_input() and scan_output().

Canadian SIN uses the Service Canada / CRA grouping XXX-XXX-XXX (also accepted
with spaces or dots). A 3-2-4 number labeled as SIN in nearby text is logged
as SIN, not SSN.

Docs: docs/guardrails/GUARDRAIL_2_DLP.md#how-sensitive-content-is-detected
      docs/guardrails/DETECTION_OVERVIEW.md
"""

from __future__ import annotations

import re
from typing import Callable, List, Tuple

from rag_protection_proxy.models import Finding
from rag_protection_proxy.scanners.base import Scanner, ScannerResult

# Standard SIN grouping: XXX-XXX-XXX; spaces and dots are the other common typesetting.
_SIN_RE = re.compile(r"\b\d{3}(?:[-.\s]\d{3}[-.\s]\d{3})\b")
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_SIN_HINT_RE = re.compile(r"\b(?:sins?|social insurance)\b", re.I)
_SSN_HINT_RE = re.compile(r"\b(?:ssns?|social security)\b", re.I)

_PATTERNS: List[Tuple[re.Pattern[str], str, str, float]] = [
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), "email", "[REDACTED_EMAIL]", 0.3),
    (re.compile(r"\b(?:\+?\d{1,2}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b"), "phone", "[REDACTED_PHONE]", 0.3),
    (_SSN_RE, "ssn", "[REDACTED_SSN]", 0.7),
    (_SIN_RE, "sin_candidate", "[REDACTED_SIN]", 0.7),
    (re.compile(r"\b(?:\d[ -]*?){13,19}\b"), "credit_card_candidate", "[REDACTED_CC]", 0.5),
]


class PIIScanner(Scanner):
    name = "pii"

    def scan(self, text: str) -> ScannerResult:
        if not isinstance(text, str):
            text = "" if text is None else str(text)

        findings: List[Finding] = []
        sanitized = text
        redactions = 0
        for regex, category, replacement, severity in _PATTERNS:
            if category == "ssn":
                sanitized, extra, count = _redact_ssn_matches(sanitized, regex, severity)
                findings.extend(extra)
                redactions += count
                continue
            if category == "sin_candidate":
                sanitized, extra, count = _redact_if(
                    sanitized, regex, replacement, severity, "sin", _is_canadian_sin
                )
                findings.extend(extra)
                redactions += count
                continue
            matches = list(regex.finditer(sanitized))
            if not matches:
                continue
            if category == "credit_card_candidate":
                matches = [m for m in matches if _luhn_valid(re.sub(r"\D", "", m.group(0)))]
                if not matches:
                    continue
                category = "credit_card"
            for m in matches:
                findings.append(Finding(
                    scanner=self.name,
                    category=category,
                    severity=severity,
                    snippet=_mask(m.group(0)),
                ))
            sanitized = regex.sub(replacement, sanitized)
            redactions += len(matches)
        return ScannerResult(sanitized_text=sanitized, findings=findings, redactions=redactions)


def _window(text: str, start: int, end: int, size: int = 40) -> str:
    return text[max(0, start - size) : min(len(text), end + size)]


def _prefer_sin_label(window: str) -> bool:
    return bool(_SIN_HINT_RE.search(window)) and not _SSN_HINT_RE.search(window)


def _redact_ssn_matches(
    text: str,
    regex: re.Pattern[str],
    severity: float,
) -> Tuple[str, List[Finding], int]:
    """3-2-4 numbers are SSN unless nearby text names them as a Canadian SIN."""
    findings: List[Finding] = []
    count = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal count
        raw = match.group(0)
        if _prefer_sin_label(_window(text, match.start(), match.end())):
            category, replacement = "sin", "[REDACTED_SIN]"
        else:
            category, replacement = "ssn", "[REDACTED_SSN]"
        findings.append(
            Finding(
                scanner="pii",
                category=category,
                severity=severity,
                snippet=_mask(raw),
            )
        )
        count += 1
        return replacement

    return regex.sub(repl, text), findings, count


def _redact_if(
    text: str,
    regex: re.Pattern[str],
    replacement: str,
    severity: float,
    category: str,
    predicate: Callable[[str, str], bool],
) -> Tuple[str, List[Finding], int]:
    findings: List[Finding] = []
    count = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal count
        raw = match.group(0)
        window = _window(text, match.start(), match.end())
        if not predicate(raw, window):
            return raw
        findings.append(
            Finding(
                scanner="pii",
                category=category,
                severity=severity,
                snippet=_mask(raw),
            )
        )
        count += 1
        return replacement

    return regex.sub(repl, text), findings, count


def _is_canadian_sin(raw: str, window: str = "") -> bool:
    """True for a 9-digit value in standard SIN grouping (XXX-XXX-XXX)."""
    digits = re.sub(r"\D", "", raw)
    if len(digits) != 9:
        return False
    if digits[0] == "8" and not _SIN_HINT_RE.search(window):
        return False
    return True


def _luhn_valid(digits: str) -> bool:
    if not (13 <= len(digits) <= 19):
        return False
    return _luhn_ok(digits)


def _luhn_ok(digits: str) -> bool:
    if not digits.isdigit():
        return False
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _mask(s: str) -> str:
    if len(s) <= 4:
        return "*" * len(s)
    return s[:2] + "*" * (len(s) - 4) + s[-2:]
