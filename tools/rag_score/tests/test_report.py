"""Tests for the markdown / HTML / JSON reporters."""

from __future__ import annotations

import json

import pytest

from rag_scan.models import Severity

from rag_score import report
from rag_score.posture import assess
from rag_score.tests._util import finding


# ---- markdown --------------------------------------------------------------


def test_markdown_has_all_sections():
    md = report.render(assess([finding("ACL002", Severity.CRITICAL)], env="prod"), "markdown")
    assert "# Marifort Gate — RAG security posture scorecard" in md
    assert "## Grade:" in md
    assert "## OWASP LLM Top 10 coverage" in md
    assert "## Top fixes" in md
    assert "## Next step" in md
    assert report.ASSESSMENT_URL in md


def test_markdown_lists_top_fix_details():
    f = finding(
        "ACL002",
        Severity.CRITICAL,
        title="Confidential doc readable",
        message="payroll is all-staff",
        remediation="restrict groups",
        location="sample_documents.json",
    )
    md = report.render(assess([f], env="prod"), "markdown")
    assert "[ACL002] Confidential doc readable" in md
    assert "payroll is all-staff" in md
    assert "Fix: restrict groups" in md
    assert "sample_documents.json" in md


def test_markdown_clean_path_says_no_issues():
    md = report.render(assess([], env="prod"), "markdown")
    assert "nothing to fix" in md
    assert "Grade: A" in md


def test_markdown_includes_not_assessed_notes():
    md = report.render(assess([], env="prod"), "markdown")
    assert "LLM07:" in md and "LLM08:" in md
    assert "Lab 1" in md


# ---- html ------------------------------------------------------------------


def test_html_is_self_contained():
    out = report.render(assess([], env="prod"), "html")
    assert out.startswith("<!doctype html>")
    assert "<style>" in out and "</style>" in out
    assert out.rstrip().endswith("</html>")
    # No external resources (inline CSS only).
    assert "http-equiv" not in out
    assert ".css" not in out and "<script" not in out


def test_html_grade_badge_uses_grade_color():
    out = report.render(assess([], env="prod"), "html")  # grade A
    assert report._GRADE_COLOR["A"] in out
    assert ">A</div>" in out  # badge letter


def test_html_escapes_finding_content():
    nasty = finding(
        "ACL002",
        Severity.CRITICAL,
        title="<script>alert('xss')</script>",
        message="<img src=x onerror=alert(1)>",
        remediation="<b>bad</b>",
    )
    out = report.render(assess([nasty], env="prod"), "html")
    assert "<script>alert('xss')</script>" not in out
    assert "&lt;script&gt;" in out
    assert "<img src=x" not in out


def test_html_clean_path_renders_no_issues():
    out = report.render(assess([], env="prod"), "html")
    assert "nothing to fix" in out


# ---- json ------------------------------------------------------------------


def test_json_round_trips_core_fields():
    p = assess([finding("POL001", Severity.WARNING)], env="prod")
    data = json.loads(report.render(p, "json"))
    assert data["grade"] == p.grade
    assert data["score"] == p.score
    assert data["env"] == "prod"
    assert data["counts"] == {"critical": 0, "warning": 1, "info": 0}


def test_json_coverage_has_four_rows_with_notes():
    data = json.loads(report.render(assess([], env="prod"), "json"))
    assert len(data["owasp_coverage"]) == 4
    notes = {r["risk_id"]: r["note"] for r in data["owasp_coverage"]}
    assert notes["LLM07"] and notes["LLM08"]
    assert notes["LLM01"] == "" and notes["LLM06"] == ""


def test_json_top_fixes_serialises_findings():
    p = assess([finding("SEC001", Severity.CRITICAL, remediation="rotate")], env="prod")
    data = json.loads(report.render(p, "json"))
    assert data["top_fixes"][0]["rule_id"] == "SEC001"
    assert data["top_fixes"][0]["remediation"] == "rotate"


def test_json_clean_has_empty_top_fixes():
    data = json.loads(report.render(assess([], env="prod"), "json"))
    assert data["top_fixes"] == []


# ---- dispatch --------------------------------------------------------------


def test_unknown_format_raises_value_error():
    with pytest.raises(ValueError):
        report.render(assess([], env="prod"), "pdf")
