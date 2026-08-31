# Demo: #6 — Config scanner (`rag-scan`)

**~3 minutes.** Bad fixture fails scan; prod ACL stays clean.

**Feature:** [../features/06-config-scanner.md](../features/06-config-scanner.md)

```bash
tools/rag-scan --version

# Bad PR fixture → CI red
tools/rag-scan check --env prod \
  --policy rag-protection-proxy/config/policy.yaml \
  --acl rag-protection-proxy/config/acl_policy.prod.yaml \
  --sample-docs tools/rag_scan/tests/fixtures/bad_sample_documents.json

# Expected: non-zero exit, ACL findings on all-staff payroll
```

Full script: [lab2 DEMO](../../../ENTERPRISE.md).
