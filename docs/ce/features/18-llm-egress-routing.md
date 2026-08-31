# #18 — LLM egress routing by classification

> **Which doc?** **Card** (this page) = behavior / policy · **Demo** = show it · **Learn** = teach it · **Lab** = GTM depth
>
> [Demo](../demos/18-llm-egress-routing.md) · [Learn](../learn/02-runtime-and-operations.md#18-llm-egress-routing-by-classification) · [Lab](../../../ENTERPRISE.md) · [Tutorial](../tutorials/09-implemented-features-walkthrough.md#part-p-llm-egress-routing-t06-18)

| Field | Value |
|-------|-------|
| **Edition** | CE |
| **Status** | Shipped |
| **Legacy alias** | T0.6 |
| **Code** | `rag_protection_proxy/llm_routing.py` · hook in `pipeline.py` |
| **Tests** | `tests/test_llm_routing.py` |

**Demo:** [../demos/18-llm-egress-routing.md](../demos/18-llm-egress-routing.md) · **Tutorial:** [T09 §P](../tutorials/09-implemented-features-walkthrough.md#part-p-llm-egress-routing-t06-18)

---

## What & why

RFPs ask for **data residency** or dual-region LLM: HR/M&A on EU/on-prem, public FAQs on US SaaS — without building two chat apps.

After retrieval, the gateway reads the **highest-sensitivity** `metadata.classification` among context chunks, looks up `llm_routing:` policy, and calls the matching OpenAI-compatible endpoint. One `/v1/query` API; legal sees one architecture diagram.

**Not** #21 URL/SSRF packs — those guard outbound URLs; #18 chooses which LLM host receives the prompt.

---

## How it works

```text
retrieve chunks → context_blocks
  → resolve_llm_route(policy, chunk.metadata[])
  → highest classification by classification_rank
  → match routes[].match → endpoint_id
  → LLMClient(resolved policy).chat()
  → QueryResponse.llm_route + audit kind=llm_routed
```

### Policy

```yaml
llm_routing:
  enabled: true
  fail_closed: true
  default_endpoint_id: default
  classification_rank:
    - highly-confidential
    - confidential-hr
    - public
  routes:
    - match: confidential
      endpoint_id: eu-onprem
    - match: public
      endpoint_id: us-saas
  endpoints:
    eu-onprem:
      base_url: http://eu-llm/v1
      model: hr-onprem
    us-saas:
      base_url: http://us-llm/v1
      model: public-faq
```

Env: `RAG_LLM_ROUTING_ENABLED=1`. Reload after editing `data/policy.yaml`.

### Response

`QueryResponse.llm_route` includes `endpoint_id`, `model`, `classification`, `base_url_host`.

Unmapped classification + `fail_closed: true` → `blocked: true`, `block_reason: llm_routing_unmapped_classification`, LLM not called.

---

## Validate (smoke)

```bash
# Enable llm_routing.enabled: true in data/policy.yaml, reload, then:
curl -s -X POST http://localhost:8090/v1/query \
  -H "Authorization: Bearer employee-demo-token" \
  -H "Content-Type: application/json" \
  -d '{"query":"What are support hours?"}' | jq '{blocked, llm_route}'

cd rag-protection-proxy && pytest tests/test_llm_routing.py -q
```

Full demo: [../demos/18-llm-egress-routing.md](../demos/18-llm-egress-routing.md).

---

## Gaps & non-claims

| In scope | Out of scope |
|----------|--------------|
| Route by document classification label | Live network egress interception |
| Fail-closed unmapped classes | Residency compliance certification |
| Audit `llm_routed` with endpoint id | #21 URL reputation / SSRF packs |

---

## Engineering reference

| Artifact | Path |
|----------|------|
| Router | `llm_routing.py` |
| Full spec | [t06 SPEC](../../../ENTERPRISE.md) |
| Procurement context | [feature-roadmap-gtm § D6](../../../ENTERPRISE.md) |
