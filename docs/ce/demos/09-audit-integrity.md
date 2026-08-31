# Demo: #9 — Tamper-evident audit log

**~2 minutes.** Enable chain → Verify chain in UI/API.

**Feature:** [../features/09-audit-integrity.md](../features/09-audit-integrity.md) · **Tutorial:** [T09 §F](../tutorials/09-implemented-features-walkthrough.md#part-f-tamper-evident-audit-log-9-t04)

```bash
bash tools/docker_start.sh
export RAG_PROTECTION_ADMIN_KEY=rag-admin-demo-key
# data/policy.yaml → audit.integrity_chain: true (+ RAG_AUDIT_FILE set)
curl -s -X POST http://localhost:8090/admin/reload-policy \
  -H "Authorization: Bearer $RAG_PROTECTION_ADMIN_KEY" | jq .

# Generate a few events, then:
curl -s http://localhost:8090/admin/audit/integrity/verify \
  -H "Authorization: Bearer $RAG_PROTECTION_ADMIN_KEY" | jq
```

UI: `/ui` → **Audit Log** → **Verify chain**.

```bash
cd rag-protection-proxy && pytest tests/test_audit_integrity.py -q
```
