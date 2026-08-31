from __future__ import annotations

from pathlib import Path

import pytest

from acl_backfill._bootstrap import ensure_imports
from acl_backfill.backfill import apply_plan, build_plan, run_backfill
from acl_backfill.loaders import LoaderError, load_group_map, load_permissions, load_store_snapshot
from acl_backfill.writers import MemoryWriter

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


@pytest.fixture(scope="module", autouse=True)
def _ee():
    ensure_imports()


def test_load_drive_permissions_and_group_map():
    perms, fmt = load_permissions(EXAMPLES / "permissions.json")
    assert fmt == "drive"
    assert "hr-payroll-2024" in perms
    group_map = load_group_map(EXAMPLES / "group_map.yaml")
    assert group_map["@corp.com"] == "all-staff"
    assert group_map["alice@corp.com"] == "hr"


def test_load_flat_csv():
    perms, fmt = load_permissions(EXAMPLES / "permissions_flat.csv")
    assert fmt == "flat"
    assert perms["hr-payroll-2024"] == ["hr", "executives"]


def test_dry_run_diff_fail_closed():
    snapshot = load_store_snapshot(EXAMPLES / "store_snapshot.json")
    writer = MemoryWriter.from_snapshot(snapshot)
    perms, fmt = load_permissions(EXAMPLES / "permissions.json")
    group_map = load_group_map(EXAMPLES / "group_map.yaml")

    result = run_backfill(
        writer,
        perms,
        group_map,
        perm_format=fmt,
        unmapped_policy="deny",
        dry_run=True,
    )
    assert not result.applied
    by_id = {d.document_id: d for d in result.plan.diffs}

    assert by_id["hr-payroll-2024"].action == "change"
    # alice@corp.com → hr; also matches @corp.com → all-staff (same as runtime map_drive_permissions)
    assert set(by_id["hr-payroll-2024"].after_groups) == {"hr", "all-staff"}
    assert by_id["eng-handbook"].after_groups == ["all-staff"]
    assert by_id["public-faq"].after_groups == ["public"]

    # contractor email has no group-map entry → fail-closed empty groups
    assert by_id["unmapped-secret"].action == "missing_in_store"
    assert by_id["unmapped-secret"].after_groups == []
    assert by_id["unmapped-secret"].mapping_status == "unmapped"

    # legacy-notes in store but not in permissions export
    assert by_id["legacy-notes"].action == "missing_in_permissions"

    summary = result.plan.summary()
    assert summary["changed"] >= 3
    assert summary["coverage_pct_after"] > 0


def test_apply_idempotent_and_enriches_metadata():
    snapshot = load_store_snapshot(EXAMPLES / "store_snapshot.json")
    writer = MemoryWriter.from_snapshot(snapshot)
    perms, fmt = load_permissions(EXAMPLES / "permissions.json")
    # Drop the orphan-only permission so apply focuses on in-store docs
    perms = {k: v for k, v in perms.items() if k in snapshot}
    group_map = load_group_map(EXAMPLES / "group_map.yaml")

    first = run_backfill(
        writer, perms, group_map, perm_format=fmt, unmapped_policy="deny", dry_run=False
    )
    assert first.applied
    assert first.written >= 3
    assert not first.errors

    hr = writer.list_documents()["hr-payroll-2024"]
    assert set(hr.allowed_groups) == {"hr", "all-staff"}
    assert hr.metadata.get("acl_mapping_status") == "mapped"
    assert hr.metadata.get("acl_backfill") is True
    assert "source_permissions" in hr.metadata
    assert hr.metadata.get("source_revision")

    second = run_backfill(
        writer, perms, group_map, perm_format=fmt, unmapped_policy="deny", dry_run=False
    )
    assert second.applied
    # Re-run should be mostly no-ops (unchanged + metadata already enriched)
    assert second.written == 0 or second.skipped >= second.written


def test_unmapped_all_staff_opt_in():
    writer = MemoryWriter.from_snapshot(
        {"secret": {"allowed_groups": [], "metadata": {}}}
    )
    perms = {
        "secret": [{"type": "user", "emailAddress": "nobody@elsewhere.com", "role": "reader"}]
    }
    group_map = {"@corp.com": "all-staff"}
    plan = build_plan(
        writer.list_documents(),
        perms,
        group_map,
        perm_format="drive",
        unmapped_policy="all_staff",
    )
    diff = plan.diffs[0]
    assert diff.action == "unmapped_all_staff"
    assert diff.after_groups == ["all-staff"]
    assert diff.mapping_status == "unmapped"


def test_pgvector_update_document_acl():
    ensure_imports()
    from rag_protection_enterprise.pgvector_store import PgVectorDocumentStore
    from rag_protection_proxy.embeddings import HashEmbedder

    store = PgVectorDocumentStore(
        connection_url=":memory:",
        table_prefix="a4test",
        embedder=HashEmbedder(),
    )
    store.ingest(
        document_id="doc-1",
        title="Doc",
        content="hello world " * 40,
        allowed_groups=[],
        metadata={},
        chunk_size=40,
    )
    ok = store.update_document_acl(
        "doc-1",
        ["hr"],
        {"acl_mapping_status": "mapped", "acl_backfill": True},
    )
    assert ok is True
    detail = store.get_document_detail("doc-1")
    assert detail is not None
    assert detail["allowed_groups"] == ["hr"]
    assert detail["metadata"]["acl_mapping_status"] == "mapped"

    # Chunks must match docs (retrieval ACL)
    rows = store._conn.execute(
        f"SELECT allowed_groups, metadata FROM {store._chunks_table()}"
    ).fetchall()
    assert rows
    import json

    for row in rows:
        assert json.loads(row["allowed_groups"]) == ["hr"]
        assert json.loads(row["metadata"])["acl_backfill"] is True


def test_cli_dry_run_examples(tmp_path):
    from acl_backfill.cli import main

    out = tmp_path / "report.txt"
    cov = tmp_path / "coverage.json"
    code = main(
        [
            "--backend",
            "memory",
            "--snapshot",
            str(EXAMPLES / "store_snapshot.json"),
            "--permissions",
            str(EXAMPLES / "permissions.json"),
            "--group-map",
            str(EXAMPLES / "group_map.yaml"),
            "--output",
            str(out),
            "--coverage-out",
            str(cov),
        ]
    )
    assert code == 0
    text = out.read_text(encoding="utf-8")
    assert "DRY-RUN" in text
    assert "hr-payroll-2024" in text
    assert cov.is_file()


def test_cli_apply_memory_snapshot(tmp_path):
    from acl_backfill.cli import main

    snap_out = tmp_path / "after.json"
    code = main(
        [
            "--backend",
            "memory",
            "--snapshot",
            str(EXAMPLES / "store_snapshot.json"),
            "--permissions",
            str(EXAMPLES / "permissions.json"),
            "--group-map",
            str(EXAMPLES / "group_map.yaml"),
            "--apply",
            "--write-snapshot",
            str(snap_out),
            "--format",
            "json",
        ]
    )
    assert code == 0
    assert snap_out.is_file()
    after = load_store_snapshot(snap_out)
    assert set(after["hr-payroll-2024"]["allowed_groups"]) == {"hr", "all-staff"}
    assert after["eng-handbook"]["allowed_groups"] == ["all-staff"]


def test_qdrant_examples_match_sample_corpus_acl():
    """Fixtures for live rag_chunks must keep payroll off all-staff (engineer blocked)."""
    snapshot = load_store_snapshot(EXAMPLES / "qdrant_store_snapshot.json")
    writer = MemoryWriter.from_snapshot(snapshot)
    perms, fmt = load_permissions(EXAMPLES / "qdrant_permissions.json")
    group_map = load_group_map(EXAMPLES / "qdrant_group_map.yaml")
    assert "@corp.com" not in group_map

    result = run_backfill(
        writer,
        perms,
        group_map,
        perm_format=fmt,
        unmapped_policy="deny",
        dry_run=True,
    )
    by_id = {d.document_id: d for d in result.plan.diffs}

    assert set(by_id["hr-payroll"].after_groups) == {"hr", "executives"}
    assert "all-staff" not in by_id["hr-payroll"].after_groups
    assert by_id["eng-runbook"].after_groups == ["engineering"]
    assert by_id["exec-strategy"].after_groups == ["executives"]
    assert set(by_id["public-faq"].after_groups) == {"public", "all-staff"}
    assert set(by_id["customer-feedback-poisoned"].after_groups) == {"public", "all-staff"}

    assert by_id["drive-unmapped-secret"].action == "missing_in_store"
    assert by_id["drive-unmapped-secret"].after_groups == []
    assert by_id["drive-unmapped-secret"].mapping_status == "unmapped"


def test_loader_rejects_empty_group_map(tmp_path):
    path = tmp_path / "empty.yaml"
    path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(LoaderError):
        load_group_map(path)


def test_apply_plan_skips_orphans():
    writer = MemoryWriter.from_snapshot(
        {"in-store": {"allowed_groups": [], "metadata": {}}}
    )
    perms = {
        "in-store": [{"type": "domain", "domain": "corp.com", "role": "reader"}],
        "only-perms": [{"type": "domain", "domain": "corp.com", "role": "reader"}],
    }
    group_map = {"@corp.com": "all-staff"}
    plan = build_plan(
        writer.list_documents(), perms, group_map, perm_format="drive", unmapped_policy="deny"
    )
    result = apply_plan(writer, plan, perms, group_map, dry_run=False)
    assert result.written == 1
    assert writer.list_documents()["in-store"].allowed_groups == ["all-staff"]
