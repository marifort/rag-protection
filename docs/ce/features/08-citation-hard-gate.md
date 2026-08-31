# #8 — Per-claim citation hard gate

> **Which doc?** **Card** (this page) = behavior / policy · **Demo** = show it · **Security** = pipeline depth · **Learn** = teach it
>
> [Demo](../demos/08-citation-hard-gate.md) · [Security](../security/GUARDRAIL_4_CITATION.md) · [Learn](../learn/01-core-moats.md#8-per-claim-citation-hard-gate) · [Tutorial](../tutorials/09-implemented-features-walkthrough.md#part-e-per-claim-citation-hard-gate-8) · Phase depth: [E3.4](../../../ENTERPRISE.md) · [E3.5 entailment](../../../ENTERPRISE.md)

| Field | Value |
|-------|-------|
| **Edition** | CE |
| **Status** | Shipped |
| **Legacy alias** | Moat #8 / E3.4 related |
| **Code** | `rag_protection_proxy/guardrails/citation.py` |
| **Tests** | `tests/test_e3.py::test_hard_citation_gate_*` |
| **Pipeline doc** | [GUARDRAIL_4_CITATION.md](../security/GUARDRAIL_4_CITATION.md) |

**Demo:** [../demos/08-citation-hard-gate.md](../demos/08-citation-hard-gate.md) · **Tutorial:** [T09 §E](../tutorials/09-implemented-features-walkthrough.md#part-e-per-claim-citation-hard-gate-8) · **Learn:** [learn §#8](../learn/01-core-moats.md#8-per-claim-citation-hard-gate)

---

## What & why

Guardrail 4 verifies LLM answers against retrieved context. The **hard gate** goes further: any **substantive** sentence without a supporting `chunk_id` causes a **block** — not just a low coverage warning.

Stops ungrounded claims (including hallucinated revenue figures mixed with grounded FAQ text) from reaching users when procurement requires provable grounding.

---

## How it works

```text
LLM answer
  → verify_citations() per sentence
  → map claims to chunk_id + offsets (per_claim_citations)
  → hard_citation_gate: substantive sentence without support → BLOCK
  → SAFE_FALLBACK + citation_failed audit
```

### Policy

```yaml
output:
  per_claim_citations: true
  hard_citation_gate: true
  substantive_min_tokens: 3
  min_citation_coverage: 0.15
  block_system_prompt_leak: true
```

These four knobs sit under `output:` and control how Guardrail 4 judges whether an LLM answer is grounded in retrieved sources. They work together: coverage is the floor, and the hard gate is the “no ungrounded substantive claim” ceiling.

**`per_claim_citations`** turns on sentence-level citation mapping. After generation, each answer sentence is checked against retrieved chunks and recorded in `citations.claims[]` with fields such as `sentence`, `chunk_id`, `supported`, and character offsets. This knob is required for the hard gate: without it, the proxy only knows an overall coverage ratio, not which individual claims lack support.

**`hard_citation_gate`** is the strict mode. When enabled (and `per_claim_citations` is also on), any substantive sentence without a supporting `chunk_id` fails the whole answer — even if most of the answer is grounded. That is what catches mixed answers such as grounded support-hours text plus a hallucinated “Q3 revenue grew 40%” claim. Soft coverage alone might still pass such an answer; the hard gate does not. The block reason is `citation_hard_gate_failed`.

**`substantive_min_tokens`** defines what counts as a substantive claim for the hard gate. Sentences with fewer than this many tokens (for example “Yes.” or “OK.”) are ignored so short filler does not trigger a block. Raise it (for example to 4–5) if you get false blocks on short acknowledgments; lower it to treat shorter phrases as claims that must be cited.

**`min_citation_coverage`** is the soft ratio gate: at least this fraction of sentences must align with retrieved context (`coverage_ratio >= min_citation_coverage`). This check always applies. The final pass condition is:

`passed = (coverage_ratio >= min_citation_coverage) AND (not hard_gate_failed)`

So both gates must succeed. In the demo query (“support hours and Q3 revenue growth”), an answer can still clear 15% coverage if most sentences are FAQ-grounded, but the fabricated revenue sentence fails the hard gate and the answer is replaced with the safe fallback.

### Block behavior

| Field | Value |
|-------|-------|
| `blocked` | `true` |
| `block_reason` | `citation_hard_gate_failed` |
| Audit `kind` | `citation_failed` |
| Detail | `unsupported_claims[]` |

Base citation verification (soft gate) documented in [GUARDRAIL_4_CITATION.md](../security/GUARDRAIL_4_CITATION.md).

---

## Validate (smoke)

```bash
curl -s -X POST http://localhost:8090/v1/query \
  -H "Authorization: Bearer employee-demo-token" \
  -H "Content-Type: application/json" \
  -d '{"query":"Summarize support hours and Q3 revenue growth"}' \
  | jq '{block_reason, hard_gate: .citations.hard_gate_failed}'

cd rag-protection-proxy && pytest tests/test_e3.py -k hard_citation_gate -q
```

Full demo: [../demos/08-citation-hard-gate.md](../demos/08-citation-hard-gate.md).

---

## Console

**Policy → Edit → Thresholds** — enable `hard_citation_gate` + `per_claim_citations` → **Query Lab → Ungrounded demo**.

---

## Gaps & non-claims

- Heuristic token overlap — not entailment/NLP judge (see E3.5 for rescoring).
- Only checks against **retrieved** context passed to the model.
- On **host uvicorn** without a reachable LLM, the proxy’s “temporarily unavailable…” fallback is often blocked as an unsupported substantive claim. That is the hard gate working; set `RAG_LLM_BASE_URL=http://localhost:12434/engines/v1` (see [EE_CUSTOMER_DELIVERY.md — /tmp demo](../../../ENTERPRISE.md#local-pc--tmp-demo-ce-and-ee)).

---

## Engineering reference

**Depth docs for this feature:** this card (policy / hard gate) + [GUARDRAIL_4_CITATION.md](../security/GUARDRAIL_4_CITATION.md) (pipeline / soft citation). Do not treat the related links below as a second source of truth for knobs or `block_reason`.

| Artifact | Path |
|----------|------|
| Citation module | `guardrails/citation.py` |
| Pipeline (Guardrail 4) | [GUARDRAIL_4_CITATION.md](../security/GUARDRAIL_4_CITATION.md) |

### Related (not peer depth)

| Topic | Document |
|-------|----------|
| Per-claim API / E3.4 delivery | [E3_4_PER_CLAIM_CITATIONS.md](../../../ENTERPRISE.md) |
| Quality vs security (rerank / HyDE / guardrails / citations) | [RAG_QUALITY_VS_SECURITY.md](../../product/RAG_QUALITY_VS_SECURITY.md) |
| Severity / risk map (all guardrails) | [DETECTION_OVERVIEW.md](../security/DETECTION_OVERVIEW.md) |
