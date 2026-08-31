# Datadog log-based metrics (Lab 3 SIEM pack)

Create these in **Logs → Generate Metrics** (or via API). Filter on the RAG Protection audit pipeline.

| Metric name | Filter / group-by | Use |
|-------------|-------------------|-----|
| `rag.audit.events` | `@rag.kind:*` · group by `@rag.kind`, `@rag.decision` | Volume by event type |
| `rag.audit.blocks` | `@rag.decision:block` · group by `@rag.kind`, `@rag.tenant_id` | Block rate |
| `rag.audit.injection_blocks` | `@rag.kind:scan_input` `@rag.decision:block` `@findings.scanner:prompt_injection` | Injection SOC tile |
| `rag.audit.extraction_alerts` | `@rag.kind:extraction_suspected` · group by `@usr.id`, `@rag.tenant_id` | Lab 9 scraping |
| `rag.audit.canary_triggers` | `@rag.kind:canary_triggered` · group by `@usr.id`, `@rag.tenant_id` | Lab 10 ACL tripwire |

## Suggested monitors (pair with metrics)

| Monitor | Query sketch | Severity |
|---------|--------------|----------|
| Corpus extraction | `sum:rag.audit.extraction_alerts{*}.as_count() > 0` over 5m | High |
| Canary triggered | `sum:rag.audit.canary_triggers{*}.as_count() > 0` over 5m | Critical |
| ACL mapping fail | logs `@rag.kind:acl_mapping_failed` count > 0 | High |
| Permission drift critical | logs `@rag.kind:permission_drift` `@findings.label:critical` | High |

## Push mode

Set `RAG_AUDIT_WEBHOOK_URL` to the Datadog logs intake URL and pass the API key in `RAG_AUDIT_WEBHOOK_HEADERS` (see `deploy/siem/README.md`).
