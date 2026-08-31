"""Tests for the weighted score and A–F grade banding."""

from __future__ import annotations

import pytest

from rag_scan.models import Severity

from rag_score import scoring
from rag_score.tests._util import finding


# ---- weighting -------------------------------------------------------------


def test_clean_config_scores_100():
    assert scoring.score_findings([]) == scoring.BASE_SCORE == 100


def test_single_severity_weights():
    assert scoring.score_findings([finding("X", Severity.CRITICAL)]) == 75
    assert scoring.score_findings([finding("X", Severity.WARNING)]) == 92
    assert scoring.score_findings([finding("X", Severity.INFO)]) == 98


def test_mixed_severities_sum():
    mixed = [
        finding("A", Severity.CRITICAL),
        finding("B", Severity.WARNING),
        finding("C", Severity.INFO),
    ]
    assert scoring.score_findings(mixed) == 100 - 25 - 8 - 2  # 65


def test_score_clamps_to_zero_not_negative():
    many = [finding(f"R{i}", Severity.CRITICAL) for i in range(10)]
    assert scoring.score_findings(many) == 0


def test_score_never_exceeds_100():
    # Defensive: even an empty/odd input cannot push above the base.
    assert scoring.score_findings([]) <= 100


def test_weights_table_matches_spec():
    assert scoring.WEIGHTS[Severity.CRITICAL] == -25
    assert scoring.WEIGHTS[Severity.WARNING] == -8
    assert scoring.WEIGHTS[Severity.INFO] == -2


# ---- grade banding ---------------------------------------------------------


@pytest.mark.parametrize(
    "score,grade",
    [
        (100, "A"), (95, "A"), (90, "A"),
        (89, "B"), (85, "B"), (80, "B"),
        (79, "C"), (75, "C"), (70, "C"),
        (69, "D"), (65, "D"), (60, "D"),
        (59, "F"), (30, "F"), (0, "F"),
    ],
)
def test_grade_bands_boundaries(score, grade):
    assert scoring.grade_for_score(score) == grade


def test_every_grade_has_a_blurb():
    for _, letter in scoring.GRADE_BANDS:
        assert scoring.grade_blurb(letter), f"missing blurb for {letter}"


def test_unknown_grade_blurb_is_empty_string():
    assert scoring.grade_blurb("Z") == ""
