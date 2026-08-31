"""Map scanner rules onto the OWASP LLM Top 10 and build the coverage summary.

The scorecard reports on the OWASP risks the config scan can actually speak to
(LLM01 prompt injection, LLM06 sensitive information disclosure) plus the two
RAG-relevant risks that a *config* scan cannot judge (LLM07 insecure plugin/tool
design, LLM08 excessive agency) — surfaced as "not assessed here" with a pointer
to the Marifort Gate tool gateway. Mirrors the shipped coverage map in
``docs/commercial/AI_SECURITY_COMPETENCY_LABS.md#owasp-llm-top-10--coverage-map``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List

from rag_scan.models import Finding, Severity

# OWASP LLM Top 10 risk identifiers used by this scorecard.
RISK_NAMES: Dict[str, str] = {
    "LLM01": "Prompt injection",
    "LLM06": "Sensitive information disclosure",
    "LLM07": "Insecure plugin / tool design",
    "LLM08": "Excessive agency",
}

# Each scanner rule attributes to the OWASP risk it most directly evidences.
RULE_TO_RISK: Dict[str, str] = {
    "ACL001": "LLM06",  # demo tokens bypass IdP -> unauthorized access to data
    "ACL002": "LLM06",  # confidential doc readable by a broad group
    "ACL003": "LLM06",  # wildcard default_groups grants universal read
    "POL001": "LLM01",  # input block threshold below floor -> guardrail mis-tuned
    "POL002": "LLM06",  # connectors fail open -> synced docs broadly readable
    "POL003": "LLM01",  # injection detection coverage reduced
    "CON001": "LLM06",  # connector job missing ACL mapping
    "SEC001": "LLM06",  # default admin key in prod -> privileged access
    "SEC002": "LLM06",  # no caller auth -> unauthenticated access
    "VEC001": "LLM06",  # vector payloads missing allowed_groups
}

# Risks the config scan evaluates, in report order.
ASSESSED_RISKS: List[str] = ["LLM01", "LLM06"]

# RAG-relevant risks a config scan cannot judge; covered by the runtime gateway.
NOT_ASSESSED_RISKS: List[str] = ["LLM07", "LLM08"]

_NOT_ASSESSED_NOTE = (
    "Not assessed by a config scan — covered at runtime by the Marifort Gate "
    "tool gateway (allowlist + audit). See Lab 1 (MCP gateway)."
)

# status -> human label, worst first.
_STATUS_LABEL = {
    "critical": "At risk (critical)",
    "warning": "Needs attention",
    "info": "Minor",
    "clean": "Clean",
    "not-assessed": "Not assessed here",
}


@dataclass
class CoverageRow:
    risk_id: str
    name: str
    status: str  # one of _STATUS_LABEL keys
    rule_ids: List[str] = field(default_factory=list)
    note: str = ""

    @property
    def status_label(self) -> str:
        return _STATUS_LABEL.get(self.status, self.status)


def _worst_status(findings: Iterable[Finding]) -> str:
    """Collapse a set of findings into their worst severity status string."""
    worst = "clean"
    rank = {"clean": 0, "info": 1, "warning": 2, "critical": 3}
    for f in findings:
        if rank[f.severity.value] > rank[worst]:
            worst = f.severity.value
    return worst


def build_coverage(findings: Iterable[Finding]) -> List[CoverageRow]:
    """Return the OWASP coverage rows for the report, in display order."""
    findings = list(findings)
    by_risk: Dict[str, List[Finding]] = {}
    for f in findings:
        risk = RULE_TO_RISK.get(f.rule_id)
        if risk:
            by_risk.setdefault(risk, []).append(f)

    rows: List[CoverageRow] = []
    for risk_id in ASSESSED_RISKS:
        hits = by_risk.get(risk_id, [])
        rows.append(
            CoverageRow(
                risk_id=risk_id,
                name=RISK_NAMES[risk_id],
                status=_worst_status(hits),
                rule_ids=sorted({f.rule_id for f in hits}),
            )
        )
    for risk_id in NOT_ASSESSED_RISKS:
        rows.append(
            CoverageRow(
                risk_id=risk_id,
                name=RISK_NAMES[risk_id],
                status="not-assessed",
                note=_NOT_ASSESSED_NOTE,
            )
        )
    return rows


def top_fixes(findings: Iterable[Finding], limit: int = 3) -> List[Finding]:
    """Return the highest-severity remediations, de-duplicated, capped at ``limit``.

    De-duplication is keyed on (rule_id, remediation) so a rule firing on many
    documents (e.g. ACL002) contributes a single actionable fix rather than
    crowding out other issues.
    """
    ordered = sorted(findings, key=lambda f: (-f.severity.rank, f.rule_id))
    seen: set[tuple[str, str]] = set()
    picked: List[Finding] = []
    for f in ordered:
        key = (f.rule_id, f.remediation)
        if key in seen:
            continue
        seen.add(key)
        picked.append(f)
        if len(picked) >= limit:
            break
    return picked
