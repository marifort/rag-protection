# #29 — Vector ACL backfill

> **Which doc?** **Card** (this page) = behavior / policy · **Demo** = show it · **Learn** = teach it · **Lab** = GTM depth
>
> [Demo](../demos/29-acl-backfill.md) · [Learn](../learn/03-tools-and-assessment.md#29-vector-acl-backfill) · [Lab](../../../ENTERPRISE.md) · [Tutorial](../tutorials/09-implemented-features-walkthrough.md#part-n-vector-acl-backfill-a4-29)

| Field | Value |
|-------|-------|
| **Edition** | CE tool (full mapping path may use EE `acl_mapping`) |
| **Status** | Shipped |
| **Code** | `tools/acl_backfill/` · `tools/acl-backfill` |

**Demo:** [../demos/29-acl-backfill.md](../demos/29-acl-backfill.md) · **Tutorial:** [T09 §N](../tutorials/09-implemented-features-walkthrough.md#part-n-vector-acl-backfill-a4-29)

---

## What & why

Workshops hit *"corpus already indexed without `allowed_groups`."* One-shot metadata backfill onto Qdrant / pgvector / memory using the **same** `acl_mapping` functions as runtime — dry-run + apply.

Not a live sync (#12), connector (#28), or re-embed pipeline.

```bash
tools/acl-backfill plan ...
tools/acl-backfill apply ...
```

## Engineering

[a4 SPEC](../../../ENTERPRISE.md)
