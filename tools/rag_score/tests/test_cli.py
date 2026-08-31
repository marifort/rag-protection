"""Tests for the rag-score CLI: formats, output, fail-under gate, exit codes."""

from __future__ import annotations

import json

import pytest

from rag_score.cli import _is_worse, main
from rag_score.tests._util import FIXTURES

GOOD = ["--policy", str(FIXTURES / "good_policy.yaml"), "--acl", str(FIXTURES / "good_acl.yaml")]
BAD = [
    "--policy", str(FIXTURES / "bad_policy.yaml"),
    "--acl", str(FIXTURES / "bad_acl.yaml"),
    "--sample-docs", str(FIXTURES / "bad_sample_documents.json"),
]


# ---- default output --------------------------------------------------------


def test_markdown_to_stdout_by_default(capsys):
    assert main(["--env", "prod", *GOOD]) == 0
    out = capsys.readouterr().out
    assert "## Grade:" in out


def test_html_format_to_stdout(capsys):
    assert main(["--env", "prod", "--format", "html", *GOOD]) == 0
    assert capsys.readouterr().out.lstrip().startswith("<!doctype html>")


def test_json_to_file_and_grade_echo(tmp_path, capsys):
    out = tmp_path / "posture.json"
    assert main(["--env", "prod", "--format", "json", "--output", str(out), *GOOD]) == 0
    stdout = capsys.readouterr().out
    assert "report written to" in stdout
    assert "rag-score: grade" in stdout
    data = json.loads(out.read_text())
    assert data["grade"] in {"A", "B"}


# ---- fail-under gate -------------------------------------------------------


def test_fail_under_returns_1_when_worse(capsys):
    assert main(["--env", "prod", "--fail-under", "C", *BAD]) == 1
    assert "below --fail-under" in capsys.readouterr().err


def test_fail_under_equal_grade_passes():
    # Bad config grades F; --fail-under F is the floor, so equal is acceptable.
    assert main(["--env", "prod", "--fail-under", "F", *BAD]) == 0


def test_fail_under_better_grade_passes():
    assert main(["--env", "prod", "--fail-under", "B", *GOOD]) == 0


def test_no_fail_under_is_always_zero_on_load():
    assert main(["--env", "prod", *BAD]) == 0  # report still produced


def test_is_worse_ordering():
    assert _is_worse("F", "C") is True
    assert _is_worse("A", "C") is False
    assert _is_worse("C", "C") is False


# ---- env -------------------------------------------------------------------


def test_env_default_is_prod(capsys):
    # No --env: prod-only rules apply, so the demo bad ACL fails a B gate.
    assert main(["--fail-under", "B", *BAD]) == 1


# ---- errors / meta ---------------------------------------------------------


def test_config_load_error_exits_two(capsys):
    assert main(["--policy", "/nonexistent/policy.yaml"]) == 2
    assert "could not be loaded" in capsys.readouterr().err


def test_invalid_policy_exits_two(capsys):
    assert main(["--policy", str(FIXTURES / "invalid_policy.yaml")]) == 2


def test_version_flag_exits_zero(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert "rag-score" in capsys.readouterr().out
