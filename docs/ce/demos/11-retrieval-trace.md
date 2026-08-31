# Demo: #11 — Retrieval explainability trace

**~3 minutes.** Show ACL exclusions and selected chunks in one query.

**Feature reference:** [../features/11-retrieval-trace.md](../features/11-retrieval-trace.md) · **Tutorial:** [T09 §G](../tutorials/09-implemented-features-walkthrough.md#part-g-retrieval-explainability-trace-11-t07)

---

## 0. Setup

```yaml
retrieval:
  explainability_enabled: true
  max_trace_candidates: 100
```

```bash
bash tools/docker_start.sh
export RAG_PROTECTION_ADMIN_KEY=rag-admin-demo-key

curl -s -X POST http://localhost:8090/admin/reload-policy \
  -H "Authorization: Bearer $RAG_PROTECTION_ADMIN_KEY" | jq .
```

---

## 1. Engineer query — payroll excluded by ACL (90 sec)

```bash
curl -s -X POST http://localhost:8090/v1/query \
  -H "Authorization: Bearer employee-demo-token" \
  -H "Content-Type: application/json" \
  -d '{"query":"payroll confidential Q1 total","include_retrieval_trace":true}' \
  | jq '{chunks: [.chunks[].document_id], trace: [.retrieval_trace[] | {document_id, outcome}]}'
```

**Expected:** Payroll-related docs show `outcome: excluded_acl`; returned chunks omit HR-only payroll.

Narrative: *"Same search candidates — ACL removed them before top-k. That's Guardrail 1, visible in the trace."*

---

## 2. HR query — payroll selected (60 sec)

```bash
curl -s -X POST http://localhost:8090/v1/query \
  -H "Authorization: Bearer hr-demo-token" \
  -H "Content-Type: application/json" \
  -d '{"query":"payroll Q1 total disbursement","include_retrieval_trace":true}' \
  | jq '.retrieval_trace[] | select(.outcome=="selected") | {document_id, outcome, detail}'
```

**Expected:** Payroll doc `selected` for HR token.

---

## 3. Audit + UI (45 sec)

```bash
curl -s "http://localhost:8090/admin/audit/events?kind=retrieval_trace&limit=3" \
  -H "Authorization: Bearer $RAG_PROTECTION_ADMIN_KEY" | jq '.events[0].kind'
```

**Query Lab (CE):** enable **include_retrieval_trace** → run the same query → **Retrieval Explainability** table.

**Policy knobs (EE):** Policy Viewer/Admin → **Edit → Advanced Features → Retrieval** → set `retrieval.explainability_enabled` / `retrieval.max_trace_candidates` → **Save Policy Knobs**. That writes Audit events; it does not fill the Query Lab table by itself. Operator notes: [feature card](../features/11-retrieval-trace.md#console).

---

## 4. Unit suite (off camera)

```bash
cd rag-protection-proxy && pytest tests/test_retrieval_trace.py -q
```
