# #10 — Packaged red-team harness

> **Which doc?** **Card** (this page) = behavior / policy · **Demo** = show it · **Learn** = teach it · **Lab** = GTM depth
>
> [Demo](../demos/10-redteam.md) · [Learn](../learn/01-core-moats.md#10-packaged-red-team-harness) · [Lab](../../../ENTERPRISE.md) · [Tutorial](../tutorials/05-labs-2-through-5.md)

| Field | Value |
|-------|-------|
| **Edition** | CE (CLI) · Service packaging |
| **Status** | Shipped |
| **Code** | `tools/redteam/` · `tools/rag-redteam` |

**Demo:** [../demos/10-redteam.md](../demos/10-redteam.md) · **Tutorial:** [T05](../tutorials/05-labs-2-through-5.md) · [T08](../../../ENTERPRISE.md)

---

## What & why

Security teams want **evidence, not slides**. Harness runs YAML scenarios against live `/v1/ingest`, `/v1/query`, audit export → report + artifacts for consulting engagements.

Not model-weight red teaming or a fuzzing platform.

---

## How it works

```bash
tools/rag-redteam run --all \
  --base-url http://localhost:8090 \
  --out /tmp/rt-demo \
  --engagement "demo"
```

Produces `report.md` + per-scenario evidence under `--out`.

## Engineering

[lab5 SPEC](../../../ENTERPRISE.md) · [tools/redteam/README.md](../../../tools/redteam/README.md)
