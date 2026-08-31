# Demo: #8 — Per-claim citation hard gate

**~3 minutes.** Mixed grounded + ungrounded query trips hard gate block.

**Feature reference:** [../features/08-citation-hard-gate.md](../features/08-citation-hard-gate.md) · **Tutorial:** [T09 §E](../tutorials/09-implemented-features-walkthrough.md#part-e-per-claim-citation-hard-gate-8) · **Pipeline depth:** [GUARDRAIL_4_CITATION.md](../security/GUARDRAIL_4_CITATION.md)

---

## 0. Setup

Require per-claim mapping, the hard gate, a three-token substantive floor, and 15% soft coverage. Full prose for each knob: [feature policy](../features/08-citation-hard-gate.md#policy).

```yaml
output:
  per_claim_citations: true
  hard_citation_gate: true
  substantive_min_tokens: 3
  min_citation_coverage: 0.15
```

```bash
bash tools/docker_start.sh
export RAG_PROTECTION_ADMIN_KEY=rag-admin-demo-key

curl -s -X POST http://localhost:8090/admin/reload-policy \
  -H "Authorization: Bearer $RAG_PROTECTION_ADMIN_KEY" | jq .
```

---

## 1. Ungrounded mixed query (90 sec)

Ask for something partially in corpus + fabricated metric:

```bash
curl -s -X POST http://localhost:8090/v1/query \
  -H "Authorization: Bearer employee-demo-token" \
  -H "Content-Type: application/json" \
  -d '{"query":"Summarize support hours and Q3 revenue growth"}' \
  | jq '{blocked, block_reason, hard_gate: .citations.hard_gate_failed, unsupported: .citations.unsupported_claims}'
```

**Expected:** `block_reason: citation_hard_gate_failed`, `hard_gate_failed: true`.

---

## 2. Grounded query — passes (60 sec)

```bash
curl -s -X POST http://localhost:8090/v1/query \
  -H "Authorization: Bearer employee-demo-token" \
  -H "Content-Type: application/json" \
  -d '{"query":"What are support hours?"}' \
  | jq '{blocked, citations_passed: .citations.passed}'
```

**Expected:** `blocked: false`, citations pass.

---

## 3. Audit (30 sec)

```bash
curl -s "http://localhost:8090/admin/audit/events?kind=citation_failed&limit=3" \
  -H "Authorization: Bearer $RAG_PROTECTION_ADMIN_KEY" | jq '.events[0] | {kind, decision, detail}'
```

UI: **Query Lab → Ungrounded demo** — blocked banner + unsupported claim rows.

---

## 4. Unit suite (off camera)

```bash
cd rag-protection-proxy && pytest tests/test_e3.py -k hard_citation_gate -q
```
