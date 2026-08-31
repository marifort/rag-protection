# #3 — Canary / honeypot documents

> **Which doc?** **Card** (this page) = behavior / policy · **Demo** = show it · **Learn** = teach it · **Lab** = GTM depth
>
> [Demo](../demos/03-canary-docs.md) · [Learn](../learn/01-core-moats.md#3-canary--honeypot-documents) · [Lab](../../../ENTERPRISE.md) · [Tutorial](../tutorials/09-implemented-features-walkthrough.md#part-b-canary-honeypot-documents-lab-10-3)

| Field | Value |
|-------|-------|
| **Edition** | CE |
| **Status** | Shipped |
| **Legacy alias** | Lab 10 |
| **Code** | `rag_protection_proxy/guardrails/canary.py` · hook in `pipeline.py` |
| **Tests** | `tests/test_canary.py` |

**Demo:** [../demos/03-canary-docs.md](../demos/03-canary-docs.md) · **Tutorial:** [T09 §B](../tutorials/09-implemented-features-walkthrough.md#part-b-canary-honeypot-documents-lab-10-3) · **Pairs with:** [#2 extraction](../features/02-extraction-monitor.md) · [#5 SIEM](../../../ENTERPRISE.md)

---

## What & why

ACL enforcement can regress silently after a connector sync bug, metadata filter mistake, or vector-backend edge case. Security teams want **continuous proof** that unauthorized documents never enter retrieval — not just a passing POC.

A **canary** is a decoy document with a restrictive ACL (`__canary__` group). If it ever appears in a retrieval candidate set for a non-auditor subject, that is an unambiguous P1 alarm: enforcement broke. The canary chunk is **scrubbed** from the response before context assembly.

---

## How it works

```text
POST /admin/canary/seed  →  store.ingest(metadata.canary=true, allowed_groups=["__canary__"])
POST /v1/query           →  store.search → inspect_candidates()
  → canary in results for non-auditor?  → scrub chunk + canary_triggered audit
  → optional output_backstop scans final answer for canary_token
```

### Policy (`canary:` block)

```yaml
canary:
  enabled: true
  auditor_subjects: ["security-canary-bot"]
  auditor_groups: ["canary-admin"]
  output_backstop: true
```

| Key | Purpose |
|-----|---------|
| `enabled` | Arms retrieval trap (default off). Reload policy or restart after edit. |
| `auditor_subjects` / `auditor_groups` | May retrieve canaries without tripping (verification bots) |
| `output_backstop` | Scan final LLM output for registered `canary_token` |

`POST /admin/canary/seed` works even when `enabled: false`; only the trap requires arming.

### API

| Endpoint | Purpose |
|----------|---------|
| `POST /admin/canary/seed` | Seed decoy (title, body, optional `allowed_groups` for honeypot demos) |
| `GET /admin/canary/list` | Active canaries |
| `POST /admin/canary/retire` | Remove canary |
| `GET /admin/audit/events?kind=canary_triggered` | P1 audit feed |

### Audit event

| Field | Value |
|-------|-------|
| `kind` | `canary_triggered` |
| `decision` | `block` |
| `risk_score` | `1.0` |
| `source` | `retrieval.canary` or `output.canary` |

Treat as **P1** — enforcement is broken.

---

## Operator notes: theft card, hybrid retrieval, and missing retire rows

These notes cover a recurring demo/lab confusion: **Suspected data theft** lights up even though nobody “called a canary,” and **Documents & Ingest** does not show the `document_id` from the audit event.

### You never call a canary

There is no canary query API. `inspect_candidates()` runs on **every** `POST /v1/query` after retrieval. If any retrieved chunk has `metadata.canary=true` and the subject is not a canary auditor, the proxy:

1. Writes `kind=canary_triggered` (`source: retrieval.canary`).
2. **Scrubs** the decoy from `chunks` / the answer.

The Query Lab response can look clean while Audit still records a hit. Filter Audit to `canary_triggered` and read `detail.document_id`.

Two seed modes:

| Seed | `allowed_groups` | When it fires |
|------|------------------|---------------|
| Production tripwire | default `__canary__` (no real user) | Only if ACL/retrieval is broken |
| Demo honeypot | a group the demo user holds (`engineering`, `hr`, …) | Any search that **retrieves** that doc, including unrelated hybrid neighbors |

Lab leftovers titled **Zephyr Phantom Ledger** are almost always reachable honeypots. They are supposed to trip for that group. They are **not** proof that someone typed the bait string.

### Why **Suspected data theft** appears

The Overview / Audit card is **not** a third detector. It joins, in the selected time range, the same `subject` + `tenant_id` with:

1. `extraction_suspected` (corpus walk — often **breadth**, not coverage), and
2. `canary_triggered`.

Both in the same UTC hour → **same hour** (aligned with SIEM `RAG-Exfil-HighConfidence`). Both in range but different hours → **range only**.

A hybrid retrieval session as `alice.engineer` (`employee-demo-token`) with `top_k=10` on a ~50-doc demo corpus commonly produces **both** halves without a dedicated canary demo: many distinct titles trip breadth, and a reachable or **orphan vector** canary lands in the fused top-k. Pair walkthrough: [exfil-correlation DEMO_SCRIPT](../../../ENTERPRISE.md).

### Why Documents & Ingest does not list that id

**Corpus Documents** is ACL-filtered to the **user** token (toolbar), not the admin key. `bob.hr` / `hr-demo-token` only sees `hr` / `all-staff` (and similar) groups. An `engineering` honeypot that Alice retrieved will not appear for Bob.

`Delete` on a live canary is blocked (**409**). Retire with `policy_admin`:

```bash
curl -s -X POST http://localhost:8090/admin/canary/retire \
  -H "Authorization: Bearer $RAG_PROTECTION_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"document_id":"<id-from-audit>"}'
```

`GET /admin/canary/list` (admin) is the full canary catalog. It still will not include an id that is **already gone from SQLite**.

### Hybrid orphan: SQLite retired, Qdrant still retrieves

Under `RAG_STORE_BACKEND=hybrid`, list/detail/retire follow **SQLite**. Retrieval fuses SQLite + Qdrant. A point can remain in collection `RAG_QDRANT_COLLECTION` (default `rag_chunks`) after the SQLite row is gone (volume kept across a DB reset, retire while Qdrant was down, or a failed vector delete). Then:

- Audit `canary_triggered` still cites that `document_id`.
- `GET /admin/canary/list` and document inspect return **404**.
- Lexical `retrieval_trace` never lists the id (trace is the SQLite leg). The fused `chunks` had it long enough for the trap, then it was scrubbed.
- The Documents table cannot show a row to retire.

Confirm the orphan (host port **6333**):

```bash
curl -s -X POST "http://localhost:6333/collections/${RAG_QDRANT_COLLECTION:-rag_chunks}/points/scroll" \
  -H "Content-Type: application/json" \
  -d '{"limit": 20, "with_payload": true, "with_vector": false,
       "filter": {"must": [{"key": "document_id", "match": {"value": "<id-from-audit>"}}]}}'
```

Payload typically includes `metadata.canary: true` and `allowed_groups` (e.g. `engineering`). `POST /admin/canary/retire` **404s** — delete the Qdrant points:

```bash
curl -s -X POST "http://localhost:6333/collections/${RAG_QDRANT_COLLECTION:-rag_chunks}/points/delete" \
  -H "Content-Type: application/json" \
  -d '{"filter": {"must": [{"key": "document_id", "match": {"value": "<id-from-audit>"}}]}}'
```

Qdrant catalog vs SQLite list: [QDRANT_CONFIGURATION_AND_TESTING.md](../../product/QDRANT_CONFIGURATION_AND_TESTING.md). Hybrid fusion vs lexical trace: [E3.6](../../../ENTERPRISE.md).

Production tripwires should stay on `__canary__`. After a lab, retire reachable honeypots via `/admin/canary/list` **and** scroll Qdrant for leftover `metadata.canary` points.

### Worked example (local hybrid demo, 2026-08-23)

| What operators saw | What was actually true |
|--------------------|------------------------|
| **Suspected data theft** for `alice.engineer`, 5 scrapes, 7 canary hits, **same hour** | Five `extraction_suspected` (breadth ≥ 0.5) plus seven `canary_triggered` on ordinary hybrid queries — not a canary API |
| “I never queried a canary” | Trap fired at **retrieval**; decoy scrubbed from the answer |
| Audit `document_id` `canary-4e4b9013` (**Zephyr Phantom Ledger**, `engineering`) | Reachable honeypot / orphan vector — not `__canary__` |
| Documents & Ingest as `bob.hr` showed other Zephyr / `canary-hr-*` rows, not that id | Table is ACL-filtered; that id was already absent from SQLite |
| Retire / inspect 404 | Point still in Qdrant `rag_chunks` until deleted by `document_id` filter |

---

## Validate (smoke)

```bash
bash tools/docker_start.sh
export RAG_PROTECTION_ADMIN_KEY=rag-admin-demo-key

# Enable canary in data/policy.yaml, then:
curl -s -X POST http://localhost:8090/admin/reload-policy \
  -H "Authorization: Bearer $RAG_PROTECTION_ADMIN_KEY" | jq .

cd rag-protection-proxy && pytest tests/test_canary.py -q
```

Full demo: [../demos/03-canary-docs.md](../demos/03-canary-docs.md).

---

## Gaps & non-claims

| In scope | Out of scope |
|----------|--------------|
| Detective tripwire proving Guardrail 1 works | ACL enforcement itself |
| Scrub + P1 alert on unauthorized retrieval | Coverage beyond seeded sensitivity classes |
| Per-tenant canary seeding | Prevention of underlying ACL bugs (detect + contain) |

- **Coverage = seeded classes** — seed one canary per sensitivity level / tenant for meaningful coverage.
- **Not a scanner** — complements ACL; does not replace it.

---

## Engineering reference

| Artifact | Path |
|----------|------|
| Registry + trap | `guardrails/canary.py` |
| Admin routes | `POST /admin/canary/seed`, `list`, `retire` |
| SIEM detection | `RAG-Canary-Triggered` (#5) |
| Full spec (archived) | [lab10 SPEC](../../../ENTERPRISE.md) |
| UI testing | [lab10 UI_TESTING](../../../ENTERPRISE.md) |
| Theft-card pairing | [exfil-correlation](../../../ENTERPRISE.md) |
| Hybrid list ≠ Qdrant | [QDRANT_CONFIGURATION_AND_TESTING.md](../../product/QDRANT_CONFIGURATION_AND_TESTING.md) |
