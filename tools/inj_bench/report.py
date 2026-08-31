"""Render an injection benchmark report as text / json / junit."""

from __future__ import annotations

import json
from typing import List
from xml.sax.saxutils import escape, quoteattr

from .models import BenchReport, CaseResult

PRODUCT_NAME = "Marifort Gate"
DISCLAIMER = (
    "Regression yardstick for injection filters, not a guarantee of injection safety. "
    "The public sampler is an intentionally small subset; runs entirely locally."
)


def render(report: BenchReport, fmt: str) -> str:
    formatters = {"text": render_text, "json": render_json, "junit": render_junit}
    try:
        return formatters[fmt](report)
    except KeyError as exc:
        raise ValueError(f"unknown report format: {fmt}") from exc


def render_text(report: BenchReport) -> str:
    lines: List[str] = []
    lines.append(f"{PRODUCT_NAME} — injection benchmark")
    lines.append("")
    lines.append(f"Target: {report.target}")
    lines.append(f"Corpus: {report.corpus}")
    lines.append("")

    if report.load_error:
        lines.append(f"[ERROR] {report.load_error}")
        return "\n".join(lines)

    m = report.metrics
    lines.append(
        f"Detection rate: {m.caught}/{m.should_catch} ({m.detection_rate:.2%})"
    )
    lines.append(
        f"False-positive rate: {m.false_positives}/{m.benign} ({m.false_positive_rate:.2%})"
    )
    lines.append(f"Case pass rate: {m.cases_passed}/{m.total} ({m.pass_rate:.2%})")
    lines.append("")

    if m.per_category:
        lines.append("Per-category detection:")
        for name, bucket in sorted(m.per_category.items()):
            lines.append(
                f"  {name}: {bucket.caught}/{bucket.should_catch} "
                f"({bucket.detection_rate:.2%})"
            )
        lines.append("")

    if report.baseline_diff:
        lines.append("Baseline diff:")
        for metric, values in report.baseline_diff.items():
            lines.append(
                f"  {metric}: expected {values['expected']}, "
                f"actual {values['actual']} (delta {values['delta']:+})"
            )
        if report.baseline_regression:
            lines.append("  -> REGRESSION vs baseline")
        lines.append("")

    failures = [r for r in report.results if not r.passed]
    if failures:
        lines.append(f"Failed cases ({len(failures)}):")
        for result in failures:
            lines.append(_format_failure(result))
        lines.append("")

    lines.append("---")
    lines.append(DISCLAIMER)
    return "\n".join(lines)


def render_json(report: BenchReport) -> str:
    payload = {
        "tool": "rag-injbench",
        "product": PRODUCT_NAME,
        "target": report.target,
        "corpus": report.corpus,
        "load_error": report.load_error,
        "baseline_error": report.baseline_error,
        "baseline_regression": report.baseline_regression,
        "baseline_diff": report.baseline_diff,
        "metrics": _json_metrics(report),
        "cases": [_json_case(result) for result in report.results],
        "disclaimer": DISCLAIMER,
    }
    return json.dumps(payload, indent=2)


def render_junit(report: BenchReport) -> str:
    if report.load_error:
        body = (
            '  <testcase classname="rag-injbench" name="corpus-load">\n'
            f"    <error message={quoteattr(report.load_error)}/>\n"
            "  </testcase>\n"
        )
        return _suite(body, tests=1, failures=0, errors=1)

    cases = [_junit_case(result) for result in report.results]
    failures = sum(1 for result in report.results if not result.passed)
    if report.baseline_regression:
        failures += 1
        cases.append(
            '  <testcase classname="rag-injbench" name="baseline-regression">\n'
            '    <failure message="metrics regressed vs baseline"/>\n'
            "  </testcase>"
        )
    body = "\n".join(cases) + "\n"
    tests = len(report.results) + (1 if report.baseline_regression else 0)
    return _suite(body, tests=tests, failures=failures, errors=0)


def _json_metrics(report: BenchReport) -> dict:
    m = report.metrics
    return {
        "detection_rate": round(m.detection_rate, 4),
        "false_positive_rate": round(m.false_positive_rate, 4),
        "pass_rate": round(m.pass_rate, 4),
        "total": m.total,
        "should_catch": m.should_catch,
        "caught": m.caught,
        "benign": m.benign,
        "false_positives": m.false_positives,
        "per_category": {
            name: {
                "should_catch": bucket.should_catch,
                "caught": bucket.caught,
                "detection_rate": round(bucket.detection_rate, 4),
            }
            for name, bucket in sorted(m.per_category.items())
        },
    }


def _json_case(result: CaseResult) -> dict:
    return {
        "id": result.entry.id,
        "category": result.entry.category,
        "vector": result.entry.vector,
        "expected": result.entry.expected,
        "actual": result.actual,
        "caught": result.caught,
        "max_severity": result.max_severity,
        "passed": result.passed,
        "findings": [
            {
                "scanner": f.scanner,
                "category": f.category,
                "severity": f.severity,
                "detail": f.detail,
            }
            for f in result.findings
        ],
    }


def _format_failure(result: CaseResult) -> str:
    finding = ""
    if result.findings:
        top = max(result.findings, key=lambda f: f.severity)
        finding = f" via {top.scanner}/{top.category} ({top.severity:.2f})"
    return (
        f"  - {result.entry.id}: expected {result.entry.expected}, "
        f"got {result.actual}{finding}"
    )


def _junit_case(result: CaseResult) -> str:
    name = result.entry.id
    case_attr = f'classname="rag-injbench" name={quoteattr(name)}'
    if result.passed:
        return f"  <testcase {case_attr}/>"
    msg = quoteattr(
        f"expected {result.entry.expected}, got {result.actual} "
        f"(severity {result.max_severity:.2f})"
    )
    detail = _format_failure(result).strip()
    return (
        f"  <testcase {case_attr}>\n"
        f"    <failure message={msg}>{escape(detail)}</failure>\n"
        f"  </testcase>"
    )


def _suite(body: str, *, tests: int, failures: int, errors: int) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<testsuite name="rag-injbench" tests="{tests}" '
        f'failures="{failures}" errors="{errors}">\n'
        f"{body}"
        "</testsuite>\n"
    )
