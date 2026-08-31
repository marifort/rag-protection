"""mcp-lint command-line interface.

Statically lint MCP tool manifests for description injection and over-broad scopes.

Exit codes:
  0  clean (no findings at or above the fail severity)
  1  findings at or above the fail severity
  2  manifest could not be loaded / MCP server unreachable
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__
from .fetch import ManifestError, fetch_live, load_manifest
from .linter import lint_tools
from .models import LintReport, Severity
from .reporters import render


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mcp-lint",
        description="MCP manifest / tool-description linter — shift-left CI gate for MCP servers.",
    )
    parser.add_argument("--version", action="version", version=f"mcp-lint {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="Lint tool descriptions from a manifest file or live MCP URL.")
    src = scan.add_mutually_exclusive_group(required=True)
    src.add_argument("--manifest", help="Path to a saved tools/list JSON file.")
    src.add_argument("--url", help="Live MCP Streamable HTTP endpoint (e.g. http://mcp:8000/mcp).")
    scan.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="HTTP timeout for --url mode. Default: 30.",
    )
    scan.add_argument("--format", default="text", choices=["text", "junit", "sarif"])
    scan.add_argument("--output", default=None, help="Write report to file instead of stdout.")
    scan.add_argument(
        "--severity",
        default="warning",
        choices=["critical", "warning", "info"],
        help="Minimum severity that fails CI (exit 1). Default: warning.",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "scan":
        return _cmd_scan(args)
    return 2


def _cmd_scan(args: argparse.Namespace) -> int:
    report = LintReport()
    try:
        if args.manifest:
            tools = load_manifest(args.manifest)
        else:
            tools = fetch_live(args.url, timeout=args.timeout)
    except ManifestError as exc:
        report.load_error = str(exc)
        _emit(render(report, args.format), args.output)
        return 2

    report = lint_tools(tools)
    _emit(render(report, args.format), args.output)

    fail_at = Severity(args.severity)
    return 1 if report.has_at_or_above(fail_at) else 0


def _emit(text: str, output: Optional[str]) -> None:
    if output:
        Path(output).write_text(text + "\n", encoding="utf-8")
        print(f"mcp-lint: report written to {output}")
    else:
        print(text)


if __name__ == "__main__":
    raise SystemExit(main())
