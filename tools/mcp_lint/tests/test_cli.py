"""Tests for the mcp-lint CLI: formats, exit codes, errors."""

from __future__ import annotations

import json

import pytest

from mcp_lint.cli import main
from mcp_lint.tests._util import BAD_MANIFEST, GOOD_MANIFEST


def test_scan_good_manifest_exits_zero(capsys):
    assert main(["scan", "--manifest", str(GOOD_MANIFEST)]) == 0
    assert "no issues found" in capsys.readouterr().out


def test_scan_bad_manifest_exits_one(capsys):
    assert main(["scan", "--manifest", str(BAD_MANIFEST)]) == 1
    assert "MCP001" in capsys.readouterr().out


def test_scan_info_only_passes_with_critical_gate(tmp_path):
    path = tmp_path / "info_only.json"
    path.write_text(
        json.dumps({"tools": [{"name": "legacy", "description": "Helper"}]}),
        encoding="utf-8",
    )
    assert main(["scan", "--manifest", str(path), "--severity", "critical"]) == 0


def test_missing_manifest_exits_two(capsys):
    assert main(["scan", "--manifest", "/nonexistent/tools.json"]) == 2
    assert "not found" in capsys.readouterr().out


def test_junit_output_to_file(tmp_path, capsys):
    out = tmp_path / "report.xml"
    assert main(["scan", "--manifest", str(BAD_MANIFEST), "--format", "junit", "--output", str(out)]) == 1
    assert "report written to" in capsys.readouterr().out
    assert "<testsuite" in out.read_text()


def test_sarif_to_stdout(capsys):
    assert main(["scan", "--manifest", str(BAD_MANIFEST), "--format", "sarif"]) == 1
    doc = json.loads(capsys.readouterr().out)
    assert doc["runs"][0]["tool"]["driver"]["name"] == "mcp-lint"


def test_version_flag_exits_zero(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert "mcp-lint" in capsys.readouterr().out


def test_scan_requires_manifest_or_url(capsys):
    with pytest.raises(SystemExit):
        main(["scan"])
