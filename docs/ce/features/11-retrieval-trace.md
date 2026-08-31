# #11 — Retrieval explainability trace

> **Which doc?** **Card** (this page) = behavior / policy · **Demo** = show it · **Learn** = teach it
>
> [Demo](../demos/11-retrieval-trace.md) · [Learn](../learn/01-core-moats.md#11-retrieval-decision-explainability-trace) · [Tutorial](../tutorials/09-implemented-features-walkthrough.md#part-g-retrieval-explainability-trace-11-t07)

| Field | Value |
|-------|-------|
| **Edition** | CE (runtime + Query Lab + Audit drawer). EE adds Policy Viewer knobs. |
| **Status** | Shipped |
| **Legacy alias** | T0.7 / Moat #11 |
| **Code** | `rag_protection_proxy/retrieval_trace.py`, `store.py` / `vector_store.py` `search_with_trace` |
| **Tests** | `tests/test_retrieval_trace.py`, `tests/test_vector_store.py` |

**Demo:** [../demos/11-retrieval-trace.md](../demos/11-retrieval-trace.md) · **Tutorial:** [T09 §G](../tutorials/09-implemented-features-walkthrough.md#part-g-retrieval-explainability-trace-11-t07)

---

## What & why

Operators and security reviewers need to know **why** a document appeared (or did not) in retrieval — not just the final `chunks[]` list. The trace records per-candidate outcomes: ACL drop, quarantine, low score, or selected into top-k.

Answers: *"Why didn't payroll show up?"* → `excluded_acl`. *"Why did this doc rank?"* → `selected` with score detail.

This is a **forensics / diagnosis** control, not a new deny path. Turning it on does not change who can retrieve what; it records the retrieval decision.

---

## How it works

```text
explain_search() → store.search_with_trace()
  → unfiltered candidates + ACL / quarantine / top-k classification
  → audit kind=retrieval_trace when policy.retrieval.explainability_enabled
  → QueryResponse.retrieval_trace[] only when include_retrieval_trace=true
```

**Response vs audit (FR-15.2 / FR-15.3):**

| Knob | Effect |
|------|--------|
| Request `include_retrieval_trace: true` | Compute trace **and** put rows on the HTTP response (Query Lab table) |
| Policy `retrieval.explainability_enabled` | Compute trace and persist `kind=retrieval_trace` to Audit — **does not** force the response field |
| Both | Trace on the response **and** in Audit |
| Neither | Ordinary `search()` path (no explainability overhead) |

Query Lab only renders the table when the request toggle is on (stale response payloads are ignored if the toggle was off).

Both the lexical `DocumentStore` and Qdrant `VectorDocumentStore` implement `search_with_trace` (ACL / quarantine outcomes). Cap size with `retrieval.max_trace_candidates`.

### Outcomes

| Outcome | Meaning |
|---------|---------|
| `selected` | In final top-k returned from the store (ranked survivor) |
| `excluded_acl` | Failed document ACL for caller groups |
| `excluded_quarantine` | Document status quarantined |
| `excluded_low_score` | Below relevance threshold |
| `not_in_top_k` | Scored but outside top_k cutoff |

`selected` means the chunk survived retrieval filters. It is **not** a guarantee the LLM saw it: selected chunks still pass **input guardrails** (DLP, injection, risk). Blocked survivors appear in Retrieved Chunks with `blocked: true` and never become `<retrieved_untrusted_context>`. Pipeline: [TECH_STACK — Retrieval Explainability vs what reaches the LLM](../../product/TECH_STACK.md#retrieval-explainability-vs-what-reaches-the-llm).

### Policy

<a id="policy"></a>

```yaml
retrieval:
  explainability_enabled: true
  max_trace_candidates: 100
```

**`retrieval.explainability_enabled`** — persist a `retrieval_trace` audit event on every query that reaches retrieval. Default `false`. Does **not** add `retrieval_trace[]` to API responses. Use this for SOC / privacy investigations that need a durable record; leave it off if you only need on-demand Query Lab traces.

**`retrieval.max_trace_candidates`** — cap how many candidate rows the store retains for the response / in-memory trace (default `100`). Audit `detail.trace[]` is **further capped at 50** regardless of this knob, so Audit drawers never dump the full candidate pool.

**Request `include_retrieval_trace: true`** on `POST /v1/query` — required for `QueryResponse.retrieval_trace[]` and the Query Lab table. Works even when policy explainability is off.

**Env `RAG_RETRIEVAL_EXPLAINABILITY=1`** — maps to the policy explainability flag (same effect as `explainability_enabled: true`). Restart if you change env-only.

### When to turn which knob on

| Goal | What to enable |
|------|----------------|
| One-off “why this result?” in Query Lab | Request toggle `include_retrieval_trace` only |
| Every query leaves a forensic audit row | Policy `explainability_enabled` (or env) |
| Both live table and Audit history | Policy **and** the Query Lab toggle on that request |
| Production with no extra retrieval work | Both off — ordinary `search()` |

Always-on audit traces add retrieval-path work (`search_with_trace` instead of `search`) and store candidate metadata (document ids, scores, drop reasons) in Audit. That is usually acceptable for POCs and regulated tenants; it is not free. Size the candidate cap down if Audit volume is a concern.

### API

Response field: `retrieval_trace[]` with `{document_id, chunk_id, outcome, detail, score?}` — **empty unless** the request sets `include_retrieval_trace: true`.

Audit: `GET /admin/audit/events?kind=retrieval_trace` (when policy explainability is on).

---

## Validate (smoke)

```bash
curl -s -X POST http://localhost:8090/v1/query \
  -H "Authorization: Bearer employee-demo-token" \
  -H "Content-Type: application/json" \
  -d '{"query":"payroll confidential","include_retrieval_trace":true}' \
  | jq '.retrieval_trace[] | {document_id, outcome, detail}'

cd rag-protection-proxy && pytest tests/test_retrieval_trace.py -q
```

Full demo: [../demos/11-retrieval-trace.md](../demos/11-retrieval-trace.md).

---

## Console

### Query Lab (CE)

Enable **include_retrieval_trace** → run a query → **Retrieval Explainability** table (candidates → ACL / quarantine drops → ranked survivors). The table stays empty if the toggle is off, even if a leftover payload arrives.

### Audit Log (CE)

Filter Type **Document retrieval** (`kind=retrieval_trace`; requires `retrieval.explainability_enabled`). The table Detail is a short summary (for example `4 used of 42 considered · 14 access denied…`) with **click Detail** for the candidate / ACL / rank table — not raw JSON. Audit detail is capped at 50 rows.

### Policy Viewer/Admin → Edit → Advanced Features → Retrieval (EE)

EE Policy forms write the same YAML keys CE operators edit by hand:

1. Open **Policy Viewer/Admin** → **Edit** → **Advanced Features** → **Retrieval**.
2. Set `retrieval.explainability_enabled` (`true` to persist traces to Audit).
3. Optionally change `retrieval.max_trace_candidates` (store/response cap; audit still 50).
4. Click **Save Policy Knobs** (not Reload Policy — knobs persist via `PATCH /admin/policy-knobs`).

The env override footnote on that pane (`RAG_RETRIEVAL_EXPLAINABILITY=1`) maps to the same explainability flag. CE-only installs have no Policy forms (Tier 2 **404**); edit `retrieval:` in the active `policy.yaml` and `POST /admin/reload-policy`.

### Empty-table troubleshooting

| Symptom | Cause |
|---------|--------|
| Query Lab table empty | Toggle was off, or the query was **blocked before retrieval** (input guardrail) so no trace exists |
| Audit has no `retrieval_trace` | Policy `explainability_enabled` is false (Query Lab toggle does not write Audit) |
| Audit row has fewer candidates than Query Lab | Audit `detail.trace[]` is hard-capped at 50; raise is not a knob |
| Payroll missing from both chunks and trace | Query never reached retrieval, or the doc was not a candidate at all |

---

## Gaps & non-claims

- Trace reflects **gateway retrieval path** only — not customer BYO retrieval (Pattern C).
- Heuristic scores — explains ranking, not legal discovery of all corpus content.
- Does not explain LLM token attribution after generation.
- `selected` is not “the model saw this chunk” — input scan can still drop it.
- Trace size is capped; it is not a full vector-similarity dump.

---

## Engineering reference

| Artifact | Path |
|----------|------|
| Module | `retrieval_trace.py` |
| Lexical trace | `store.py` → `search_with_trace` |
| Vector (Qdrant) trace | `vector_store.py` → `search_with_trace` |
| Pipeline gating | `pipeline.py` → `_compute_retrieval_trace` / `_trace_for_response` |
| Audit cap | `record_retrieval_trace()` keeps `trace[:50]` |
| Policy knobs API | `retrieval_explainability_enabled`, `retrieval_max_trace_candidates` on `PATCH /admin/policy-knobs` |
| UI tests | `QueryLabPane.test.tsx`, `retrieval/trace.test.ts` |
