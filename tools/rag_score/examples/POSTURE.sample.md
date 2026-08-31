<!--
  Sample rag-score output (markdown). Generated with:

    tools/rag-score --env prod \
      --policy tools/rag_scan/tests/fixtures/bad_policy.yaml \
      --acl    tools/rag_scan/tests/fixtures/bad_acl.yaml \
      --sample-docs tools/rag_scan/tests/fixtures/bad_sample_documents.json

  This is a deliberately *failing* configuration, used to show what a low grade
  looks like. The shipped production config (acl_policy.prod.yaml) grades A.
-->

# Marifort Gate — RAG security posture scorecard

## Grade: F  (0/100)

_Failing posture — critical misconfigurations are present right now._

Scanned at `--env prod` · 4 critical · 4 warning · 0 info

## OWASP LLM Top 10 coverage

| Risk | Area | Status | Rules |
|------|------|--------|-------|
| LLM01 | Prompt injection | WARN · Needs attention | POL001, POL003 |
| LLM06 | Sensitive information disclosure | CRITICAL · At risk (critical) | ACL001, ACL002, ACL003, CON001, POL002, SEC001 |
| LLM07 | Insecure plugin / tool design | n/a · Not assessed here | — |
| LLM08 | Excessive agency | n/a · Not assessed here | — |

> LLM07: Not assessed by a config scan — covered at runtime by the Marifort Gate tool gateway (allowlist + audit). See Lab 1 (MCP gateway).
> LLM08: Not assessed by a config scan — covered at runtime by the Marifort Gate tool gateway (allowlist + audit). See Lab 1 (MCP gateway).

## Top fixes

1. **[ACL001] Demo bearer tokens present in production ACL** (critical)
   - 1 static demo token(s) defined while --env=prod (e.g. employee-demo-token). Anyone with the token bypasses the IdP.
   - Fix: Remove `demo_users` in production and rely on OIDC bearer tokens.
   - Location: `tools/rag_scan/tests/fixtures/bad_acl.yaml`
2. **[ACL002] Confidential document readable by broad group** (critical)
   - Document 'hr-payroll' (classification='confidential-hr') grants access to broad group(s): ['all-staff'].
   - Fix: Restrict `allowed_groups` to least-privilege groups (e.g. hr, executives).
   - Location: `tools/rag_scan/tests/fixtures/bad_sample_documents.json`
3. **[POL002] Connectors fail open on unmapped permissions** (critical)
   - connectors.enabled is true but unmapped_permissions='all_staff' (fail-open). Synced documents whose source ACL cannot be mapped become broadly readable.
   - Fix: Set connectors.unmapped_permissions: deny (fail-closed).
   - Location: `tools/rag_scan/tests/fixtures/bad_policy.yaml`

## Next step

This is a free self-serve grade. For a hands-on review of your RAG deployment, book the [GenAI/RAG security assessment](https://github.com/marifort/rag-protection/blob/main/docs/commercial/SOLOPRENEUR_PRODUCT_OPPORTUNITIES.md#1-genai--rag-security-assessment).

---
_Indicative posture grade, not a certification. Scores the *declared* configuration only and runs entirely locally — no configuration is uploaded._
