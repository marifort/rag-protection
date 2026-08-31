"""NER-style PII scanner — person names and street addresses (E3.1).

Lightweight heuristic NER (no spaCy/Presidio dependency). Detects capitalized
person names and US-style street addresses beyond regex PII patterns.

Policy toggle: `dlp.enable_ner` (API knob: `dlp_enable_ner`). When true, runs in
`scan_input()` and `scan_output()` after `PIIScanner`.

Docs: docs/guardrails/GUARDRAIL_2_DLP.md § Scanner 4
      docs/enterprise/e3/E3_1_NER_DLP.md
"""

from __future__ import annotations

import re
from typing import List, Set, Tuple

from rag_protection_proxy.models import Finding
from rag_protection_proxy.scanners.base import Scanner, ScannerResult

_PERSON_NAME_RE = re.compile(
    r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\b"
)
_ADDRESS_RE = re.compile(
    r"\b(\d{1,5}\s+[A-Za-z0-9][\w\s.'-]{0,40}?"
    r"(?:Street|St\.?|Avenue|Ave\.?|Road|Rd\.?|Boulevard|Blvd\.?|Drive|Dr\.?|Lane|Ln\.?))\b",
    re.I,
)

_NAME_BLOCKLIST: Set[str] = {
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
    "January", "February", "March", "April", "May", "June", "July", "August",
    "September", "October", "November", "December",
    "Eastern", "Pacific", "Central", "Mountain",
    "Payroll", "Summary", "Employee", "Executive", "Company", "Support",
    "Engineering", "Customer", "Feedback", "Ticket", "Strategy", "Memo",
    "San Francisco", "New York", "Los Angeles",
    "Market Street", "Main Street", "Broadway",
}

_TITLE_PREFIXES = {"mr", "mrs", "ms", "dr", "prof"}

_COMMON_NAME_PARTS = {
    "test", "doc", "only", "acme", "globex", "custom", "ingest", "content",
    "tenant", "confidential", "memo", "secret", "summary", "policy", "guide",
    "runbook", "ticket", "feedback", "strategy", "office", "headquarters",
}


class PIINERScanner(Scanner):
    name = "pii_ner"

    def scan(self, text: str) -> ScannerResult:
        if not isinstance(text, str):
            text = "" if text is None else str(text)

        findings: List[Finding] = []
        sanitized = text
        redactions = 0

        for match in _ADDRESS_RE.finditer(sanitized):
            address = match.group(1)
            findings.append(Finding(
                scanner=self.name,
                category="address",
                severity=0.5,
                snippet=_mask(address),
            ))
            sanitized = sanitized.replace(address, "[REDACTED_ADDRESS]", 1)
            redactions += 1

        for match in _PERSON_NAME_RE.finditer(sanitized):
            name = match.group(1)
            if not _is_person_name(name):
                continue
            findings.append(Finding(
                scanner=self.name,
                category="person_name",
                severity=0.45,
                snippet=_mask(name),
            ))
            sanitized = sanitized.replace(name, "[REDACTED_PERSON_NAME]", 1)
            redactions += 1

        return ScannerResult(sanitized_text=sanitized, findings=findings, redactions=redactions)


def _is_person_name(name: str) -> bool:
    parts = name.split()
    if len(parts) < 2:
        return False
    if any(part in _NAME_BLOCKLIST for part in parts):
        return False
    if any(part.lower() in _COMMON_NAME_PARTS for part in parts):
        return False
    if parts[0].lower() in _TITLE_PREFIXES:
        return len(parts) >= 3
    return all(len(part) >= 2 for part in parts)


def _mask(value: str, max_len: int = 40) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    if len(value) <= max_len:
        return value
    return value[: max_len - 1] + "…"
