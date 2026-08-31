"""CLI integration tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from inj_bench.cli import main

BASELINE = str(Path(__file__).resolve().parents[1] / "baseline" / "builtin.json")


def test_run_builtin_exits_zero(capsys):
    assert main(["run", "--target", "builtin", "--baseline", BASELINE]) == 0
    assert "Detection rate" in capsys.readouterr().out


def test_published_only_runs(capsys):
    rc = main(["run", "--target", "builtin", "--published-only"])
    assert rc == 0
    assert "injection benchmark" in capsys.readouterr().out


def test_json_format(capsys):
    assert main(["run", "--target", "builtin", "--format", "json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["tool"] == "rag-injbench"
    assert "metrics" in data


def test_junit_format(capsys):
    assert main(["run", "--target", "builtin", "--format", "junit"]) == 0
    assert "<testsuite" in capsys.readouterr().out


def test_invalid_corpus_exits_two(tmp_path, capsys):
    bad = tmp_path / "bad.yaml"
    bad.write_text("version: 2\nname: x\nentries: []\n", encoding="utf-8")
    assert main(["run", "--corpus", str(bad)]) == 2
    assert "ERROR" in capsys.readouterr().out or "version" in capsys.readouterr().out


def test_invalid_target_exits_two(capsys):
    assert main(["run", "--target", "not-a-target"]) == 2


def test_write_baseline(tmp_path, capsys):
    out = tmp_path / "baseline.json"
    rc = main(["run", "--target", "builtin", "--write-baseline", str(out)])
    assert rc == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["version"] == 1
    assert "metrics" in data


def test_no_command_exits_two(capsys):
    assert main([]) == 2
