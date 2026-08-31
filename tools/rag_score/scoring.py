"""Posture scoring: weight findings by severity into a 0–100 score and A–F grade.

Scoring model (see ADDITIONAL_OPPORTUNITIES_SPECS.md § A3):

    base 100, then per finding: critical −25, warning −8, info −2,
    clamped to [0, 100], mapped to an A/B/C/D/F band.

Deliberately simple and stable so a grade is explainable to a non-security buyer
("each critical costs you a letter and a half") and reproducible across runs.
"""

from __future__ import annotations

from typing import Iterable, List, Tuple

from rag_scan.models import Finding, Severity

BASE_SCORE = 100

# Penalty applied to the base score for each finding of a given severity.
WEIGHTS: dict[Severity, int] = {
    Severity.CRITICAL: -25,
    Severity.WARNING: -8,
    Severity.INFO: -2,
}

# (inclusive score floor, grade letter), highest band first.
GRADE_BANDS: List[Tuple[int, str]] = [
    (90, "A"),
    (80, "B"),
    (70, "C"),
    (60, "D"),
    (0, "F"),
]

# One-line characterisation shown next to the grade in the report.
GRADE_BLURB: dict[str, str] = {
    "A": "Strong posture — no critical exposure detected in the declared config.",
    "B": "Good posture — a few issues to tighten before production.",
    "C": "Fair posture — notable gaps that an attacker could chain.",
    "D": "Weak posture — at least one path to data exposure is open.",
    "F": "Failing posture — critical misconfigurations are present right now.",
}


def score_findings(findings: Iterable[Finding]) -> int:
    """Return the clamped 0–100 posture score for ``findings``."""
    raw = BASE_SCORE + sum(WEIGHTS[f.severity] for f in findings)
    return max(0, min(100, raw))


def grade_for_score(score: int) -> str:
    """Map a 0–100 score onto an A/B/C/D/F letter grade."""
    for floor, letter in GRADE_BANDS:
        if score >= floor:
            return letter
    return "F"


def grade_blurb(grade: str) -> str:
    return GRADE_BLURB.get(grade, "")
