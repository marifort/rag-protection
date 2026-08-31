# #2 — Corpus-extraction monitor

> **Which doc?** **Card** (this page) = behavior / policy · **Demo** = show it · **Learn** = teach it · **Lab** = GTM depth
>
> [Demo](../demos/02-extraction-monitor.md) · [Learn](../learn/01-core-moats.md#2-corpus-extraction-monitor) · [Lab](../../../ENTERPRISE.md) · [Tutorial](../tutorials/09-implemented-features-walkthrough.md#part-a-corpus-extraction-monitor-lab-9-2)

| Field | Value |
|-------|-------|
| **Edition** | CE |
| **Status** | Shipped |
| **Legacy alias** | Lab 9 |
| **Code** | `rag_protection_proxy/guardrails/extraction.py` · hook in `pipeline.py` |
| **Tests** | `tests/test_extraction.py` |

**Demo:** [../demos/02-extraction-monitor.md](../demos/02-extraction-monitor.md) · **Tutorial:** [T09 §A](../tutorials/09-implemented-features-walkthrough.md#part-a-corpus-extraction-monitor-lab-9-2) · **Pairs with:** [#3 canary](../features/03-canary-docs.md) · [#5 SIEM](../../../ENTERPRISE.md)

---

## What & why

Authorized users can reconstruct an entire knowledge base through many individually allowed queries. ACL, DLP, and per-query rate limits miss this because each request passes on its own.

The extraction monitor scores **cross-query retrieval behavior** per subject: corpus coverage, breadth ratio, and novelty over a sliding window. It emits `extraction_suspected` audit events and optional challenge/throttle actions.

**Plain-English context:** These ratios are security telemetry on the retrieval stream, not fields the vector store returns with search hits, and not the same as citation coverage on a single answer. Primer: [HOW_RAG_WORKS.md § Coverage, breadth_ratio, and novelty_ratio](../../product/HOW_RAG_WORKS.md#coverage-breadth_ratio-and-novelty_ratio).

**Discovery one-liner:** *An authorized user can still download your whole knowledge base one question at a time — we detect that on the retrieval stream, which no gateway or prompt firewall can see.*

---

## How it works

```text
POST /v1/query (per subject)
  → after ACL-filtered retrieval
  → record { distinct_documents, chunks, query_hash } in sliding window
  → score_extraction() → none | elevated | severe
  → audit kind=extraction_suspected (alert | challenge | throttle)
```

### Signals

In this feature, a **signal** is one measurable clue the monitor computes from a subject’s recent retrieval history — not from document text, titles, or “was this query malicious?” content inspection. After each allowed query, the monitor looks at the sliding window of what that person retrieved and derives three numbers. Each number asks a different question about whether the session looks like corpus walking. None of these alone is a verdict; they feed severity only after the window has enough queries (`window_queries ≥ min_window_queries`). “Signal” here means a behavioral metric on the retrieval stream, not a network alert, SIEM rule, or content classifier.

#### Corpus coverage

**Coverage** answers: how much of the whole tenant knowledge base has this person touched in the window? It is calculated as distinct documents retrieved divided by total tenant corpus size (`distinct_documents ÷ corpus_size`). If the corpus is smaller than `min_corpus_size`, coverage is treated as inactive so tiny demo stores do not look like scrapes by accident.

High coverage means the subject has reached a large share of all tenant documents — the end state of a successful scrape. The vulnerability it exposes is **authorized corpus reconstruction**: an allowed user rebuilding large parts of the knowledge base across many individually legitimate queries. ACL and DLP miss that pattern because each request can still be permitted on its own.

#### Breadth ratio

**Breadth** answers: how widely is the subject spreading across documents relative to how many times they asked? It is calculated as distinct documents divided by queries in the window (`distinct_documents ÷ window_queries`). Digging into one topic keeps breadth low. Walking many different shelves keeps it high. Values can exceed `1.0` when a single query returns several documents (common with high `top_k` on a large store).

High breadth looks like enumeration — “many different docs per ask” — rather than normal follow-up Q&A. The vulnerability it exposes is the same family of **authorized breadth abuse / aggregation over retrieval**: reconstructing payroll tables, runbooks, tickets, or wiki pages piece by piece without a bulk-download API. It is not a classic auth bypass or injection; it is behavioral data-exfiltration on the retrieval stream (OWASP-adjacent sensitive disclosure via aggregation). In this product, breadth at or above `breadth_ratio_threshold` (full window) raises **severe**.

#### Novelty ratio

**Novelty** answers: how often does a new query still unlock something the subject had not retrieved yet in this window? It is the share of window queries that touched at least one previously unseen `document_id`. Re-asking about the same documents does not count as novel. Stay on a few docs and novelty stays low; keep finding first-time material and novelty stays high.

High novelty is the “map the unknown” shape of the same extraction risk: sustained exploration that expands the set of touched documents one unlock at a time. Breadth asks whether asks are *wide*; novelty asks whether asks keep unlocking *new* territory. In this product, novelty at or above `novelty_ratio_threshold` (full window) raises **elevated** only — it never drives severe by itself.

### Sliding window

A **sliding window** is the monitor’s short-term memory for one subject: only retrievals from the last `window_seconds` count toward the score.

It is “sliding” because the cutoff moves forward with time. As the clock advances, old queries age out of the window and stop affecting coverage, breadth, and novelty — you do not need to reset anything by hand. Each new query is added; anything older than the TTL is dropped on the next prune. The result is always “what has this person retrieved *recently*,” not “everything they have ever retrieved.”

That memory lives **in-process per subject** (no separate datastore in MVP). Waiting out `window_seconds` or restarting the proxy clears the live window; it does **not** delete prior Audit Log rows.

### Policy (`extraction:` block)

#### Big picture

The extraction monitor watches **one user (subject) over time**, not a single query. After each ACL-filtered retrieval it remembers which documents that person touched, then asks: does this look like someone quietly walking the knowledge base one allowed question at a time?

ACL, DLP, and per-query rate limits each see only the current request. This guardrail is different: it scores **cross-query retrieval behavior** inside a sliding window — how much of the corpus was touched, how widely queries spread across documents, and whether each ask keeps unlocking new ones. When that pattern looks like a scrape, it emits `extraction_suspected` and optionally challenges or throttles.

The knobs below control how long it remembers, how much evidence it needs before caring, and how harshly it reacts to a **severe** score.

```yaml
extraction:
  enabled: true
  window_seconds: 3600
  min_window_queries: 20
  min_corpus_size: 50
  elevated_coverage: 0.25
  severe_coverage: 0.50
  breadth_ratio_threshold: 0.8
  novelty_ratio_threshold: 0.9
  action: alert          # alert | challenge | throttle
```

#### Parameters

**`enabled`** — Master on/off switch. When `false` (the code default), the monitor does nothing. When `true`, every ACL-filtered retrieval for a subject is recorded and scored. This is the only extraction setting with an env shortcut (`RAG_EXTRACTION_ENABLED`); everything else is YAML-only and needs a policy reload.

**`window_seconds`** — How far back the monitor looks for that subject. Think of it as a sliding “recent history” window: entries older than this many seconds drop out of the score. It does **not** erase Audit Log rows — only the live in-memory watch state. Restarting the proxy clears that state immediately. A longer window catches slow scrapes; a shorter one forgets sooner and is less sticky across demos.

**`min_window_queries`** — Minimum number of queries that must sit in the current window before **any** elevated or severe score can fire. Until that floor is met, severity stays `none` even if coverage looks high. This stops a single Query Lab click (or a few exploratory asks) from looking like extraction. Coverage, breadth, and novelty all wait on this floor in the current scorer.

**`min_corpus_size`** — Floor on tenant corpus size before the **coverage** signal is used. On tiny corpora (demo DBs, handful of sample docs), “touched 2 of 5 docs” is noise, not a scrape. If `corpus_size` is below this value, coverage is treated as inactive (effectively 0 for scoring). Breadth and novelty can still fire once `min_window_queries` is met.

**`elevated_coverage`** — Softer coverage alarm. Coverage is “distinct documents touched in the window ÷ total docs in the tenant corpus.” If that fraction reaches this value (and the window is full, and coverage is active), severity becomes **elevated** — suspicious breadth, but not the worst tier. Example: `0.25` means about a quarter of the corpus in one window.

**`severe_coverage`** — Harder coverage alarm. Same fraction as above; at or above this value (full window, coverage active), severity is **severe**. Example: `0.50` means roughly half the corpus. Severe can also come from breadth alone (see below).

**`breadth_ratio_threshold`** — Threshold on breadth (distinct documents ÷ window queries). High breadth means the subject is spreading across many documents relative to how often they asked — walking the shelves rather than digging into one topic. Values can exceed `1.0` when each query returns multiple docs. At or above this threshold with a full window, severity is **severe**. The usual production default `0.8` means roughly four different docs for every five queries. This signal exposes **authorized breadth abuse**: reconstructing the corpus through many allowed, recall-maximizing asks. Demo Case C may lower the threshold (for example `0.5`) because Alice’s three visible sample docs over five queries top out near `0.6`.

**`novelty_ratio_threshold`** — Threshold on novelty (share of window queries that unlocked at least one previously unseen `document_id`). High novelty means the session keeps finding first-time material — systematic exploration rather than re-asking the same sources. At or above this threshold with a full window, severity is **elevated** only (novelty never drives severe alone). Typical production default is `0.9`. Demo Case D uses `0.5` with a `top_k: 1` one-doc query sequence; reusing Case A’s `top_k: 5` scrape often collapses novelty or lets breadth win instead.

**`action`** — What happens to the **live query** when severity is **severe**:

| Value | Effect |
|--------|--------|
| `alert` | Audit only; traffic keeps flowing (usual soft / demo mode) |
| `challenge` | Step-up / challenge path for that request |
| `throttle` | Throttle that request |

Audit still labels elevated as `challenge` and severe as `block` on `extraction_suspected` events. With `action: alert`, those audit labels do **not** mean the query was actually blocked.

### Severity criteria

Scored **per `(tenant_id, subject)`** after each ACL-filtered retrieval. Document title/content and ingest parameters are **not** inputs.

Once the window has enough queries (`window_queries ≥ min_window_queries`), the three signals answer different questions:

- **Coverage** — How much of the whole corpus has this person touched?
- **Breadth** — Are they spreading across many docs per query?
- **Novelty** — Does each query keep unlocking new docs?

**Severe** if coverage ≥ `severe_coverage` **or** breadth ≥ `breadth_ratio_threshold`.  
**Elevated** (if not already severe) if coverage ≥ `elevated_coverage` **or** novelty ≥ `novelty_ratio_threshold`.  
Otherwise **none** — including any session still shorter than `min_window_queries`.

| Severity | When (any condition that matches, **and** full window) |
|----------|-----------------------------------|
| **severe** | `corpus_coverage ≥ severe_coverage` **or** `breadth_ratio ≥ breadth_ratio_threshold` |
| **elevated** | (if not severe) `corpus_coverage ≥ elevated_coverage` **or** `novelty_ratio ≥ novelty_ratio_threshold` |
| **none** | Otherwise (including sessions shorter than `min_window_queries`) |

Definitions:

| Metric | Formula |
|--------|---------|
| `corpus_coverage` | `distinct_documents / corpus_size` (total tenant docs; requires `corpus_size ≥ min_corpus_size`) |
| `breadth_ratio` | `distinct_documents / window_queries` |
| `novelty_ratio` | share of window queries that touched at least one new `document_id` |

**All signals require a full window** (`window_queries ≥ min_window_queries`). A single Query Lab retrieval over a 5-document sample corpus cannot trip elevated/severe.

**`action` vs audit `decision`:** Audit always records severity as `elevated → challenge`, `severe → block` on `kind=extraction_suspected`. The query itself is blocked only when severity is **severe** and `action` is `challenge` or `throttle`. With `action: alert`, traffic is not blocked for extraction even though Audit may still show `challenge`/`block` on the event row.

### Where to see what fired

Severity alone is not enough for triage — the monitor also records **which signal(s)** crossed their thresholds.

| Surface | What you get |
|---------|----------------|
| **Audit Log** (`kind=extraction_suspected`) | Finding `category` is the firing signal(s) (`coverage`, `breadth`, `novelty`, or joined with `+`). Finding `detail` / event Detail JSON include `triggered_by` and a human `trigger_summary` (e.g. `breadth_ratio 0.85 ≥ 0.8`). |
| **Extraction watch** (`GET /admin/extraction/watch`) | Each elevated/severe subject includes `triggered_by` and `trigger_summary` alongside the ratios. |
| **Query Lab / `/v1/query`** | Only when the request is actually paused (`action: challenge` or `throttle`): `block_reason=extraction_suspected` plus `block_detail` with the same cause line (also echoed in the answer text). Normal allowed queries do not return the ratios. |

**UI demo cases** (coverage / breadth / novelty / Query Lab pause): [lab9 UI_TESTING — UI demo cases](../../../ENTERPRISE.md#ui-demo-cases-trigger--artifacts).

State is **in-process** — it accumulates across Query Lab, redteam, and API traffic for the same subject until the window ages out or the proxy restarts.

**Common confusion:** changing a redteam scenario’s `setup.ingest` `document_id` / title / content does **not** clear or avoid this finding. Those fields only add another corpus document; the monitor still scores the attack token’s subject (e.g. `employee-demo-token` → `alice.engineer`) over the sliding window.

### Operator notes (tuning & demos)

| Runtime | Active policy file |
|---------|-------------------|
| Docker (`docker_start.sh`) | `data/policy.yaml` |
| Host uvicorn | `rag-protection-proxy/config/policy.yaml` (or `RAG_POLICY_FILE`) |

1. Edit the `extraction:` block in the **active** policy file (not only the repo seed if Docker already seeded `data/`).
2. Reload: `POST /admin/reload-policy` (YAML edits do not apply until reload). Only `enabled` has an env shortcut (`RAG_EXTRACTION_ENABLED`); `window_seconds` / thresholds are YAML-only.
3. **Live score ≠ Audit history.** `window_seconds` only expires the in-memory per-subject deque. Waiting that long (or restarting the proxy) clears **watch** state; it does **not** delete prior Audit Log rows. Judge a clean slate with `GET /admin/extraction/watch` (`subjects: []`), not by whether old `extraction_suspected` rows disappear.
4. After a wait/restart, you still need **`min_window_queries`** before any elevated/severe trip. A single probe alone cannot fire; run a full window of retrievals that return chunks.
5. To soft-demo without blocking: keep `action: alert`. To show Query Lab `block_detail`, set `action: challenge` or `throttle` (see UI Case B). To stop re-trips while iterating other labs: raise coverage thresholds, disable `extraction.enabled`, or restart and avoid multi-scenario bursts under the same token.

```bash
export RAG_PROTECTION_ADMIN_KEY=rag-admin-demo-key
curl -s -X POST http://localhost:8090/admin/reload-policy \
  -H "Authorization: Bearer $RAG_PROTECTION_ADMIN_KEY" | jq '{status, policy_version}'
curl -s http://localhost:8090/admin/extraction/watch \
  -H "Authorization: Bearer $RAG_PROTECTION_ADMIN_KEY" | jq '{enabled, action, count, subjects}'
```

### API

| Endpoint | Purpose |
|----------|---------|
| `GET /admin/extraction/watch` | **Current** elevated/severe subjects (live window) |
| `GET /admin/audit/events?kind=extraction_suspected` | Historical audit feed (does not TTL with `window_seconds`) |
| `GET /admin/audit/export?kind=extraction_suspected` | SIEM export |

---

## Validate (smoke)

```bash
bash tools/docker_start.sh
export RAG_PROTECTION_ADMIN_KEY=rag-admin-demo-key

# Enable extraction in data/policy.yaml (see demo doc for demo thresholds), then:
curl -s -X POST http://localhost:8090/admin/reload-policy \
  -H "Authorization: Bearer $RAG_PROTECTION_ADMIN_KEY" | jq '{status, policy_version}'

cd rag-protection-proxy && pytest tests/test_extraction.py -q
```

Full scripted scrape demo: [../demos/02-extraction-monitor.md](../demos/02-extraction-monitor.md).

---

## Gaps & non-claims

| In scope | Out of scope |
|----------|--------------|
| Per-subject sliding-window scoring on retrieval | Per-query content filter or ingest-content judgment |
| `extraction_suspected` + optional step-up/throttle | Guaranteed prevention of all exfiltration |
| Coverage / breadth / novelty signals | Cross-account distributed scrape (use SIEM #5) |

- **Not an ACL** — catches authorized breadth abuse after Guardrail 1 passes.
- **Not a rate limiter** — orthogonal to E4.5 volume caps (EE).
- **Not ingest quarantine / injection scoring** — does not read document body, title, or ingest allow/reject outcome; only retrieved `document_id` sets per subject.
- **Behavioral signal** — default is alert-only; tune thresholds per tenant during POC.

---

## Engineering reference

| Artifact | Path |
|----------|------|
| Scorer | `guardrails/extraction.py` |
| Config | `config.py` → `ExtractionRules` |
| Admin route | `GET /admin/extraction/watch` |
| SIEM detection | `deploy/siem/` — `RAG-Corpus-Extraction` |
| Plain-English primer (ratios vs RAG response) | [HOW_RAG_WORKS.md](../../product/HOW_RAG_WORKS.md#coverage-breadth_ratio-and-novelty_ratio) |
| Full spec (archived) | [lab9 SPEC](../../../ENTERPRISE.md) |
| UI testing | [lab9 UI_TESTING](../../../ENTERPRISE.md) |
