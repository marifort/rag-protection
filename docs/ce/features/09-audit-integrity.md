# #9 — Tamper-evident audit log

> **Which doc?** **Card** (this page) = behavior / policy · **Demo** = show it · **Security** = pipeline depth · **Learn** = teach it
>
> [Demo](../demos/09-audit-integrity.md) · [Security](../security/P2_PERSISTENT_AUDIT.md) · [Learn](../learn/01-core-moats.md#9-tamper-evident-audit-log) · [Tutorial](../tutorials/09-implemented-features-walkthrough.md#part-f-tamper-evident-audit-log-9-t04)

| Field | Value |
|-------|-------|
| **Edition** | CE |
| **Status** | Shipped |
| **Code** | `audit_integrity.py` · hash chain on JSONL |
| **Depth** | [AUDIT_INTEGRITY_AND_EXPORT.md](../README.md) · [P2_PERSISTENT_AUDIT.md](../security/P2_PERSISTENT_AUDIT.md) |

**Demo:** [../demos/09-audit-integrity.md](../demos/09-audit-integrity.md) · **Tutorial:** [T09 §F](../tutorials/09-implemented-features-walkthrough.md#part-f-tamper-evident-audit-log-9-t04)

---

## What & why

Security reviews ask whether audit logs can be silently rewritten. With `audit.integrity_chain: true`, each JSONL line carries SHA-256 `prev_hash` / `event_hash`. Operators verify via API or Audit Log **Verify chain**.

HMAC/KMS signing is **not** shipped — hash chain + customer SIEM/WORM is the posture.

---

## How it works

```yaml
audit:
  integrity_chain: true   # requires RAG_AUDIT_FILE
```

Env: `RAG_AUDIT_INTEGRITY_CHAIN=1`

```bash
curl -s http://localhost:8090/admin/audit/integrity/verify \
  -H "Authorization: Bearer $RAG_PROTECTION_ADMIN_KEY" | jq
```

UI: **Audit Log → Verify chain** → `valid` + `events_checked`.

---

## Gaps & non-claims

- Not cryptographic signing / non-repudiation under KMS.
- Customer owns file ACLs, backup, and SIEM immutability.

## Engineering reference

[AUDIT_INTEGRITY_AND_EXPORT.md](../README.md) · tests: `tests/test_audit_integrity.py`
