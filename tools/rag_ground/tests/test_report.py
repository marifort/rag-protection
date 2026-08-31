"""Tests for the text / json / junit reporters (single + batch)."""

from __future__ import annotations

import json

import pytest

from rag_ground import report
from rag_ground.grounding import check_answer, check_jsonl
from rag_ground.tests._util import (
    GROUNDED_ANSWER,
    LEAK_ANSWER,
    SOURCES,
    UNGROUNDED_ANSWER,
)

CHUNKS = [(c["id"], c["text"]) for c in SOURCES]


def _single(answer, **kw):
    return check_answer(answer, CHUNKS, **kw)


def _batch():
    return check_jsonl(
        [
            {"id": "g", "answer": GROUNDED_ANSWER, "sources": SOURCES},
            {"id": "u", "answer": UNGROUNDED_ANSWER, "sources": SOURCES},
            {"id": "leak", "answer": LEAK_ANSWER, "sources": SOURCES},
        ]
    )


# ---- text ------------------------------------------------------------------


def test_text_single_shows_verdict_and_disclaimer():
    out = report.render(_single(GROUNDED_ANSWER), "text")
    assert "Verdict: GROUNDED" in out
    assert "coverage 1.00" in out
    assert report.DISCLAIMER in out


def test_text_single_lists_ungrounded_sentences():
    out = report.render(_single(UNGROUNDED_ANSWER), "text")
    assert "Verdict: UNGROUNDED" in out
    assert "Ungrounded sentences" in out
    assert "euro currency" in out


def test_text_single_flags_leak():
    out = report.render(_single(LEAK_ANSWER), "text")
    assert "Verdict: LEAK" in out
    assert "System-prompt-like phrasing" in out


def test_text_batch_shows_pass_rate_and_items():
    out = report.render(_batch(), "text")
    assert "grounding check (batch)" in out
    assert "Pass rate: 1/3" in out
    assert "-> FAIL" in out
    assert "id=ex" not in out  # ids are the supplied ones
    assert "id=g" in out and "id=leak" in out
    assert "System-prompt leaks: 1" in out


# ---- json ------------------------------------------------------------------


def test_json_single_round_trips_core_fields():
    data = json.loads(report.render(_single(UNGROUNDED_ANSWER), "json"))
    assert data["tool"] == "rag-ground"
    assert data["mode"] == "single"
    assert data["verdict"] == "ungrounded"
    assert data["passed"] is False
    assert data["threshold"] == 0.75
    assert len(data["claims"]) >= 2
    assert any("euro currency" in s for s in data["ungrounded_sentences"])


def test_json_batch_has_items_and_aggregate():
    data = json.loads(report.render(_batch(), "json"))
    assert data["mode"] == "batch"
    assert data["total"] == 3
    assert data["passed_count"] == 1
    assert data["leak_count"] == 1
    assert data["gate_passed"] is False
    assert {i["id"] for i in data["items"]} == {"g", "u", "leak"}


# ---- junit -----------------------------------------------------------------


def test_junit_single_pass_has_no_failure():
    out = report.render(_single(GROUNDED_ANSWER), "junit")
    assert 'tests="1" failures="0"' in out
    assert "<failure" not in out


def test_junit_single_fail_has_failure():
    out = report.render(_single(UNGROUNDED_ANSWER), "junit")
    assert 'failures="1"' in out
    assert "<failure" in out


def test_junit_batch_counts_failures_and_escapes():
    out = report.render(_batch(), "junit")
    assert 'tests="3" failures="2"' in out
    assert "&lt;" in out or "<failure" in out  # escaped content present
    assert 'name="leak"' in out


# ---- dispatch --------------------------------------------------------------


def test_unknown_format_raises_value_error():
    with pytest.raises(ValueError):
        report.render(_single(GROUNDED_ANSWER), "pdf")
