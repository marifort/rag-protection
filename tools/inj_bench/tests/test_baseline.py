"""Baseline load, serialize, and regression diff tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from inj_bench.baseline import BaselineError, compare_report, load_baseline, serialize_baseline
from inj_bench.corpus import load_corpus
from inj_bench.models import BenchMetrics, BenchReport
from inj_bench.runner import run_benchmark


def test_builtin_baseline_reproducible():
    corpus = load_corpus("sampler")
    first = run_benchmark(corpus, target="builtin")
    second = run_benchmark(corpus, target="builtin")
    assert first.metrics.detection_rate == second.metrics.detection_rate
    assert first.metrics.false_positive_rate == second.metrics.false_positive_rate
    assert first.metrics.cases_passed == second.metrics.cases_passed


def test_committed_baseline_matches(tmp_path):
    corpus = load_corpus("sampler")
    report = run_benchmark(corpus, target="builtin")
    baseline_path = Path(__file__).resolve().parents[1] / "baseline" / "builtin.json"
    baseline = load_baseline(str(baseline_path))
    assert report.metrics.detection_rate == baseline["metrics"]["detection_rate"]
    assert report.metrics.false_positive_rate == baseline["metrics"]["false_positive_rate"]


def test_regression_detected():
    corpus = load_corpus("sampler")
    report = run_benchmark(corpus, target="builtin")
    worse = BenchReport(
        target=report.target,
        corpus=report.corpus,
        results=report.results,
        metrics=BenchMetrics(
            total=report.metrics.total,
            should_catch=report.metrics.should_catch,
            caught=max(0, report.metrics.caught - 1),
            benign=report.metrics.benign,
            false_positives=report.metrics.false_positives,
            cases_passed=report.metrics.cases_passed,
            per_category=report.metrics.per_category,
        ),
    )
    baseline_json = serialize_baseline(report)
    baseline_path = Path(__file__).resolve().parent / "_baseline.json"
    baseline_path.write_text(baseline_json, encoding="utf-8")
    try:
        compared = compare_report(worse, str(baseline_path))
        assert compared.baseline_regression is True
        assert compared.baseline_diff is not None
    finally:
        baseline_path.unlink(missing_ok=True)


def test_invalid_baseline_raises(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(BaselineError):
        load_baseline(str(path))
