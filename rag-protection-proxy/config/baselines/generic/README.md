# Generic baseline (CE)

Balanced secure defaults for internal/SaaS-style RAG deployments. Passes `rag-scan check --env prod` when used without confidential sample documents.

| Setting | Value | Rationale |
|---------|-------|-----------|
| `input.block_threshold` | 0.71 | Blocks high-confidence injection/DLP without excessive FP |
| `input.challenge_mode` | allow | Mid-risk ingest → quarantine queue for operator review |
| `output.min_citation_coverage` | 0.15 | Grounding check on generated answers |
| `connectors.unmapped_permissions` | deny | Fail-closed if connectors are enabled later |
| DLP patterns | CE sample (SSN + employee ID) | Demonstrates pack format; upgrade to EE HIPAA/PCI/GDPR packs |

Copy to your deployment:

```bash
tools/rag-baseline init --vertical generic --out ./config
```

Then replace OIDC placeholders in `acl_policy.yaml` and run `tools/rag-scan check --env prod`.
