"""Tests for posture orchestration (build_context + run_all + scoring)."""

from __future__ import annotations

from rag_scan.models import Severity

from rag_score.posture import Posture, assess, build_posture
from rag_score.tests._util import FIXTURES, finding


# ---- assess (pure) ---------------------------------------------------------


def test_assess_counts_by_severity():
    findings = [
        finding("A", Severity.CRITICAL),
        finding("B", Severity.WARNING),
        finding("C", Severity.WARNING),
        finding("D", Severity.INFO),
    ]
    p = assess(findings, env="prod")
    assert p.counts == {"critical": 1, "warning": 2, "info": 1}
    assert p.score == 100 - 25 - 8 - 8 - 2  # 57
    assert p.grade == "F"
    assert p.env == "prod"


def test_assess_clean_is_grade_a():
    p = assess([], env="prod")
    assert isinstance(p, Posture)
    assert p.grade == "A" and p.score == 100
    assert p.top_fixes == []
    assert p.blurb  # non-empty characterisation


def test_assess_populates_coverage_and_top_fixes():
    p = assess([finding("ACL002", Severity.CRITICAL)], env="prod")
    assert len(p.coverage) == 4
    assert [f.rule_id for f in p.top_fixes] == ["ACL002"]


# ---- build_posture (integration over fixtures) -----------------------------


def test_bad_config_grades_f():
    p = build_posture(
        env="prod",
        policy_path=str(FIXTURES / "bad_policy.yaml"),
        acl_path=str(FIXTURES / "bad_acl.yaml"),
        sample_docs_path=str(FIXTURES / "bad_sample_documents.json"),
    )
    assert p.grade == "F"
    assert p.counts["critical"] >= 1
    assert p.top_fixes


def test_good_config_grades_well():
    p = build_posture(
        env="prod",
        policy_path=str(FIXTURES / "good_policy.yaml"),
        acl_path=str(FIXTURES / "good_acl.yaml"),
    )
    assert p.counts["critical"] == 0
    assert p.grade in {"A", "B"}


def test_env_dev_suppresses_prod_only_rules_and_changes_grade():
    common = dict(
        policy_path=str(FIXTURES / "good_policy.yaml"),
        acl_path=str(FIXTURES / "bad_acl.yaml"),
    )
    dev = build_posture(env="dev", **common)
    prod = build_posture(env="prod", **common)
    # ACL001/SEC001 are prod-only criticals, so prod grades worse than dev.
    assert prod.score <= dev.score
    fired_prod = {f.rule_id for f in prod.findings}
    assert "ACL001" in fired_prod
    assert "ACL001" not in {f.rule_id for f in dev.findings}


def test_sample_docs_findings_lower_the_score():
    without = build_posture(
        env="prod",
        policy_path=str(FIXTURES / "good_policy.yaml"),
        acl_path=str(FIXTURES / "good_acl.yaml"),
    )
    with_bad = build_posture(
        env="prod",
        policy_path=str(FIXTURES / "good_policy.yaml"),
        acl_path=str(FIXTURES / "good_acl.yaml"),
        sample_docs_path=str(FIXTURES / "bad_sample_documents.json"),
    )
    assert with_bad.score < without.score
    assert "ACL002" in {f.rule_id for f in with_bad.findings}
