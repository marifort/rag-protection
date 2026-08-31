"""acl-backfill command-line interface.

One-shot migration CLI: map source permissions → allowed_groups and patch
existing vector payloads without re-embedding.

Usage:
  tools/acl-backfill \\
    --backend memory --snapshot tools/acl_backfill/examples/store_snapshot.json \\
    --permissions tools/acl_backfill/examples/permissions.json \\
    --group-map tools/acl_backfill/examples/group_map.yaml

  tools/acl-backfill --backend qdrant --qdrant http://localhost:6333 \\
    --collection rag_chunks \\
    --permissions tools/acl_backfill/examples/qdrant_permissions.json \\
    --group-map tools/acl_backfill/examples/qdrant_group_map.yaml --apply

Exit codes:
  0  success (dry-run or apply)
  1  apply completed with per-document errors
  2  invalid input / configuration
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__
from ._bootstrap import ensure_imports
from .backfill import run_backfill
from .loaders import LoaderError, load_group_map, load_permissions, load_store_snapshot
from .report import coverage_artifact, render
from .writers import MemoryWriter, PgvectorWriter, QdrantWriter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="acl-backfill",
        description=(
            "Vector ACL backfill — patch allowed_groups on an existing collection "
            "without re-embedding (A4 migration / workshop tool)."
        ),
    )
    parser.add_argument("--version", action="version", version=f"acl-backfill {__version__}")

    parser.add_argument(
        "--backend",
        choices=["memory", "qdrant", "pgvector"],
        default="memory",
        help="Store backend. Default: memory (snapshot file).",
    )
    parser.add_argument(
        "--snapshot",
        help="Memory backend: JSON snapshot of document_id → {allowed_groups, metadata}.",
    )
    parser.add_argument("--qdrant", help="Qdrant URL (e.g. http://localhost:6333).")
    parser.add_argument("--collection", help="Qdrant collection name.")
    parser.add_argument("--qdrant-api-key", default=None, help="Optional Qdrant API key.")
    parser.add_argument(
        "--pg-url",
        help="pgvector connection URL (postgresql://… or :memory: / sqlite path).",
    )
    parser.add_argument(
        "--table-prefix",
        default="rag",
        help="pgvector table prefix (default: rag).",
    )

    parser.add_argument("--permissions", required=True, help="Permissions JSON/YAML/CSV.")
    parser.add_argument(
        "--group-map",
        required=True,
        help="Group map YAML/JSON: email|@domain → product group.",
    )
    parser.add_argument(
        "--perm-format",
        choices=["auto", "drive", "flat", "notion"],
        default="auto",
        help="Permissions shape. Default: auto-detect.",
    )
    parser.add_argument(
        "--unmapped",
        choices=["deny", "all_staff"],
        default="deny",
        help="Unmapped policy (default: deny, fail-closed).",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute + print diff only (default when --apply is omitted).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write payload patches. Without this flag the tool is always dry-run.",
    )

    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Report format. Default: text.",
    )
    parser.add_argument("--output", default=None, help="Write report to this file.")
    parser.add_argument(
        "--coverage-out",
        default=None,
        help="Write compact coverage JSON artifact (workshop appendix).",
    )
    parser.add_argument(
        "--write-snapshot",
        default=None,
        help="Memory backend: after --apply, write updated snapshot to this path.",
    )
    return parser


def _build_writer(args: argparse.Namespace):
    if args.backend == "memory":
        if not args.snapshot:
            raise LoaderError("--snapshot is required for --backend memory")
        return MemoryWriter.from_snapshot(load_store_snapshot(args.snapshot))
    if args.backend == "qdrant":
        if not args.qdrant or not args.collection:
            raise LoaderError("--qdrant and --collection are required for --backend qdrant")
        return QdrantWriter(args.qdrant, args.collection, api_key=args.qdrant_api_key)
    if args.backend == "pgvector":
        if not args.pg_url:
            raise LoaderError("--pg-url is required for --backend pgvector")
        return PgvectorWriter(args.pg_url, table_prefix=args.table_prefix)
    raise LoaderError(f"unknown backend: {args.backend}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        ensure_imports()
        permissions, resolved_fmt = load_permissions(
            args.permissions, perm_format=args.perm_format
        )
        group_map = load_group_map(args.group_map)
        writer = _build_writer(args)
    except LoaderError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    dry_run = not args.apply
    try:
        result = run_backfill(
            writer,
            permissions,
            group_map,
            perm_format=resolved_fmt,
            unmapped_policy=args.unmapped,
            dry_run=dry_run,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: backfill failed: {exc}", file=sys.stderr)
        return 2

    if (
        args.apply
        and args.backend == "memory"
        and args.write_snapshot
        and isinstance(writer, MemoryWriter)
    ):
        writer.write_snapshot(args.write_snapshot)

    report = render(result, fmt=args.format)
    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
    else:
        sys.stdout.write(report)

    if args.coverage_out:
        Path(args.coverage_out).write_text(
            json.dumps(coverage_artifact(result), indent=2) + "\n",
            encoding="utf-8",
        )

    if result.applied and result.errors:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
