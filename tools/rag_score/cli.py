"""rag-score command-line interface.

Produces a shareable A–F RAG security posture scorecard by wrapping the shipped
``rag-scan`` checks. Pure top-of-funnel lead magnet: runs locally, uploads
nothing.

Exit codes:
  0  report produced (or grade at/above --fail-under, if set)
  1  grade is below --fail-under (opt-in CI gate)
  2  configuration could not be loaded / validated
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from rag_scan.cli import DEFAULT_ACL, DEFAULT_POLICY, DEFAULT_SAMPLE_DOCS
from rag_scan.context import ConfigLoadError

from . import __version__
from .posture import build_posture
from .report import render
from .scoring import GRADE_BANDS

_GRADES = [letter for _, letter in GRADE_BANDS]  # A, B, C, D, F


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rag-score",
        description="RAG security posture scorecard (A–F) — free self-serve grade.",
    )
    parser.add_argument("--version", action="version", version=f"rag-score {__version__}")
    parser.add_argument("--policy", default=str(DEFAULT_POLICY))
    parser.add_argument("--acl", default=str(DEFAULT_ACL))
    parser.add_argument("--sample-docs", default=str(DEFAULT_SAMPLE_DOCS))
    parser.add_argument(
        "--qdrant", default=None, help="Optional Qdrant URL for the live VEC001 probe."
    )
    parser.add_argument(
        "--env",
        default="prod",
        choices=["dev", "prod", "production"],
        help="Posture is graded for this environment. Default: prod.",
    )
    parser.add_argument(
        "--format",
        default="markdown",
        choices=["markdown", "html", "json"],
        help="Report format. Default: markdown (POSTURE.md).",
    )
    parser.add_argument(
        "--output", default=None, help="Write the report to this file instead of stdout."
    )
    parser.add_argument(
        "--fail-under",
        default=None,
        choices=_GRADES,
        help="Opt-in CI gate: exit 1 if the grade is worse than this letter.",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        posture = build_posture(
            env=args.env,
            policy_path=args.policy,
            acl_path=args.acl,
            sample_docs_path=args.sample_docs,
            qdrant_url=args.qdrant,
        )
    except ConfigLoadError as exc:
        print(f"[ERROR] configuration could not be loaded: {exc}", file=sys.stderr)
        return 2

    report = render(posture, args.format)
    _emit(report, args.output)

    if args.output:
        # Keep stdout useful when writing to a file (handy for CI logs / gists).
        print(f"rag-score: grade {posture.grade} ({posture.score}/100)")

    if args.fail_under and _is_worse(posture.grade, args.fail_under):
        print(
            f"rag-score: grade {posture.grade} is below --fail-under {args.fail_under}",
            file=sys.stderr,
        )
        return 1
    return 0


def _is_worse(grade: str, threshold: str) -> bool:
    """True if ``grade`` ranks below ``threshold`` (A best, F worst)."""
    return _GRADES.index(grade) > _GRADES.index(threshold)


def _emit(text: str, output: Optional[str]) -> None:
    if output:
        Path(output).write_text(text + "\n", encoding="utf-8")
        print(f"rag-score: report written to {output}")
    else:
        print(text)


if __name__ == "__main__":
    raise SystemExit(main())
