# acl-backfill — Vector ACL backfill / migration utility (A4)

A **one-shot consulting / migration CLI** that maps source permissions →
`allowed_groups` and patches existing vector payloads **without re-embedding**.

It reuses the shipped EE mapper
[`connectors/acl_mapping.py`](../../docs/ce/README.md)
— the same `map_drive_permissions` / `apply_unmapped_policy` /
`enrich_acl_metadata` semantics the runtime connectors and Lab 4 drift monitor
use — so a backfilled corpus is drift-ready for ACL sync (#12).

> Spec: [labs/a4-acl-backfill/SPEC.md](../../ENTERPRISE.md)
> · Opportunity: [ADDITIONAL_OPPORTUNITIES_SPECS § A4](../../ENTERPRISE.md#a4--vector-acl-backfill--migration-utility)
> · Roadmap: [04 §#29](../../ENTERPRISE.md#29--vector-acl-backfill--migration-utility-a4)
> · Tutorial: [T09 §N](../../docs/ce/README.md#part-n-vector-acl-backfill-a4-29) · [T06 Part 20](../../docs/ce/README.md#part-20---a4-vector-acl-backfill-migration-utility-tool-acl-backfill)
> · Workshop SKU: [SOLOPRENEUR §2](../../ENTERPRISE.md#2-idp--vector-acl-mapping-workshop) · **[ACL workshop SOW](../../ENTERPRISE.md)**

**Service SKU** — not a CE/EE product entitlement. Ships beside the product for
ACL mapping workshops when the prospect already has a live indexed collection.

---

## Quick start

From the repo root (no live vector DB required — uses the shipped memory snapshot):

```bash
tools/acl-backfill \
  --backend memory \
  --snapshot tools/acl_backfill/examples/store_snapshot.json \
  --permissions tools/acl_backfill/examples/permissions.json \
  --group-map tools/acl_backfill/examples/group_map.yaml
```

Expected: **DRY-RUN** report — 3 docs change (`hr-payroll-2024`, `eng-handbook`,
`public-faq`), 1 orphan in permissions (`unmapped-secret` → fail-closed `[]`),
1 store doc missing from the export (`legacy-notes`).

Apply on the memory snapshot (writes a new file; original untouched):

```bash
tools/acl-backfill \
  --backend memory \
  --snapshot tools/acl_backfill/examples/store_snapshot.json \
  --permissions tools/acl_backfill/examples/permissions.json \
  --group-map tools/acl_backfill/examples/group_map.yaml \
  --apply --write-snapshot /tmp/after-backfill.json
```

---

## Contents

- [Why A4 exists](#why-a4-exists)
- [How it works](#how-it-works)
- [Architecture](#architecture)
- [CLI](#cli)
- [Inputs](#inputs)
- [Backends](#backends)
- [Workshop runbook](#workshop-runbook-staging--cutover--rollback)
- [Testing](#testing)
- [Project layout](#project-layout)
- [Boundaries](#boundaries)
- [Lab artifacts](#lab-artifacts)

---

## Why A4 exists

**The pain:** *"We already embedded two million chunks without access labels."*
Full re-index takes months and kills the ACL workshop / license path.

**The fix:** import a permission map, dry-run the diff, patch payloads only
(`set_payload` / SQL UPDATE), validate coverage, cut over in days/weeks.

| Without this | With this |
|--------------|-----------|
| Re-index objection blocks the deal | Migration SKU unlocks workshop + license |
| DIY script; no fail-closed default | Same `acl_mapping` as runtime + scanner |
| Backfill invents ad-hoc metadata | Lab 4 / #12 drift-ready fields |

---

## How it works

```text
acl-backfill --permissions perms.json --group-map map.yaml [--apply]
  │
  ▼
┌──────────────────────────────────────────────────────────────┐
│ tools/acl_backfill/                                           │
│  loaders.py     JSON / YAML / CSV permissions + group-map    │
│  backfill.py    map via acl_mapping + enrich_acl_metadata    │
│  writers.py     Qdrant set_payload · pgvector UPDATE · memory│
│  report.py      text / JSON + coverage artifact              │
└──────────────────────────────────────────────────────────────┘
  --apply omitted → dry-run diff only (default, safe)
```

**Design contract:** zero alternate mapping logic. Every `allowed_groups` value
comes from `map_drive_permissions` / `map_notion_permissions` /
`apply_unmapped_policy`. Metadata enrichment matches connector ingest so Lab 4
drift and ACL sync (#12) keep working.

---

## Architecture

| Module | Role |
|--------|------|
| `cli.py` | argparse, backends, exit codes |
| `_bootstrap.py` | EE + proxy on `sys.path` |
| `loaders.py` | permissions + group-map + memory snapshot |
| `backfill.py` | plan (diff) + apply |
| `writers.py` | `MemoryWriter`, `QdrantWriter`, `PgvectorWriter` |
| `report.py` | text / JSON / coverage JSON |

Default **`--unmapped deny`** (fail-closed). Opt-in `all_staff` is fail-open —
`rag-scan` **POL002** flags that choice when connectors are enabled.

---

## CLI

```text
tools/acl-backfill \
  --backend memory|qdrant|pgvector \
  --permissions PATH --group-map PATH \
  [--unmapped deny|all_staff] [--perm-format auto|drive|flat|notion] \
  [--dry-run | --apply] [--format text|json] \
  [--coverage-out coverage.json]
```

| Flag | Meaning |
|------|---------|
| `--backend memory` | Fixture / workshop rehearsal (`--snapshot`) |
| `--backend qdrant` | Live collection (`--qdrant` + `--collection`) |
| `--backend pgvector` | Postgres or SQLite URL (`--pg-url`) |
| `--apply` | Write patches (default is dry-run) |
| `--coverage-out` | Compact JSON for SOW appendix |
| `--write-snapshot` | Memory only: dump post-apply state |

**Exit codes:** `0` ok · `1` apply with per-doc errors · `2` bad input / config

### Qdrant

```bash
tools/acl-backfill \
  --backend qdrant --qdrant http://localhost:6333 --collection rag_chunks \
  --permissions tools/acl_backfill/examples/qdrant_permissions.json \
  --group-map tools/acl_backfill/examples/qdrant_group_map.yaml          # dry-run
tools/acl-backfill \
  --backend qdrant --qdrant http://localhost:6333 --collection rag_chunks \
  --permissions tools/acl_backfill/examples/qdrant_permissions.json \
  --group-map tools/acl_backfill/examples/qdrant_group_map.yaml --apply  # set_payload
```

### pgvector

```bash
tools/acl-backfill \
  --backend pgvector --pg-url "postgresql://user:pass@host/db" \
  --table-prefix rag \
  --permissions perms.json --group-map map.yaml --apply
```

Uses `PgVectorDocumentStore.update_document_acl` (docs **and** chunks).

---

## Inputs

### `--permissions`

| Format | Shape |
|--------|-------|
| **drive** (JSON/YAML) | `{document_id: [ {emailAddress\|domain\|type, role}, … ]}` |
| **notion** | `{document_id: [ {group, public}, … ]}` |
| **flat** | `{document_id: ["hr", "executives"]}` or CSV `document_id,groups` |

Auto-detected unless `--perm-format` is set. Shipped examples:

| File | Role |
|------|------|
| `examples/permissions.json` | Drive-style matrix (memory workshop IDs) |
| `examples/permissions_flat.csv` | Flat groups CSV |
| `examples/group_map.yaml` | email / `@domain` → product group |
| `examples/store_snapshot.json` | Memory-backend corpus |
| `examples/qdrant_permissions.json` | Drive export keyed to sample corpus IDs |
| `examples/qdrant_group_map.yaml` | Demo identities → groups (no domain-wide `all-staff`) |
| `examples/qdrant_store_snapshot.json` | Unlabeled sample-corpus stand-in |

### `--group-map`

```yaml
"alice@corp.com": hr
"@corp.com": all-staff
```

Exact email and `@domain` suffix matching — identical to connector mapping.
A user email under a mapped domain receives **both** the user group and the
domain group (runtime parity).

---

## Backends

| Backend | Write mechanism | Re-embed? |
|---------|-----------------|-----------|
| Qdrant | `set_payload` on points matched by `document_id` | No |
| pgvector | `UPDATE` docs + chunks `allowed_groups` / `metadata` | No |
| memory | In-process dict (+ optional snapshot dump) | No |

Idempotent: re-run with the same map is safe; unchanged docs skip writes when
metadata is already enriched.

**Pinecone:** deferred (same semantics later via `update`).

---

## Workshop runbook (staging → cutover → rollback)

1. **Export** ACL matrix from Drive / SharePoint / IAM (`document_id` → permissions).
2. **Build** `--group-map` with the customer (workshop whiteboard → YAML).
3. **Staging dry-run:**
   ```bash
   tools/acl-backfill --backend qdrant --qdrant "$STAGING_URL" --collection "$C" \
     --permissions perms.json --group-map map.yaml --coverage-out coverage.json
   ```
4. **Review diff:** changed / unmapped / orphans. Confirm fail-closed on secrets.
5. **Apply on staging:** add `--apply`. Re-run — expect mostly `unchanged`.
6. **Validate:**
   - Coverage artifact ≥ agreed target
   - `tools/rag-scan check --qdrant …` (VEC001 / POL002)
   - Pilot queries: eng token must **not** see HR; HR token still does
7. **Rollback:** restore payload snapshot taken before apply, **or** re-apply the
   previous permissions export / group-map (tool is idempotent). Prefer snapshot
   restore if the prior map is unknown.
8. **Production cutover:** same apply + pilot matrix; keep the coverage JSON in
   the workshop SOW appendix.

---

## Testing

### Automated

```bash
.venv/bin/python -m pytest -q tools/acl_backfill/tests
# or via labs gate:
bash tools/validate_labs.sh   # includes A4 acl-backfill suite
```

| Test | Asserts |
|------|---------|
| `test_dry_run_diff_fail_closed` | Drive map + orphan + fail-closed unmapped |
| `test_apply_idempotent_and_enriches_metadata` | Write + `acl_mapping_status` / hash fields; re-run no-op |
| `test_unmapped_all_staff_opt_in` | Fail-open only when requested |
| `test_pgvector_update_document_acl` | Docs + chunks patched without re-embed |
| `test_cli_dry_run_examples` / `test_cli_apply_memory_snapshot` | CLI wiring |

### Manual (demo path)

Follow [DEMO_SCRIPT.md](../../ENTERPRISE.md)
(~3 minutes, memory backend, no infra).

### Use cases

| Use case | Command shape |
|----------|---------------|
| Workshop rehearsal | `--backend memory --snapshot …` |
| Staging cutover | `--backend qdrant …` dry-run → `--apply` |
| Postgres-only corp | `--backend pgvector --pg-url …` |
| Flat IAM export | `--permissions groups.csv --perm-format flat` |
| Coverage for SOW | `--coverage-out coverage.json` |

---

## Project layout

```text
tools/acl_backfill/
├── cli.py / backfill.py / loaders.py / writers.py / report.py
├── _bootstrap.py / __main__.py / pyproject.toml
├── examples/          # permissions, group-map, snapshot, flat CSV
└── tests/             # 10 automated tests
tools/acl-backfill     # bash wrapper
```

---

## Boundaries

- **Metadata only** — does not re-embed, re-chunk, or re-architect the pipeline
- **One-shot** — not a sync (that's connectors + Lab 4 / #12)
- **Not a connector** — does not call Drive/Notion APIs (#28)
- **Not an EE entitlement** — consulting tool; workshop SOW deliverable

Full boundary: [BOUNDARY.md](../../ENTERPRISE.md)

---

## Lab artifacts

| Doc | Path |
|-----|------|
| SPEC | [docs/commercial/labs/a4-acl-backfill/SPEC.md](../../ENTERPRISE.md) |
| Demo script | [DEMO_SCRIPT.md](../../ENTERPRISE.md) |
| Talk track | [TALK_TRACK.md](../../ENTERPRISE.md) |
| Control map | [CONTROL_MAP.md](../../ENTERPRISE.md) |
| Boundary | [BOUNDARY.md](../../ENTERPRISE.md) |
| Lab README | [README.md](../../ENTERPRISE.md) |

**Sample dry-run output** (shipped examples):

```text
ACL backfill — DRY-RUN
  unmapped policy : deny
  permissions fmt : drive
  store docs      : 4
  permissions docs: 4
  coverage after  : 100.0%

Summary
  changed              : 3
  unchanged            : 0
  unmapped (deny)      : 0
  missing in store     : 1
  missing in perms     : 1

Diff (store documents)
  [change] eng-handbook: [∅] → [all-staff] (mapped)
  [change] hr-payroll-2024: [∅] → [all-staff,hr] (mapped)
  [missing_in_permissions] legacy-notes: [all-staff] → [all-staff] (unknown)
  [change] public-faq: [∅] → [public] (mapped)
```
