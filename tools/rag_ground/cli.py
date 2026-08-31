"""rag-ground command-line interface.

Scores an LLM answer against the source chunks it was supposed to be grounded in,
by wrapping the shipped ``verify_citations`` output guardrail. Standalone OSS
lead magnet: runs locally, uploads nothing.

Usage:
  rag-ground check --answer tools/rag_ground/examples/answer.txt --sources tools/rag_ground/examples/sources.json
  rag-ground check --jsonl tools/rag_ground/examples/eval.jsonl

Exit codes:
  0  grounded (single) / pass rate >= --min-pass-rate (batch)
  1  ungrounded or system-prompt leak (single) / pass rate below the gate (batch)
  2  invalid input (missing file, bad JSON, malformed record)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__
from .grounding import (
    DEFAULT_ENTAILMENT_THRESHOLD,
    DEFAULT_MIN_PASS_RATE,
    DEFAULT_THRESHOLD,
    GroundingInputError,
    check_answer,
    check_jsonl,
    load_answer,
    load_jsonl,
    load_sources,
)
from .report import render


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rag-ground",
        description="Grounding / hallucination check — score an answer against its sources.",
    )
    parser.add_argument("--version", action="version", version=f"rag-ground {__version__}")

    sub = parser.add_subparsers(dest="command")
    check = sub.add_parser("check", help="Check an answer (or a batch) for grounding.")

    src = check.add_argument_group("inputs (provide --answer + --sources, or --jsonl)")
    src.add_argument("--answer", help="Path to a file containing the answer text.")
    src.add_argument(
        "--sources",
        help="Path to a JSON file of source chunks: [{id, text}] or a list of strings.",
    )
    src.add_argument(
        "--jsonl",
        help="Path to a batch eval set: one {answer, sources, [id]} JSON object per line.",
    )

    check.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help=f"Min coverage ratio for an answer to pass. Default: {DEFAULT_THRESHOLD}.",
    )
    check.add_argument(
        "--entailment",
        action="store_true",
        help="Enable offline lexical entailment scoring for paraphrased answers.",
    )
    check.add_argument(
        "--entailment-threshold",
        type=float,
        default=DEFAULT_ENTAILMENT_THRESHOLD,
        help=f"Min entailment score when --entailment is set. Default: {DEFAULT_ENTAILMENT_THRESHOLD}.",
    )
    check.add_argument(
        "--min-pass-rate",
        type=float,
        default=DEFAULT_MIN_PASS_RATE,
        help=(
            "Batch gate: exit 1 if the aggregate pass rate is below this. "
            f"Default: {DEFAULT_MIN_PASS_RATE} (every answer must be grounded)."
        ),
    )
    check.add_argument(
        "--format",
        default="text",
        choices=["text", "json", "junit"],
        help="Report format. Default: text.",
    )
    check.add_argument(
        "--output", default=None, help="Write the report to this file instead of stdout."
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command != "check":
        parser.print_help(sys.stderr)
        return 2

    mode = _resolve_mode(args)
    if mode is None:
        print(
            "[ERROR] provide either --answer and --sources, or --jsonl",
            file=sys.stderr,
        )
        return 2

    try:
        if mode == "batch":
            result = check_jsonl(
                load_jsonl(args.jsonl),
                threshold=args.threshold,
                entailment=args.entailment,
                entailment_threshold=args.entailment_threshold,
                min_pass_rate=args.min_pass_rate,
            )
            gate_passed = result.gate_passed
        else:
            single = check_answer(
                load_answer(args.answer),
                load_sources(args.sources),
                threshold=args.threshold,
                entailment=args.entailment,
                entailment_threshold=args.entailment_threshold,
            )
            result = single
            gate_passed = single.passed
    except GroundingInputError as exc:
        print(f"[ERROR] invalid input: {exc}", file=sys.stderr)
        return 2

    report = render(result, args.format)
    _emit(report, args.output)

    return 0 if gate_passed else 1


def _resolve_mode(args: argparse.Namespace) -> Optional[str]:
    has_single = bool(args.answer) and bool(args.sources)
    has_batch = bool(args.jsonl)
    if has_batch and (args.answer or args.sources):
        return None  # ambiguous: both modes requested
    if has_batch:
        return "batch"
    if has_single:
        return "single"
    return None


def _emit(text: str, output: Optional[str]) -> None:
    if output:
        Path(output).write_text(text + "\n", encoding="utf-8")
        print(f"rag-ground: report written to {output}")
    else:
        print(text)


if __name__ == "__main__":
    raise SystemExit(main())
