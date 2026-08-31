# #19 — Grounding / hallucination checker

> **Which doc?** **Card** (this page) = behavior / policy · **Demo** = show it · **Security** = pipeline depth · **Learn** = teach it · **Lab** = GTM depth
>
> [Demo](../demos/19-grounding.md) · [Security](../security/GUARDRAIL_4_CITATION.md) · [Learn](../learn/03-tools-and-assessment.md#19-grounding--hallucination-checker) · [Lab](../../../ENTERPRISE.md) · [Tutorial](../tutorials/06-labs-a2-a3-a6-a7.md)

| Field | Value |
|-------|-------|
| **Edition** | CE (CLI) |
| **Status** | Shipped |
| **Code** | `tools/rag_ground/` · same `verify_citations` as Guardrail 4 |

**Demo:** [../demos/19-grounding.md](../demos/19-grounding.md) · **Tutorial:** [T06](../tutorials/06-labs-a2-a3-a6-a7.md) · **Verdict walkthrough:** [../../commercial/labs/lab6-grounding/VERDICT_WALKTHROUGH.md](../../../ENTERPRISE.md) · **Runtime:** [#8](08-citation-hard-gate.md)

---

## What & why

Expose Guardrail 4 as a **batch/CI tool** so teams can score answers against source chunks offline — same scoring as runtime, not a second engine.

```bash
tools/rag-ground check --answer "..." --sources sources.json
```

## Gaps

Not a fact-checker or hallucination guarantee.

## Engineering

[lab6 SPEC](../../../ENTERPRISE.md) · [GUARDRAIL_4](../security/GUARDRAIL_4_CITATION.md)
