"""Tests for the OWASP LLM mapping, coverage rows, and top-fix selection."""

from __future__ import annotations

from rag_scan.models import Severity

from rag_score import owasp
from rag_score.tests._util import SCANNER_RULE_IDS, finding


# ---- rule -> OWASP mapping completeness ------------------------------------


def test_every_scanner_rule_is_mapped_to_a_risk():
    # If a new rag-scan rule ships, it must be attributed to an OWASP risk here.
    assert set(owasp.RULE_TO_RISK) == SCANNER_RULE_IDS


def test_mapped_risks_all_have_display_names():
    for risk_id in set(owasp.RULE_TO_RISK.values()):
        assert risk_id in owasp.RISK_NAMES


def test_assessed_and_not_assessed_risks_are_disjoint_and_named():
    assert not set(owasp.ASSESSED_RISKS) & set(owasp.NOT_ASSESSED_RISKS)
    for risk_id in owasp.ASSESSED_RISKS + owasp.NOT_ASSESSED_RISKS:
        assert risk_id in owasp.RISK_NAMES


# ---- coverage --------------------------------------------------------------


def test_coverage_has_four_rows_in_fixed_order():
    rows = owasp.build_coverage([])
    assert [r.risk_id for r in rows] == ["LLM01", "LLM06", "LLM07", "LLM08"]


def test_coverage_clean_when_no_findings():
    rows = {r.risk_id: r for r in owasp.build_coverage([])}
    assert rows["LLM01"].status == "clean"
    assert rows["LLM06"].status == "clean"


def test_coverage_not_assessed_rows_always_present_with_note():
    rows = {r.risk_id: r for r in owasp.build_coverage([finding("ACL002", Severity.CRITICAL)])}
    for risk_id in ("LLM07", "LLM08"):
        assert rows[risk_id].status == "not-assessed"
        assert rows[risk_id].note
        assert rows[risk_id].status_label == "Not assessed here"


def test_coverage_reflects_worst_severity_per_risk():
    findings = [
        finding("ACL003", Severity.WARNING),   # LLM06
        finding("ACL002", Severity.CRITICAL),  # LLM06 (worse)
        finding("POL001", Severity.WARNING),   # LLM01
    ]
    rows = {r.risk_id: r for r in owasp.build_coverage(findings)}
    assert rows["LLM06"].status == "critical"
    assert rows["LLM06"].rule_ids == ["ACL002", "ACL003"]  # sorted, de-duped
    assert rows["LLM01"].status == "warning"


def test_coverage_info_only_risk_is_info_status():
    rows = {r.risk_id: r for r in owasp.build_coverage([finding("POL001", Severity.INFO)])}
    assert rows["LLM01"].status == "info"


def test_status_label_maps_each_status():
    rows = owasp.build_coverage([finding("ACL002", Severity.CRITICAL)])
    for row in rows:
        assert row.status_label  # every status renders to a non-empty label


# ---- top fixes -------------------------------------------------------------


def test_top_fixes_orders_by_severity_then_rule_id():
    findings = [
        finding("POL001", Severity.WARNING),
        finding("SEC001", Severity.CRITICAL),
        finding("ACL002", Severity.CRITICAL),
    ]
    fixes = owasp.top_fixes(findings)
    assert [f.rule_id for f in fixes] == ["ACL002", "SEC001", "POL001"]


def test_top_fixes_dedupes_identical_rule_and_remediation():
    findings = [
        finding("ACL002", Severity.CRITICAL, remediation="restrict groups", location="doc1"),
        finding("ACL002", Severity.CRITICAL, remediation="restrict groups", location="doc2"),
    ]
    fixes = owasp.top_fixes(findings)
    assert len(fixes) == 1


def test_top_fixes_keeps_distinct_remediations_for_same_rule():
    findings = [
        finding("ACL002", Severity.CRITICAL, remediation="restrict groups"),
        finding("ACL002", Severity.CRITICAL, remediation="re-tag classification"),
    ]
    assert len(owasp.top_fixes(findings)) == 2


def test_top_fixes_respects_limit():
    findings = [finding(f"R{i}", Severity.WARNING, remediation=f"fix{i}") for i in range(5)]
    assert len(owasp.top_fixes(findings, limit=3)) == 3
    assert len(owasp.top_fixes(findings, limit=2)) == 2


def test_top_fixes_empty_when_no_findings():
    assert owasp.top_fixes([]) == []
