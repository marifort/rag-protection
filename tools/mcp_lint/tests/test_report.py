"""Tests for text/junit/sarif reporters."""

from __future__ import annotations

import json

from mcp_lint.fetch import load_manifest
from mcp_lint.linter import lint_tools
from mcp_lint.models import Finding, LintReport, Severity
from mcp_lint.reporters import render
from mcp_lint.tests._util import BAD_MANIFEST


def test_text_reporter_lists_findings():
    report = lint_tools(load_manifest(BAD_MANIFEST))
    text = render(report, "text")
    assert "MCP001" in text
    assert "mcp-lint:" in text


def test_text_load_error():
    report = LintReport(load_error="manifest not found")
    assert "manifest not found" in render(report, "text")


def test_junit_reporter_has_failures():
    report = lint_tools(load_manifest(BAD_MANIFEST))
    xml = render(report, "junit")
    assert "<testsuite name=\"mcp-lint\"" in xml
    assert "<failure" in xml


def test_junit_load_error_is_error_testcase():
    report = LintReport(load_error="bad manifest")
    xml = render(report, "junit")
    assert 'errors="1"' in xml
    assert "<error" in xml


def test_sarif_reporter_is_valid_json():
    report = LintReport(
        findings=[
            Finding(
                rule_id="MCP001",
                severity=Severity.CRITICAL,
                title="Injection",
                message="bad desc",
                location="tool:evil",
                remediation="fix it",
            )
        ],
        tools_scanned=1,
    )
    doc = json.loads(render(report, "sarif"))
    assert doc["version"] == "2.1.0"
    assert doc["runs"][0]["results"][0]["ruleId"] == "MCP001"
