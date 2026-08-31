"""Text / JSON reports for ACL backfill runs."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from .backfill import BackfillResult, DocDiff


def render(result: BackfillResult, fmt: str = "text") -> str:
    if fmt == "json":
        return json.dumps(result.to_dict(), indent=2) + "\n"
    return _render_text(result)


def _render_text(result: BackfillResult) -> str:
    plan = result.plan
    summary = plan.summary()
    mode = "APPLY" if result.applied else "DRY-RUN"
    lines: List[str] = [
        f"ACL backfill — {mode}",
        f"  unmapped policy : {summary['unmapped_policy']}",
        f"  permissions fmt : {summary['perm_format']}",
        f"  store docs      : {summary['store_documents']}",
        f"  permissions docs: {summary['permissions_documents']}",
        f"  coverage after  : {summary['coverage_pct_after']}%",
        "",
        "Summary",
        f"  changed              : {summary['changed']}",
        f"  unchanged            : {summary['unchanged']}",
        f"  unmapped (deny)      : {summary['unmapped_deny']}",
        f"  unmapped (all_staff) : {summary['unmapped_all_staff']}",
        f"  missing in store     : {summary['missing_in_store']}",
        f"  missing in perms     : {summary['missing_in_permissions']}",
    ]
    if result.applied:
        lines.extend(
            [
                "",
                "Write result",
                f"  written : {result.written}",
                f"  skipped : {result.skipped}",
                f"  errors  : {len(result.errors)}",
            ]
        )
        for err in result.errors[:20]:
            lines.append(f"    - {err}")

    lines.append("")
    lines.append("Diff (store documents)")
    store_diffs = [d for d in plan.diffs if d.in_store]
    if not store_diffs:
        lines.append("  (none)")
    else:
        for diff in store_diffs:
            lines.append(_format_diff_line(diff))

    orphans = plan.orphans_permissions
    if orphans:
        lines.append("")
        lines.append("Orphans — in permissions, not in store")
        for diff in orphans:
            lines.append(
                f"  {diff.document_id}: would map → {diff.after_groups!r} ({diff.mapping_status})"
            )

    if summary["unmapped_policy"] == "all_staff":
        lines.append("")
        lines.append(
            "WARNING: --unmapped all_staff is fail-open. "
            "rag-scan POL002 flags this policy when connectors are enabled."
        )

    lines.append("")
    return "\n".join(lines)


def _format_diff_line(diff: DocDiff) -> str:
    before = ",".join(diff.before_groups) or "∅"
    after = ",".join(diff.after_groups) or "∅"
    detail = f" — {diff.mapping_detail}" if diff.mapping_detail else ""
    return (
        f"  [{diff.action}] {diff.document_id}: "
        f"[{before}] → [{after}] ({diff.mapping_status}){detail}"
    )


def coverage_artifact(result: BackfillResult) -> Dict[str, Any]:
    """Compact coverage report suitable for workshop SOW appendix."""
    summary = result.plan.summary()
    return {
        "coverage_pct_after": summary["coverage_pct_after"],
        "store_documents": summary["store_documents"],
        "changed": summary["changed"],
        "unmapped_deny": summary["unmapped_deny"],
        "unmapped_all_staff": summary["unmapped_all_staff"],
        "missing_in_store": summary["missing_in_store"],
        "missing_in_permissions": summary["missing_in_permissions"],
        "unmapped_policy": summary["unmapped_policy"],
        "applied": result.applied,
        "orphan_document_ids": [d.document_id for d in result.plan.orphans_store],
        "unmapped_document_ids": [d.document_id for d in result.plan.unmapped],
    }
