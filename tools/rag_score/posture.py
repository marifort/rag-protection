"""Orchestrate a posture assessment: load config, run checks, assemble the grade."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from rag_scan.checks import run_all
from rag_scan.context import build_context
from rag_scan.models import Finding

from . import owasp, scoring


@dataclass
class Posture:
    """The fully-computed scorecard, ready to render."""

    env: str
    score: int
    grade: str
    counts: dict[str, int]
    findings: List[Finding] = field(default_factory=list)
    coverage: List[owasp.CoverageRow] = field(default_factory=list)
    top_fixes: List[Finding] = field(default_factory=list)

    @property
    def blurb(self) -> str:
        return scoring.grade_blurb(self.grade)


def assess(findings: List[Finding], *, env: str) -> Posture:
    """Build a :class:`Posture` from already-collected findings."""
    score = scoring.score_findings(findings)
    counts = {
        sev: sum(1 for f in findings if f.severity.value == sev)
        for sev in ("critical", "warning", "info")
    }
    return Posture(
        env=env,
        score=score,
        grade=scoring.grade_for_score(score),
        counts=counts,
        findings=findings,
        coverage=owasp.build_coverage(findings),
        top_fixes=owasp.top_fixes(findings),
    )


def build_posture(
    *,
    env: str = "prod",
    policy_path: Optional[str] = None,
    acl_path: Optional[str] = None,
    sample_docs_path: Optional[str] = None,
    qdrant_url: Optional[str] = None,
) -> Posture:
    """Load + validate config, run all scanner checks, and score the result.

    Raises ``rag_scan.context.ConfigLoadError`` if a file cannot be loaded.
    """
    ctx = build_context(
        env=env,
        policy_path=policy_path,
        acl_path=acl_path,
        sample_docs_path=sample_docs_path,
        qdrant_url=qdrant_url,
    )
    findings = run_all(ctx)
    return assess(findings, env=env)
