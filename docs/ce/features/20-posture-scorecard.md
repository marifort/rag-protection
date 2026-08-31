# #20 — RAG posture scorecard

> **Which doc?** **Card** (this page) = behavior / policy · **Demo** = show it · **Learn** = teach it · **Lab** = GTM depth
>
> [Demo](../demos/20-posture-scorecard.md) · [Learn](../learn/03-tools-and-assessment.md#20-rag-posture-scorecard) · [Lab](../../../ENTERPRISE.md) · [Posture walkthrough](../../../ENTERPRISE.md) · [Tutorial](../tutorials/06-labs-a2-a3-a6-a7.md)

| Field | Value |
|-------|-------|
| **Edition** | CE (CLI) |
| **Status** | Shipped |
| **Code** | `tools/rag_score/` · wraps [#6](06-config-scanner.md) |

**Demo:** [../demos/20-posture-scorecard.md](../demos/20-posture-scorecard.md) · **Tutorial:** [T06](../tutorials/06-labs-a2-a3-a6-a7.md)

---

## What & why

Self-serve **A–F grade** of declared RAG config (markdown/HTML/JSON) for prospects before a sales call. Uses same `rag-scan` rules as CI.

```bash
tools/rag-score --policy ... --acl ... --format markdown
```

Not a penetration test or runtime audit.

## Engineering

[lab8 SPEC](../../../ENTERPRISE.md) · [POSTURE_WALKTHROUGH](../../../ENTERPRISE.md)
