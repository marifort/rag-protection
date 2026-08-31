"""Data model for scan findings and reports."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class Severity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"

    @property
    def rank(self) -> int:
        return {"critical": 3, "warning": 2, "info": 1}[self.value]


@dataclass
class Finding:
    rule_id: str
    severity: Severity
    title: str
    message: str
    location: str = ""
    remediation: str = ""

    @property
    def fingerprint(self) -> str:
        """Stable identifier for baseline suppression.

        Keyed on rule + location + message so that a *different* instance of the
        same rule (e.g. ACL002 on another document) keeps its own fingerprint,
        and a finding whose underlying config changed resurfaces instead of
        staying silently suppressed.
        """
        digest = hashlib.sha1()
        digest.update(f"{self.rule_id}|{self.location}|{self.message}".encode("utf-8"))
        return digest.hexdigest()


@dataclass
class ScanReport:
    findings: List[Finding] = field(default_factory=list)
    # Set when configuration could not even be loaded (CLI exit code 2).
    load_error: Optional[str] = None
    # Count of findings hidden by a --baseline file (informational only).
    suppressed: int = 0

    def add(self, finding: Finding) -> None:
        self.findings.append(finding)

    def extend(self, findings: List[Finding]) -> None:
        self.findings.extend(findings)

    def by_severity(self, severity: Severity) -> List[Finding]:
        return [f for f in self.findings if f.severity is severity]

    def counts(self) -> dict[str, int]:
        return {
            sev.value: len(self.by_severity(sev))
            for sev in (Severity.CRITICAL, Severity.WARNING, Severity.INFO)
        }

    def has_at_or_above(self, severity: Severity) -> bool:
        return any(f.severity.rank >= severity.rank for f in self.findings)
