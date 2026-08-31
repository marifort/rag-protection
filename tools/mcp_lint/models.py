"""Data model for MCP lint findings and reports."""

from __future__ import annotations

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
class McpTool:
    """Normalized MCP tool entry from ``tools/list``."""

    name: str
    description: str
    input_schema: Optional[dict] = None
    source: str = ""


@dataclass
class Finding:
    rule_id: str
    severity: Severity
    title: str
    message: str
    location: str = ""
    remediation: str = ""

    @property
    def tool_name(self) -> str:
        if self.location.startswith("tool:"):
            return self.location.split(":", 1)[1]
        return ""


@dataclass
class LintReport:
    findings: List[Finding] = field(default_factory=list)
    tools_scanned: int = 0
    # Set when the manifest could not be loaded or the MCP server was unreachable.
    load_error: Optional[str] = None

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
