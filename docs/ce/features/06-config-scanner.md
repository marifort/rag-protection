# #6 — CI shift-left ACL scanner (`rag-scan`)

> **Which doc?** **Card** (this page) = behavior / policy · **Demo** = show it · **Learn** = teach it · **Lab** = GTM depth
>
> [Demo](../demos/06-config-scanner.md) · [Learn](../learn/01-core-moats.md#6-ci-shift-left-acl-scanner) · [Lab](../../../ENTERPRISE.md) · [Tutorial](../tutorials/05-labs-2-through-5.md)

| Field | Value |
|-------|-------|
| **Edition** | CE |
| **Status** | Shipped |
| **Code** | `tools/rag_scan/` · wrapper `tools/rag-scan` |
| **Tests** | `tools/rag_scan/tests/` |

**Demo:** [../demos/06-config-scanner.md](../demos/06-config-scanner.md) · **Tutorial:** [T05](../tutorials/05-labs-2-through-5.md)

---

## What & why

Most RAG breaches are **misconfiguration** (world-readable payroll, demo tokens in prod). Runtime guardrails do not catch bad config. `rag-scan` fails CI using the **same loaders** as the gateway (`load_policy` / `load_acl_policy`).

---

## How it works

```bash
tools/rag-scan check --env prod \
  --policy rag-protection-proxy/config/policy.yaml \
  --acl rag-protection-proxy/config/acl_policy.prod.yaml \
  --sample-docs tools/rag_scan/tests/fixtures/bad_sample_documents.json
```

Rules: ACL / POL / CON / SEC / VEC. Reporters: text, JUnit, SARIF.

---

## Gaps

Not a runtime gateway or generic IaC scanner. EE policy packs / pgvector probe are follow-ons.

## Engineering

[lab2 SPEC](../../../ENTERPRISE.md) · [tools/rag_scan/README.md](../../../tools/rag_scan/README.md)
