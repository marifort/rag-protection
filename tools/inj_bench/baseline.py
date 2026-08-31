"""Baseline metrics for injection-benchmark regression gates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from .models import BenchMetrics, BenchReport

BASELINE_VERSION = 1


class BaselineError(Exception):
    """Raised when a baseline file cannot be parsed (CLI exit code 2)."""


def load_baseline(path: str) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        raise BaselineError(f"baseline file not found: {path}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BaselineError(f"invalid baseline JSON ({path}): {exc}") from exc
    if not isinstance(data, dict):
        raise BaselineError("baseline root must be a JSON object")
    if data.get("version") != BASELINE_VERSION:
        raise BaselineError(f"baseline version must be {BASELINE_VERSION}")
    metrics = data.get("metrics")
    if not isinstance(metrics, dict):
        raise BaselineError("baseline must include a 'metrics' object")
    return data


def compare_report(
    report: BenchReport,
    baseline_path: str,
    *,
    detection_tolerance: float = 0.0,
    fp_tolerance: float = 0.0,
) -> BenchReport:
    try:
        baseline = load_baseline(baseline_path)
    except BaselineError as exc:
        report.baseline_error = str(exc)
        return report

    expected = baseline.get("metrics", {})
    actual = _metrics_snapshot(report.metrics)
    diff = _diff_metrics(expected, actual)
    report.baseline_diff = diff

    detection_regressed = actual["detection_rate"] + detection_tolerance < float(
        expected.get("detection_rate", 0.0)
    )
    fp_regressed = actual["false_positive_rate"] > float(
        expected.get("false_positive_rate", 0.0)
    ) + fp_tolerance
    report.baseline_regression = detection_regressed or fp_regressed
    return report


def serialize_baseline(
    report: BenchReport,
    *,
    corpus_path: str = "",
    note: str = "",
) -> str:
    doc = {
        "version": BASELINE_VERSION,
        "target": report.target,
        "corpus": report.corpus,
        "corpus_path": corpus_path,
        "note": note,
        "metrics": _metrics_snapshot(report.metrics),
    }
    return json.dumps(doc, indent=2)


def _metrics_snapshot(metrics: BenchMetrics) -> Dict[str, Any]:
    return {
        "detection_rate": round(metrics.detection_rate, 4),
        "false_positive_rate": round(metrics.false_positive_rate, 4),
        "pass_rate": round(metrics.pass_rate, 4),
        "total": metrics.total,
        "should_catch": metrics.should_catch,
        "caught": metrics.caught,
        "benign": metrics.benign,
        "false_positives": metrics.false_positives,
        "per_category": {
            name: {
                "should_catch": bucket.should_catch,
                "caught": bucket.caught,
                "detection_rate": round(bucket.detection_rate, 4),
            }
            for name, bucket in sorted(metrics.per_category.items())
        },
    }


def _diff_metrics(expected: Dict[str, Any], actual: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "detection_rate": {
            "expected": expected.get("detection_rate"),
            "actual": actual.get("detection_rate"),
            "delta": round(
                float(actual.get("detection_rate", 0.0))
                - float(expected.get("detection_rate", 0.0)),
                4,
            ),
        },
        "false_positive_rate": {
            "expected": expected.get("false_positive_rate"),
            "actual": actual.get("false_positive_rate"),
            "delta": round(
                float(actual.get("false_positive_rate", 0.0))
                - float(expected.get("false_positive_rate", 0.0)),
                4,
            ),
        },
        "pass_rate": {
            "expected": expected.get("pass_rate"),
            "actual": actual.get("pass_rate"),
            "delta": round(
                float(actual.get("pass_rate", 0.0)) - float(expected.get("pass_rate", 0.0)),
                4,
            ),
        },
    }
