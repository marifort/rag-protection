# #1 — Document-level ACL + 4-guardrail pipeline

> **Which doc?** **Card** (this page) = behavior / policy · **Demo** = show it · **Security** = pipeline depth · **Learn** = teach it
>
> [Demo](../demos/01-acl-pipeline.md) · [Security](../security/README.md) · [Learn](../learn/01-core-moats.md#1-document-level-acl--4-guardrail-pipeline) · [Tutorial](../tutorials/01-getting-started-and-guardrails.md)

| Field | Value |
|-------|-------|
| **Edition** | CE |
| **Status** | Shipped |
| **Code** | `acl.py`, `pipeline.py`, `store.py`, `guardrails/*`, `scanners/*` |
| **Pipeline docs** | [ce/security/](../security/README.md) |

**Tutorial:** [T01](../tutorials/01-getting-started-and-guardrails.md) · **Architecture:** [shared/architecture.md](../../shared/architecture.md)

---

## What & why

The core CE product: enforce **who can retrieve which documents**, sanitize query/chunks, block injection, and verify answers against sources — one ordered gateway path before the LLM.

Without this, semantic search surfaces payroll to engineers and poisoned corpus text hijacks the model.

---

## How it works

```text
identity → user-query scan (P1) → ACL retrieval → chunk scan
  → context isolation → LLM → citation → output scan
```

| Guardrail | Doc |
|-----------|-----|
| 1 — Document ACL | [GUARDRAIL_1_ACL.md](../security/GUARDRAIL_1_ACL.md) |
| 2 — DLP | [GUARDRAIL_2_DLP.md](../security/GUARDRAIL_2_DLP.md) |
| 3 — Injection | [GUARDRAIL_3_INJECTION.md](../security/GUARDRAIL_3_INJECTION.md) |
| 4 — Citation | [GUARDRAIL_4_CITATION.md](../security/GUARDRAIL_4_CITATION.md) |
| Detection map | [DETECTION_OVERVIEW.md](../security/DETECTION_OVERVIEW.md) |
| P1 / P2 | [ce/security/README.md](../security/README.md) |

Qdrant applies ACL **in-query**; SQLite filters in application code before scoring. CE DLP = regex + custom patterns + heuristic NER.

---

## Validate (smoke)

```bash
bash tools/docker_start.sh --smoke
# Employee vs HR payroll demo — see T01
```

---

## Gaps & non-claims

- Not ReBAC (#16 Planned). Pattern C BYO retrieval leaves ACL customer-owned.
- No zero-leakage guarantee — metadata and group mappings must be correct.

## Related moats

[#2](02-extraction-monitor.md) · [#3](03-canary-docs.md) · [#8](08-citation-hard-gate.md) · [#15](15-ingest-quarantine.md)
