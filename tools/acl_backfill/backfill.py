"""Core ACL backfill planning and apply logic.

Reuses ``rag_protection_enterprise.connectors.acl_mapping`` so mapped groups and
``acl_mapping_status`` metadata match runtime connectors / Lab 4 drift.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Literal, Optional

from .loaders import PermFormat, PermissionsMap
from .writers import BackfillWriter, DocumentAclState

Action = Literal[
    "change",
    "unchanged",
    "unmapped_deny",
    "unmapped_all_staff",
    "missing_in_store",
    "missing_in_permissions",
]


@dataclass(frozen=True)
class DocDiff:
    document_id: str
    action: Action
    before_groups: List[str]
    after_groups: List[str]
    mapping_status: str
    mapping_detail: Optional[str] = None
    point_count: int = 0
    in_store: bool = True
    in_permissions: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BackfillPlan:
    diffs: List[DocDiff] = field(default_factory=list)
    unmapped_policy: str = "deny"
    perm_format: str = "drive"
    store_document_count: int = 0
    permissions_document_count: int = 0

    @property
    def changes(self) -> List[DocDiff]:
        return [d for d in self.diffs if d.action in {"change", "unmapped_deny", "unmapped_all_staff"} and d.in_store]

    @property
    def unmapped(self) -> List[DocDiff]:
        return [d for d in self.diffs if d.mapping_status == "unmapped" and d.in_permissions]

    @property
    def orphans_permissions(self) -> List[DocDiff]:
        return [d for d in self.diffs if d.action == "missing_in_store"]

    @property
    def orphans_store(self) -> List[DocDiff]:
        return [d for d in self.diffs if d.action == "missing_in_permissions"]

    def coverage_pct(self) -> float:
        """Share of store docs that will have non-empty allowed_groups after apply."""
        if self.store_document_count == 0:
            return 0.0
        covered = 0
        for d in self.diffs:
            if not d.in_store:
                continue
            groups = d.after_groups if d.in_permissions else d.before_groups
            if groups:
                covered += 1
        return round(100.0 * covered / self.store_document_count, 2)

    def summary(self) -> Dict[str, Any]:
        change_n = len([d for d in self.diffs if d.action == "change" and d.in_store])
        unchanged_n = len([d for d in self.diffs if d.action == "unchanged"])
        deny_n = len([d for d in self.diffs if d.action == "unmapped_deny" and d.in_store])
        staff_n = len([d for d in self.diffs if d.action == "unmapped_all_staff" and d.in_store])
        return {
            "store_documents": self.store_document_count,
            "permissions_documents": self.permissions_document_count,
            "changed": change_n,
            "unchanged": unchanged_n,
            "unmapped_deny": deny_n,
            "unmapped_all_staff": staff_n,
            "missing_in_store": len(self.orphans_permissions),
            "missing_in_permissions": len(self.orphans_store),
            "coverage_pct_after": self.coverage_pct(),
            "unmapped_policy": self.unmapped_policy,
            "perm_format": self.perm_format,
        }


@dataclass
class BackfillResult:
    plan: BackfillPlan
    applied: bool
    written: int = 0
    skipped: int = 0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "applied": self.applied,
            "written": self.written,
            "skipped": self.skipped,
            "errors": list(self.errors),
            "summary": self.plan.summary(),
            "diffs": [d.to_dict() for d in self.plan.diffs],
        }


def map_document_permissions(
    entry: Any,
    group_map: Dict[str, str],
    *,
    perm_format: PermFormat,
    unmapped_policy: str,
):
    from rag_protection_enterprise.connectors.acl_mapping import (
        apply_unmapped_policy,
        map_drive_permissions,
        map_notion_permissions,
    )

    if perm_format == "flat":
        groups = {str(g) for g in (entry or []) if str(g).strip()}
        return apply_unmapped_policy(
            groups,
            unmapped_policy=unmapped_policy,
            source_permission_count=len(entry or []),
            mapped_permission_count=len(groups),
        )
    if perm_format == "notion":
        return map_notion_permissions(list(entry or []), unmapped_policy=unmapped_policy)
    return map_drive_permissions(
        list(entry or []),
        group_map,
        unmapped_policy=unmapped_policy,
    )


def enrich_backfill_metadata(
    existing_metadata: Dict[str, Any],
    *,
    result: Any,
    source_permissions: Any,
    perm_format: str,
) -> Dict[str, Any]:
    from rag_protection_enterprise.connectors.acl_mapping import enrich_acl_metadata
    from rag_protection_enterprise.connectors.acl_sync import content_revision_fingerprint

    meta = dict(existing_metadata)
    meta["acl_backfill"] = True
    meta["acl_backfill_format"] = perm_format
    if perm_format in {"drive", "notion"} and source_permissions is not None:
        meta["source_permissions"] = source_permissions
        meta["source_revision"] = content_revision_fingerprint(
            {"source_permissions": source_permissions}
        )
    return enrich_acl_metadata(meta, result)


def build_plan(
    store_docs: Dict[str, DocumentAclState],
    permissions: PermissionsMap,
    group_map: Dict[str, str],
    *,
    perm_format: PermFormat,
    unmapped_policy: str = "deny",
) -> BackfillPlan:
    from rag_protection_enterprise.connectors.acl_mapping import normalize_unmapped_policy

    policy = normalize_unmapped_policy(unmapped_policy)
    diffs: List[DocDiff] = []
    all_ids = sorted(set(store_docs) | set(permissions))

    for doc_id in all_ids:
        in_store = doc_id in store_docs
        in_perms = doc_id in permissions
        before = list(store_docs[doc_id].allowed_groups) if in_store else []
        points = store_docs[doc_id].point_count if in_store else 0

        if in_perms and not in_store:
            mapped = map_document_permissions(
                permissions[doc_id],
                group_map,
                perm_format=perm_format,
                unmapped_policy=policy,
            )
            diffs.append(
                DocDiff(
                    document_id=doc_id,
                    action="missing_in_store",
                    before_groups=[],
                    after_groups=list(mapped.allowed_groups),
                    mapping_status=mapped.status,
                    mapping_detail=mapped.detail,
                    point_count=0,
                    in_store=False,
                    in_permissions=True,
                )
            )
            continue

        if in_store and not in_perms:
            diffs.append(
                DocDiff(
                    document_id=doc_id,
                    action="missing_in_permissions",
                    before_groups=before,
                    after_groups=before,
                    mapping_status="unknown",
                    mapping_detail="No permissions row for this document_id",
                    point_count=points,
                    in_store=True,
                    in_permissions=False,
                )
            )
            continue

        mapped = map_document_permissions(
            permissions[doc_id],
            group_map,
            perm_format=perm_format,
            unmapped_policy=policy,
        )
        after = list(mapped.allowed_groups)
        if mapped.status == "unmapped":
            action: Action = (
                "unmapped_all_staff" if policy == "all_staff" else "unmapped_deny"
            )
        elif sorted(before) == sorted(after):
            action = "unchanged"
        else:
            action = "change"

        diffs.append(
            DocDiff(
                document_id=doc_id,
                action=action,
                before_groups=before,
                after_groups=after,
                mapping_status=mapped.status,
                mapping_detail=mapped.detail,
                point_count=points,
                in_store=True,
                in_permissions=True,
            )
        )

    return BackfillPlan(
        diffs=diffs,
        unmapped_policy=policy,
        perm_format=perm_format,
        store_document_count=len(store_docs),
        permissions_document_count=len(permissions),
    )


def apply_plan(
    writer: BackfillWriter,
    plan: BackfillPlan,
    permissions: PermissionsMap,
    group_map: Dict[str, str],
    *,
    dry_run: bool = True,
) -> BackfillResult:
    if dry_run:
        return BackfillResult(plan=plan, applied=False, written=0, skipped=len(plan.changes))

    store_docs = writer.list_documents()
    written = 0
    skipped = 0
    errors: List[str] = []

    for diff in plan.diffs:
        if not diff.in_store or not diff.in_permissions:
            skipped += 1
            continue
        if diff.action == "unchanged":
            # Still enrich metadata on re-run for drift readiness when status missing.
            existing = store_docs.get(diff.document_id)
            meta = dict(existing.metadata) if existing else {}
            if meta.get("acl_mapping_status") == diff.mapping_status and sorted(
                existing.allowed_groups if existing else []
            ) == sorted(diff.after_groups):
                skipped += 1
                continue

        mapped = map_document_permissions(
            permissions[diff.document_id],
            group_map,
            perm_format=plan.perm_format,  # type: ignore[arg-type]
            unmapped_policy=plan.unmapped_policy,
        )
        existing = store_docs.get(diff.document_id)
        existing_meta = dict(existing.metadata) if existing else {}
        new_meta = enrich_backfill_metadata(
            existing_meta,
            result=mapped,
            source_permissions=permissions[diff.document_id]
            if plan.perm_format in {"drive", "notion"}
            else None,
            perm_format=plan.perm_format,
        )
        try:
            ok = writer.update_acl(diff.document_id, list(mapped.allowed_groups), new_meta)
        except Exception as exc:  # noqa: BLE001 — surface per-doc errors in report
            errors.append(f"{diff.document_id}: {exc}")
            continue
        if ok:
            written += 1
        else:
            errors.append(f"{diff.document_id}: update returned false (missing?)")

    return BackfillResult(
        plan=plan,
        applied=True,
        written=written,
        skipped=skipped,
        errors=errors,
    )


def run_backfill(
    writer: BackfillWriter,
    permissions: PermissionsMap,
    group_map: Dict[str, str],
    *,
    perm_format: PermFormat,
    unmapped_policy: str = "deny",
    dry_run: bool = True,
) -> BackfillResult:
    store_docs = writer.list_documents()
    plan = build_plan(
        store_docs,
        permissions,
        group_map,
        perm_format=perm_format,
        unmapped_policy=unmapped_policy,
    )
    return apply_plan(
        writer,
        plan,
        permissions,
        group_map,
        dry_run=dry_run,
    )
