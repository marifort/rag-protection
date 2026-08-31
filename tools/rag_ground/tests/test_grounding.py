"""Tests for the core grounding logic, input normalization, and aggregation."""

from __future__ import annotations

import json

import pytest

from rag_ground.grounding import (
    DEFAULT_THRESHOLD,
    BatchResult,
    GroundingInputError,
    GroundingResult,
    build_policy,
    check_answer,
    check_jsonl,
    load_answer,
    load_jsonl,
    load_sources,
    normalize_sources,
)
from rag_ground.tests._util import (
    GROUNDED_ANSWER,
    LEAK_ANSWER,
    SOURCES,
    UNGROUNDED_ANSWER,
)

CHUNKS = [(c["id"], c["text"]) for c in SOURCES]


# ---- check_answer ----------------------------------------------------------


def test_grounded_answer_passes():
    r = check_answer(GROUNDED_ANSWER, CHUNKS)
    assert isinstance(r, GroundingResult)
    assert r.passed is True
    assert r.verdict == "grounded"
    assert r.coverage_ratio == 1.0
    assert r.ungrounded_claims == []


def test_ungrounded_answer_fails_and_lists_sentences():
    r = check_answer(UNGROUNDED_ANSWER, CHUNKS)
    assert r.passed is False
    assert r.verdict == "ungrounded"
    assert 0.0 < r.coverage_ratio < 1.0
    assert any("euro currency" in c.sentence for c in r.ungrounded_claims)


def test_system_prompt_leak_is_a_leak_verdict():
    r = check_answer(LEAK_ANSWER, CHUNKS)
    assert r.system_prompt_leak is True
    assert r.passed is False
    assert r.verdict == "leak"


def test_threshold_controls_pass_fail():
    # The ungrounded answer is 1/2 covered; a 0.5 threshold should pass it.
    lenient = check_answer(UNGROUNDED_ANSWER, CHUNKS, threshold=0.5)
    strict = check_answer(UNGROUNDED_ANSWER, CHUNKS, threshold=0.75)
    assert lenient.passed is True
    assert strict.passed is False


def test_entailment_flag_runs_offline():
    # --entailment uses HashEmbedder (lexical) -> no network / no model download.
    r = check_answer(GROUNDED_ANSWER, CHUNKS, entailment=True)
    assert r.verdict in {"grounded", "ungrounded"}


# ---- build_policy ----------------------------------------------------------


def test_build_policy_maps_threshold_and_keeps_claims_on():
    policy = build_policy(threshold=0.42, entailment=True, entailment_threshold=0.6)
    assert policy.min_citation_coverage == 0.42
    assert policy.per_claim_citations is True
    assert policy.block_system_prompt_leak is True
    assert policy.entailment_check is True
    assert policy.entailment_threshold == 0.6


# ---- normalize_sources -----------------------------------------------------


def test_normalize_accepts_list_of_dicts():
    out = normalize_sources([{"id": "a", "text": "hello"}])
    assert out == [("a", "hello")]


def test_normalize_accepts_bare_strings_with_index_ids():
    out = normalize_sources(["one", "two"])
    assert out == [("0", "one"), ("1", "two")]


def test_normalize_accepts_chunks_wrapper_and_content_key():
    out = normalize_sources({"chunks": [{"chunk_id": "x", "content": "body"}]})
    assert out == [("x", "body")]


def test_normalize_rejects_non_list():
    with pytest.raises(GroundingInputError):
        normalize_sources({"nope": 1})


def test_normalize_rejects_missing_text():
    with pytest.raises(GroundingInputError):
        normalize_sources([{"id": "a"}])


def test_normalize_rejects_empty_list():
    with pytest.raises(GroundingInputError):
        normalize_sources([])


# ---- loaders ---------------------------------------------------------------


def test_load_answer_reads_file(tmp_path):
    p = tmp_path / "ans.txt"
    p.write_text("hello world", encoding="utf-8")
    assert load_answer(str(p)) == "hello world"


def test_load_answer_missing_raises():
    with pytest.raises(GroundingInputError):
        load_answer("/nonexistent/ans.txt")


def test_load_answer_empty_raises(tmp_path):
    p = tmp_path / "ans.txt"
    p.write_text("   \n", encoding="utf-8")
    with pytest.raises(GroundingInputError):
        load_answer(str(p))


def test_load_sources_invalid_json_raises(tmp_path):
    p = tmp_path / "src.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(GroundingInputError):
        load_sources(str(p))


def test_load_jsonl_parses_records(tmp_path):
    p = tmp_path / "eval.jsonl"
    p.write_text(
        '{"answer": "a", "sources": ["s"]}\n\n{"answer": "b", "sources": ["t"]}\n',
        encoding="utf-8",
    )
    records = load_jsonl(str(p))
    assert len(records) == 2


def test_load_jsonl_bad_line_reports_line_number(tmp_path):
    p = tmp_path / "eval.jsonl"
    p.write_text('{"answer": "a", "sources": ["s"]}\n{bad}\n', encoding="utf-8")
    with pytest.raises(GroundingInputError) as exc:
        load_jsonl(str(p))
    assert "line 2" in str(exc.value)


def test_load_jsonl_empty_raises(tmp_path):
    p = tmp_path / "eval.jsonl"
    p.write_text("\n\n", encoding="utf-8")
    with pytest.raises(GroundingInputError):
        load_jsonl(str(p))


# ---- check_jsonl / batch aggregation ---------------------------------------


def test_check_jsonl_aggregates_pass_rate():
    records = [
        {"id": "g", "answer": GROUNDED_ANSWER, "sources": SOURCES},
        {"id": "u", "answer": UNGROUNDED_ANSWER, "sources": SOURCES},
    ]
    batch = check_jsonl(records)
    assert isinstance(batch, BatchResult)
    assert batch.total == 2
    assert batch.passed_count == 1
    assert batch.pass_rate == 0.5
    # default min-pass-rate is 1.0, so a 0.5 rate fails the gate.
    assert batch.gate_passed is False


def test_check_jsonl_counts_leaks():
    records = [{"id": "leak", "answer": LEAK_ANSWER, "sources": SOURCES}]
    batch = check_jsonl(records)
    assert batch.leak_count == 1
    assert batch.passed_count == 0


def test_check_jsonl_gate_passes_when_rate_met():
    records = [{"answer": GROUNDED_ANSWER, "sources": SOURCES}]
    batch = check_jsonl(records, min_pass_rate=1.0)
    assert batch.gate_passed is True


def test_check_jsonl_record_missing_sources_raises():
    with pytest.raises(GroundingInputError):
        check_jsonl([{"answer": "hi"}])


def test_check_jsonl_record_non_string_answer_raises():
    with pytest.raises(GroundingInputError):
        check_jsonl([{"answer": 123, "sources": ["s"]}])


def test_check_jsonl_preserves_ids_and_indices():
    records = [
        {"id": "first", "answer": GROUNDED_ANSWER, "sources": SOURCES},
        {"answer": GROUNDED_ANSWER, "sources": SOURCES},
    ]
    batch = check_jsonl(records)
    assert batch.results[0].id == "first"
    assert batch.results[0].index == 1
    assert batch.results[1].id is None
    assert batch.results[1].index == 2


def test_default_threshold_value():
    assert DEFAULT_THRESHOLD == 0.75
