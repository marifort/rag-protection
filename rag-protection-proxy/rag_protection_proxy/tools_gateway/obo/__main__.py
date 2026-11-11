"""CLI: demo OBO invoke, or print an agent access matrix.

    python -m rag_protection_proxy.tools_gateway.obo demo
    python -m rag_protection_proxy.tools_gateway.obo matrix
    python -m rag_protection_proxy.tools_gateway.obo matrix --format json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rag_protection_proxy.tools_gateway.obo.matrix import (
    default_fixture_dir,
    format_text,
    scan_files,
)
from rag_protection_proxy.tools_gateway.obo.pipeline import invoke_identity_bound
from rag_protection_proxy.tools_gateway.obo.tokens import mint_app_only_token, mint_user_token


def _cmd_demo(_args: argparse.Namespace) -> int:
    alice = mint_user_token(
        oid="alice-oid",
        groups=["engineering", "all-staff"],
        username="alice.engineer@contoso.com",
    )
    frank = mint_user_token(
        oid="frank-oid",
        groups=["data-platform", "all-staff"],
        username="frank.dba@contoso.com",
    )
    bot = mint_app_only_token()

    print("1. Alice (engineer) + run_sql  → expect BLOCK (group)")
    print("  ", invoke_identity_bound(inbound_token=alice, tool="run_sql", arguments={"query": "SELECT 1"}).reason)

    print("2. Frank (data-platform) + run_sql → expect ALLOW, acted_as_oid=frank-oid")
    ok = invoke_identity_bound(
        inbound_token=frank,
        tool="run_sql",
        arguments={"query": "SELECT employee_id, department FROM payroll"},
    )
    print("  ", ok.decision, ok.reason)
    if ok.result:
        print("   acted_as_oid=", ok.result.get("acted_as_oid"), "rows=", ok.result.get("row_count"))

    print("3. App-only bot + run_sql → expect BLOCK (service account)")
    print("  ", invoke_identity_bound(inbound_token=bot, tool="run_sql", arguments={"query": "SELECT 1"}).reason)

    print("4. Frank over-asks Files.ReadWrite.All for SQL → downscope empty / block")
    print(
        "  ",
        invoke_identity_bound(
            inbound_token=frank,
            tool="run_sql",
            arguments={"query": "SELECT 1"},
            requested_scopes=["Files.ReadWrite.All"],
        ).reason,
    )
    return 0


def _cmd_matrix(args: argparse.Namespace) -> int:
    fixtures = default_fixture_dir()
    entra = Path(args.entra) if args.entra else fixtures / "entra_grants.json"
    tools = Path(args.tools) if args.tools else fixtures / "mcp_tools.json"
    findings = scan_files(entra, tools)
    if args.format == "json":
        json.dump([f.as_dict() for f in findings], sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(format_text(findings))
    return 1 if any(f.severity == "high" for f in findings) else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m rag_protection_proxy.tools_gateway.obo",
        description="OBO identity lab — demo invoke and access-matrix scan. Not wired into POST /v1/tools/invoke.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("demo", help="Four-beat identity demo (Alice / Frank / app-only / over-ask)")

    matrix = sub.add_parser("matrix", help="Scan Entra SP grants vs MCP tools/list fixture")
    matrix.add_argument("--entra", help="Path to entra_grants.json")
    matrix.add_argument("--tools", help="Path to mcp_tools.json")
    matrix.add_argument("--format", choices=("text", "json"), default="text")

    args = parser.parse_args(argv)
    if args.cmd == "demo":
        return _cmd_demo(args)
    if args.cmd == "matrix":
        return _cmd_matrix(args)
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
