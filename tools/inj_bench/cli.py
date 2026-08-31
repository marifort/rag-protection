"""rag-injbench command-line interface.

Scores a versioned injection corpus against builtin scanners or any HTTP filter.

Usage:
  rag-injbench run --target builtin
  rag-injbench run --target http://localhost:8080/v1/scan --header "X-Admin-Key: secret"
  rag-injbench run --corpus sampler --published-only --baseline tools/inj_bench/baseline/builtin.json

Exit codes:
  0  metrics at or above baseline (or no baseline configured)
  1  regression vs baseline, or case failures when --fail-on-cases is set
  2  invalid corpus / baseline / target configuration
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional

from . import __version__
from .baseline import BaselineError, compare_report, serialize_baseline
from .corpus import CorpusError, load_corpus
from .report import render
from .runner import default_baseline_path, ensure_hash_embedder, run_benchmark


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rag-injbench",
        description="Prompt-injection benchmark — score a filter against a labeled corpus.",
    )
    parser.add_argument("--version", action="version", version=f"rag-injbench {__version__}")

    sub = parser.add_subparsers(dest="command")
    run = sub.add_parser("run", help="Run the benchmark against a target filter.")
    run.add_argument(
        "--target",
        default="builtin",
        help="builtin (shipped scanners) or an HTTP scan endpoint URL.",
    )
    run.add_argument(
        "--corpus",
        default="sampler",
        help="Corpus name or path. Default: sampler.",
    )
    run.add_argument(
        "--published-only",
        action="store_true",
        help="Run only corpus entries marked published=true (OSS sampler subset).",
    )
    run.add_argument(
        "--baseline",
        default=None,
        help="Baseline JSON for regression diff. Defaults to tools/inj_bench/baseline/<target>.json for builtin.",
    )
    run.add_argument(
        "--write-baseline",
        default=None,
        metavar="PATH",
        help="Write the computed metrics to a baseline file and exit 0.",
    )
    run.add_argument(
        "--header",
        action="append",
        default=[],
        metavar="NAME:VALUE",
        help="HTTP header for --target URL mode (repeatable).",
    )
    run.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="HTTP timeout in seconds for URL targets. Default: 30.",
    )
    run.add_argument(
        "--format",
        default="text",
        choices=["text", "json", "junit"],
        help="Report format. Default: text.",
    )
    run.add_argument("--output", default=None, help="Write report to this file instead of stdout.")
    run.add_argument(
        "--fail-on-cases",
        action="store_true",
        help="Exit 1 when any corpus case fails its expected verdict (even without --baseline).",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command != "run":
        parser.print_help(sys.stderr)
        return 2

    ensure_hash_embedder()

    try:
        corpus = load_corpus(args.corpus, published_only=args.published_only)
    except CorpusError as exc:
        report = _error_report(args.target, str(exc))
        _emit(render(report, args.format), args.output)
        return 2

    try:
        report = run_benchmark(
            corpus,
            target=args.target,
            http_headers=_parse_headers(args.header),
            http_timeout=args.timeout,
        )
    except (ValueError, RuntimeError) as exc:
        report = _error_report(args.target, str(exc))
        _emit(render(report, args.format), args.output)
        return 2

    if args.write_baseline:
        out = Path(args.write_baseline)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            serialize_baseline(report, corpus_path=args.corpus) + "\n",
            encoding="utf-8",
        )
        print(f"rag-injbench: baseline written to {args.write_baseline}")

    baseline_path = args.baseline
    if baseline_path is None and args.target == "builtin":
        baseline_path = default_baseline_path(args.target)

    if baseline_path and not args.write_baseline:
        try:
            report = compare_report(report, baseline_path)
        except BaselineError as exc:
            report.baseline_error = str(exc)
            _emit(render(report, args.format), args.output)
            return 2

    _emit(render(report, args.format), args.output)

    if report.baseline_regression:
        print("rag-injbench: regression vs baseline", file=sys.stderr)
        return 1
    if args.fail_on_cases and report.metrics.cases_passed < report.metrics.total:
        print("rag-injbench: one or more corpus cases failed", file=sys.stderr)
        return 1
    return 0


def _error_report(target: str, message: str):
    from .models import BenchMetrics, BenchReport

    return BenchReport(
        target=target,
        corpus="",
        results=[],
        metrics=BenchMetrics(),
        load_error=message,
    )


def _parse_headers(items: List[str]) -> Dict[str, str]:
    headers: Dict[str, str] = {}
    for item in items:
        if ":" not in item:
            raise ValueError(f"invalid --header (expected Name:Value): {item}")
        name, value = item.split(":", 1)
        headers[name.strip()] = value.strip()
    return headers


def _emit(text: str, output: Optional[str]) -> None:
    if output:
        Path(output).write_text(text + "\n", encoding="utf-8")
        print(f"rag-injbench: report written to {output}")
    else:
        print(text)


if __name__ == "__main__":
    raise SystemExit(main())
