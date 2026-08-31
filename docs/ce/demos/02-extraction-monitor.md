# Demo: #2 — Corpus-extraction monitor

**~5 minutes.** Scripted corpus walk trips `extraction_suspected`; a normal session does not. Attribution fields (`triggered_by`, `trigger_summary`) appear in Audit / watch; Query Lab pause shows `block_detail` when `action` blocks.

**Feature reference:** [../features/02-extraction-monitor.md](../features/02-extraction-monitor.md) · **Tutorial:** [T09 §A](../tutorials/09-implemented-features-walkthrough.md#part-a-corpus-extraction-monitor-lab-9-2) · **UI demo cases:** [lab9 UI_TESTING](../../../ENTERPRISE.md#ui-demo-cases-trigger--artifacts)

---

## 0. One-time setup (off camera)

### Start stack

```bash
bash tools/docker_start.sh
export RAG_PROTECTION_ADMIN_KEY=rag-admin-demo-key
```

### Add demo policy (required)

The YAML block below is **not applied automatically** — paste it into the policy file the **proxy** loads, then reload.

| Runtime | Active policy file | Notes |
|---------|-------------------|--------|
| **Docker** (`docker_start.sh`) | `data/policy.yaml` | Seeded from `rag-protection-proxy/config/policy.yaml` on first start |
| **Host** (`uvicorn`) | `rag-protection-proxy/config/policy.yaml` | Or `RAG_POLICY_FILE` |

**Demo thresholds** (short window, low query floor) — **Case A / coverage severe**:

```yaml
extraction:
  enabled: true
  window_seconds: 600
  min_window_queries: 5
  min_corpus_size: 5
  elevated_coverage: 0.25
  severe_coverage: 0.50
  breadth_ratio_threshold: 0.8
  novelty_ratio_threshold: 0.9
  action: alert
```

For **Query Lab pause** (`block_reason` / `block_detail`), set `action: throttle` (or `challenge`). For breadth-only or novelty-only attribution, use the tuned blocks in [UI demo Cases C–D](../../../ENTERPRISE.md#ui-demo-cases-trigger--artifacts).

**Reload:**

```bash
curl -s -X POST http://localhost:8090/admin/reload-policy \
  -H "Authorization: Bearer $RAG_PROTECTION_ADMIN_KEY" | jq '{status, policy_version}'

curl -s http://localhost:8090/admin/extraction/watch \
  -H "Authorization: Bearer $RAG_PROTECTION_ADMIN_KEY" | jq '{enabled, subjects}'
```

**Preflight** — shipped sample corpus is **5** docs. If count is much higher, reset or use vocabulary-aligned scrape in §2:

```bash
curl -s http://localhost:8090/v1/documents \
  -H "Authorization: Bearer employee-demo-token" | jq '.documents | length'
```

Restarting the proxy clears the in-process extraction window.

---

## 1. Baseline — normal session (30 sec)

```bash
for q in "what is the pto policy" "who approves expenses"; do
  curl -s -X POST http://localhost:8090/v1/query \
    -H "Authorization: Bearer employee-demo-token" \
    -H "Content-Type: application/json" \
    -d "{\"query\": \"$q\", \"top_k\": 3}" | jq -r '.subject'
done
```

Narrative: "Two targeted questions. Low coverage — nothing fires."

---

## 2. Scripted scrape (60 sec)

Use terms that match **sample document vocabulary**:

```bash
for q in \
  "pto policy support hours office" \
  "on-call deployment rollback incident severity" \
  "customer billing feedback ticket invoice" \
  "support policy incident deployment billing" \
  "on-call runbook api key rotation pool"; do
  curl -s -X POST http://localhost:8090/v1/query \
    -H "Authorization: Bearer employee-demo-token" \
    -H "Content-Type: application/json" \
    -d "{\"query\": \"$q\", \"top_k\": 5}" | jq '{blocked, block_reason, block_detail}'
done
```

Narrative: "Broad, recall-maximizing queries — the shape of a corpus walk."

With `action: alert`, expect `blocked: false` and empty `block_reason` even after the trip (audit still records the event). With `action: throttle`/`challenge`, the trip query shows `block_reason: extraction_suspected` and a `block_detail` cause line.

---

## 3. Show the alert (60 sec)

```bash
curl -s "http://localhost:8090/admin/extraction/watch" \
  -H "Authorization: Bearer $RAG_PROTECTION_ADMIN_KEY" | jq '.'

curl -s "http://localhost:8090/admin/audit/events?kind=extraction_suspected" \
  -H "Authorization: Bearer $RAG_PROTECTION_ADMIN_KEY" | jq '.events[0] | {kind, decision, subject, findings, detail}'
```

**Expected artifacts**

| Surface | Fields |
|---------|--------|
| Watch | `severity`, `corpus_coverage`, `triggered_by`, `trigger_summary` |
| Audit event | Finding `category` (e.g. `coverage`), `label` (`severe`), `detail` = cause line |
| Audit `detail` JSON | `triggered_by`, `trigger_summary`, ratios, `distinct_documents`, `window_queries`, `corpus_size` |

Example watch subject (ratios vary):

```json
{
  "subject": "alice.engineer",
  "severity": "severe",
  "triggered_by": ["coverage"],
  "trigger_summary": "coverage 0.60 ≥ 0.5"
}
```

---

## 4. UI path (operator console)

Open [http://localhost:8090/ui](http://localhost:8090/ui) and run the labeled cases:

| Case | What it proves |
|------|----------------|
| **A** Coverage severe | Audit + Watch show `triggered_by: ["coverage"]` |
| **B** Query Lab pause | Banner + `block_reason` / `block_detail` |
| **C** Breadth only | Finding category `breadth` |
| **D** Novelty elevated | Finding category `novelty`, decision `challenge` |
| **E** Extraction Watch | Live offenders include attribution fields |
| **F** Analytics / export | By-kind count + NDJSON with `triggered_by` |

Full click-path: [UI_TESTING — UI demo cases](../../../ENTERPRISE.md#ui-demo-cases-trigger--artifacts).

---

## 5. Unit suite (off camera)

```bash
cd rag-protection-proxy && pytest tests/test_extraction.py -q
```

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `enabled: true` but no alert after scrape | Demo thresholds not in `data/policy.yaml` — replace `extraction:` block and reload |
| Queries return zero chunks | Use vocabulary-aligned terms in §2, not one-word probes |
| Corpus bloated from prior labs | Reset `data/tenants/default/documents.db` or use broader scrape |
| Stale window from prior session | `docker compose restart rag-protection-proxy` |
| Waited `window_seconds` but Audit still shows old block | Expected — Audit history does not TTL; confirm clean slate with `/admin/extraction/watch` → `subjects: []` |
| No trip after a single probe post-restart | All signals need `min_window_queries` (demo: 5) |
| Audit says `challenge`/`block` but query allowed | `action: alert` — audit severity mapping ≠ query enforcement |
| Blocked but no `block_detail` | Rebuild/restart proxy with attribution change; use `action: throttle`/`challenge` |

---

## Close

Pair with **#3 canary**: canary hit + high extraction score = high-confidence exfil alarm, shown in `/ui` as **Suspected data theft**. Combined curl + UI sample: [exfil-correlation DEMO_SCRIPT](../../../ENTERPRISE.md). Both export to **#5 SIEM** (`RAG-Corpus-Extraction` / `RAG-Exfil-HighConfidence`).
