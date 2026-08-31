"""rag-scan command-line interface.

Exit codes:
  0  clean (no findings at or above the fail severity)
  1  findings at or above the fail severity
  2  configuration could not be loaded / validated
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__
from . import baseline as baseline_mod
from .checks import run_all
from .context import ConfigLoadError, build_context
from .models import ScanReport, Severity
from .reporters import render

# Repo-relative defaults so `python -m rag_scan check` works out of the box.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_CONFIG = _REPO_ROOT / "rag-protection-proxy" / "config"
DEFAULT_POLICY = _DEFAULT_CONFIG / "policy.yaml"
DEFAULT_ACL = _DEFAULT_CONFIG / "acl_policy.yaml"
DEFAULT_SAMPLE_DOCS = _DEFAULT_CONFIG / "sample_documents.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rag-scan",
        description="Pre-production RAG config scanner (shift-left CI gate).",
    )
    parser.add_argument("--version", action="version", version=f"rag-scan {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="Load/validate policy + ACL YAML only.")
    _add_config_args(validate)

    check = sub.add_parser("check", help="Run all security checks.")
    _add_config_args(check)
    check.add_argument("--sample-docs", default=str(DEFAULT_SAMPLE_DOCS))
    check.add_argument("--qdrant", default=None, help="Optional Qdrant URL for live VEC001 probe.")
    check.add_argument("--env", default="dev", choices=["dev", "prod", "production"])
    check.add_argument("--format", default="text", choices=["text", "junit", "sarif"])
    check.add_argument("--output", default=None, help="Write report to file instead of stdout.")
    check.add_argument(
        "--severity",
        default="critical",
        choices=["critical", "warning", "info"],
        help="Minimum severity that fails CI (exit 1). Default: critical.",
    )
    check.add_argument(
        "--baseline",
        default=None,
        help="Suppress findings recorded in this baseline JSON file (brownfield repos).",
    )
    check.add_argument(
        "--write-baseline",
        default=None,
        metavar="PATH",
        help="Write current findings to PATH as a baseline and exit 0 (no CI gate).",
    )
    return parser


def _add_config_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--policy", default=str(DEFAULT_POLICY))
    p.add_argument("--acl", default=str(DEFAULT_ACL))


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "validate":
        return _cmd_validate(args)
    if args.command == "check":
        return _cmd_check(args)
    return 2


def _cmd_validate(args: argparse.Namespace) -> int:
    try:
        build_context(policy_path=args.policy, acl_path=args.acl)
    except ConfigLoadError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    print("rag-scan: policy and ACL loaded successfully.")
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    report = ScanReport()
    try:
        ctx = build_context(
            env=args.env,
            policy_path=args.policy,
            acl_path=args.acl,
            sample_docs_path=args.sample_docs,
            qdrant_url=args.qdrant,
        )
    except ConfigLoadError as exc:
        report.load_error = str(exc)
        _emit(render(report, args.format), args.output)
        return 2

    report.extend(run_all(ctx))

    # Snapshot mode: record current findings as the accepted baseline and stop.
    if args.write_baseline:
        Path(args.write_baseline).write_text(
            baseline_mod.serialize(report.findings) + "\n", encoding="utf-8"
        )
        print(
            f"rag-scan: wrote baseline with {len(report.findings)} finding(s) "
            f"to {args.write_baseline}"
        )
        return 0

    if args.baseline:
        try:
            baseline_mod.apply(report, baseline_mod.load_fingerprints(args.baseline))
        except baseline_mod.BaselineError as exc:
            print(f"[ERROR] {exc}", file=sys.stderr)
            return 2

    _emit(render(report, args.format), args.output)

    fail_at = Severity(args.severity)
    return 1 if report.has_at_or_above(fail_at) else 0


def _emit(text: str, output: Optional[str]) -> None:
    if output:
        Path(output).write_text(text + "\n", encoding="utf-8")
        print(f"rag-scan: report written to {output}")
    else:
        print(text)


if __name__ == "__main__":
    raise SystemExit(main())
