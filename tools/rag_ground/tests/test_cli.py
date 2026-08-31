"""Tests for the rag-ground CLI: modes, formats, exit codes, gates."""

from __future__ import annotations

import json

import pytest

from rag_ground.cli import main
from rag_ground.tests._util import EXAMPLES, GROUNDED_ANSWER, SOURCES

ANSWER = str(EXAMPLES / "answer.txt")
SOURCES_JSON = str(EXAMPLES / "sources.json")
EVAL_JSONL = str(EXAMPLES / "eval.jsonl")


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return str(p)


def _grounded_inputs(tmp_path):
    ans = _write(tmp_path, "ans.txt", GROUNDED_ANSWER)
    src = _write(tmp_path, "src.json", json.dumps(SOURCES))
    return ["--answer", ans, "--sources", src]


# ---- single mode -----------------------------------------------------------


def test_single_grounded_exits_zero(tmp_path, capsys):
    assert main(["check", *_grounded_inputs(tmp_path)]) == 0
    assert "Verdict: GROUNDED" in capsys.readouterr().out


def test_single_ungrounded_exits_one(capsys):
    # The shipped example answer is only 50% grounded -> fails the 0.75 gate.
    assert main(["check", "--answer", ANSWER, "--sources", SOURCES_JSON]) == 1
    assert "Verdict: UNGROUNDED" in capsys.readouterr().out


def test_single_threshold_relaxation_flips_to_zero():
    assert main(["check", "--answer", ANSWER, "--sources", SOURCES_JSON, "--threshold", "0.5"]) == 0


# ---- batch mode ------------------------------------------------------------


def test_batch_default_gate_fails(capsys):
    assert main(["check", "--jsonl", EVAL_JSONL]) == 1
    assert "Pass rate" in capsys.readouterr().out


def test_batch_min_pass_rate_can_pass():
    # 1/3 grounded; a 0.3 floor is met.
    assert main(["check", "--jsonl", EVAL_JSONL, "--min-pass-rate", "0.3"]) == 0


# ---- formats / output ------------------------------------------------------


def test_json_format(capsys, tmp_path):
    assert main(["check", *_grounded_inputs(tmp_path), "--format", "json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["tool"] == "rag-ground"


def test_junit_format(capsys, tmp_path):
    assert main(["check", *_grounded_inputs(tmp_path), "--format", "junit"]) == 0
    assert "<testsuite" in capsys.readouterr().out


def test_output_to_file(tmp_path, capsys):
    out = tmp_path / "grounding.json"
    rc = main(["check", *_grounded_inputs(tmp_path), "--format", "json", "--output", str(out)])
    assert rc == 0
    assert "report written to" in capsys.readouterr().out
    assert json.loads(out.read_text())["mode"] == "single"


# ---- input validation / errors ---------------------------------------------


def test_no_inputs_exits_two(capsys):
    assert main(["check"]) == 2
    assert "provide either" in capsys.readouterr().err


def test_ambiguous_inputs_exit_two():
    assert main(["check", "--jsonl", EVAL_JSONL, "--answer", ANSWER]) == 2


def test_missing_answer_file_exits_two(capsys):
    assert main(["check", "--answer", "/nope.txt", "--sources", SOURCES_JSON]) == 2
    assert "invalid input" in capsys.readouterr().err


def test_bad_sources_json_exits_two(tmp_path):
    bad = _write(tmp_path, "bad.json", "{not json")
    assert main(["check", "--answer", ANSWER, "--sources", bad]) == 2


def test_no_subcommand_exits_two():
    assert main([]) == 2


def test_version_flag_exits_zero(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert "rag-ground" in capsys.readouterr().out
