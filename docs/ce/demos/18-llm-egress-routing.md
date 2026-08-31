# Demo: #18 — LLM egress routing

**~4 minutes.** Public FAQ → `us-saas`; HR payroll → `eu-onprem`; audit shows `llm_routed`.

**Feature reference:** [../features/18-llm-egress-routing.md](../features/18-llm-egress-routing.md) · **Tutorial:** [T09 §P](../tutorials/09-implemented-features-walkthrough.md#part-p-llm-egress-routing-t06-18)

---

## 0. Setup

Edit active policy (`data/policy.yaml` for Docker):

```yaml
llm_routing:
  enabled: true
```

```bash
bash tools/docker_start.sh
export RAG_PROTECTION_ADMIN_KEY=rag-admin-demo-key

curl -s -X POST http://localhost:8090/admin/reload-policy \
  -H "Authorization: Bearer $RAG_PROTECTION_ADMIN_KEY" | jq '{status, policy_version}'
```

For architecture proof without live dual endpoints: `pytest tests/test_llm_routing.py -q`

---

## 1. Public FAQ → us-saas (90 sec)

```bash
curl -s -X POST http://localhost:8090/v1/query \
  -H "Authorization: Bearer employee-demo-token" \
  -H "Content-Type: application/json" \
  -d '{"query":"What are support hours?"}' \
  | jq '{blocked, llm_route}'
```

**Expected:** `endpoint_id: "us-saas"`, `classification: "public"`.

---

## 2. HR payroll → eu-onprem (90 sec)

```bash
curl -s -X POST http://localhost:8090/v1/query \
  -H "Authorization: Bearer hr-demo-token" \
  -H "Content-Type: application/json" \
  -d '{"query":"What is the Q1 payroll total disbursement?"}' \
  | jq '{blocked, llm_route}'
```

**Expected:** `endpoint_id: "eu-onprem"`, classification reflecting `confidential-hr`.

---

## 3. Audit (45 sec)

```bash
curl -s "http://localhost:8090/admin/audit/events?kind=llm_routed&limit=5" \
  -H "Authorization: Bearer $RAG_PROTECTION_ADMIN_KEY" \
  | jq '.events[:2] | .[] | {kind, decision, detail}'
```

UI: `/ui` → **Audit Log** → filter **`llm_routed`**.

---

## 4. Fail-closed (optional)

Ingest doc with `metadata.classification: secret-board` (no route), query → `block_reason: llm_routing_unmapped_classification`.

---

## Pass criteria

| Check | Pass |
|-------|------|
| Public vs HR → different `endpoint_id` | ✓ |
| Audit `llm_routed` shows endpoint | ✓ |
| `pytest tests/test_llm_routing.py` green | ✓ |
