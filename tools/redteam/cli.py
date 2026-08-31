"""rag-redteam command-line interface.

Exit codes:
  0  all scenarios passed
  1  one or more scenarios failed
  2  configuration / connectivity error
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List

from . import __version__
from .client import RedTeamClient, RedTeamClientError
from .report import render_report, write_report
from .runner import load_and_run, run_scenarios, write_results
from .scenario import ScenarioLoadError, list_scenarios, load_scenario


def default_scenarios_dir() -> Path:
    return Path(__file__).resolve().parent / "scenarios"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rag-redteam",
        description="Packaged RAG red-team harness — scenario-based consulting deliverable (Lab 5).",
    )
    parser.add_argument("--version", action="version", version=f"rag-redteam {__version__}")

    run = parser.add_subparsers(dest="command").add_parser("run", help="Run scenario(s) against a proxy.")
    run.add_argument("--base-url", default="http://localhost:8090", help="Proxy base URL.")
    run.add_argument("--admin-token", default=None, help="Admin bearer token (ingest + audit export).")
    run.add_argument(
        "--scenario",
        action="append",
        default=[],
        help="Scenario YAML path or id (repeatable). Default: all bundled scenarios.",
    )
    run.add_argument("--all", action="store_true", help="Run every scenario in tools/redteam/scenarios/.")
    run.add_argument(
        "--out",
        default="tools/redteam/artifacts/engagement",
        help="Output directory for results.json, audit.ndjson, report.md.",
    )
    run.add_argument("--engagement", default="engagement", help="Engagement label for the report.")
    run.add_argument("--tenant-id", default="default")
    return parser


def _resolve_scenario_paths(args: argparse.Namespace) -> List[Path]:
    bundled = default_scenarios_dir()
    if args.all or not args.scenario:
        return list_scenarios(bundled)
    paths: List[Path] = []
    for item in args.scenario:
        candidate = Path(item)
        if candidate.is_file():
            paths.append(candidate)
            continue
        by_id = bundled / f"{item}.yaml"
        if by_id.is_file():
            paths.append(by_id)
            continue
        raise FileNotFoundError(f"scenario not found: {item}")
    return paths


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command != "run":
        parser.print_help()
        return 2

    try:
        paths = _resolve_scenario_paths(args)
        scenarios = [load_scenario(path) for path in paths]
    except (ScenarioLoadError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    client = RedTeamClient(args.base_url, admin_token=args.admin_token)
    try:
        client.health()
    except RedTeamClientError as exc:
        print(f"ERROR: proxy unreachable at {args.base_url}: {exc}", file=sys.stderr)
        return 2

    if not client.admin_token:
        print(
            "ERROR: missing admin token (set --admin-token or RAG_PROTECTION_ADMIN_KEY)",
            file=sys.stderr,
        )
        return 2

    try:
        results = run_scenarios(client, scenarios, tenant_id=args.tenant_id)
        try:
            audit = client.export_audit(limit=2000, scrub=True)
        except RedTeamClientError:
            audit = ""
    except RedTeamClientError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    out_dir = Path(args.out)
    write_results(out_dir, results, audit)
    report_md = render_report(results, engagement=args.engagement, base_url=args.base_url)
    write_report(out_dir, report_md)

    failed = [r for r in results if not r.passed]
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(f"[{status}] {result.scenario_id}: {result.title}")
        for message in result.messages:
            print(f"       - {message}")
    print(f"\nArtifacts: {out_dir.resolve()}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
