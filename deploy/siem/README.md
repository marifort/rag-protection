# RAG Protection — SIEM pack (Lab 3)

Packaging for Splunk and Datadog on the **shipped** audit pipeline (`audit.py`). No runtime code changes required.

| Artifact | Path |
|----------|------|
| Field guide + stability promise | [docs/SIEM_FIELD_GUIDE.md](../../docs/ce/README.md) |
| SOC triage runbook | [docs/SOC_RUNBOOK.md](../../docs/ce/README.md) |
| Sample NDJSON (all kinds) | [samples/audit_sample.jsonl](samples/audit_sample.jsonl) |
| Splunk sourcetype | [splunk/props.conf](splunk/props.conf) |
| Splunk detections (14 rules) | [splunk/detections.spl](splunk/detections.spl) |
| Splunk dashboard | [splunk/dashboard.xml](splunk/dashboard.xml) |
| Datadog pipeline | [datadog/log_pipeline.json](datadog/log_pipeline.json) |
| Datadog metrics + monitors | [datadog/metrics.md](datadog/metrics.md) |
| Datadog dashboard | [datadog/dashboard.json](datadog/dashboard.json) |

## Detection inventory

| Rule | `kind` / signal |
|------|-----------------|
| RAG-Inj-Block-UserQuery | `scan_input` / injection |
| RAG-ACL-EmptyRetrieval | `query_blocked` |
| RAG-DLP-HighVolume | `findings.scanner=pii` |
| RAG-Ingest-Quarantine | `ingest_completed` + quarantine |
| RAG-ACL-Mapping-Fail | `acl_mapping_failed` |
| RAG-Permission-Drift | `permission_drift` (Lab 4) |
| RAG-Tool-Block | `tool_invoke` |
| RAG-Tool-ExternalEmail | `tool_invoke` + `send_email` |
| RAG-Citation-Fail-Spike | `citation_failed` |
| **RAG-Corpus-Extraction** | **`extraction_suspected`** (Lab 9) |
| **RAG-Canary-Triggered** | **`canary_triggered`** (Lab 10) |
| **RAG-Exfil-HighConfidence** | canary + extraction pair |
| RAG-Cross-Tenant | tenant anomaly |
| RAG-Webhook-DeadLetter | dead-letter file |

## Push mode (Splunk HEC)

```bash
export RAG_AUDIT_WEBHOOK_URL="https://<splunk>:8088/services/collector/event"
export RAG_AUDIT_WEBHOOK_HEADERS='{"Authorization":"Splunk <HEC_TOKEN>"}'
```

Each `audit.record()` POSTs one JSON `AuditEvent` line. Retries + dead-letter are built in (E1.4).

## Pull mode

Forward `RAG_AUDIT_FILE` (JSONL) or schedule `GET /admin/audit/export` with an `audit_reader` token.

## Validate indexing

```bash
# Splunk: one-shot ingest test (adjust index/sourcetype)
cat deploy/siem/samples/audit_sample.jsonl | while read line; do
  curl -k "$RAG_AUDIT_WEBHOOK_URL" -H "Authorization: Splunk $HEC_TOKEN" \
    -d "{\"event\": $line, \"sourcetype\": \"rag_protection:audit\"}"
done

# Or use the onboarding helper (P0):
bash tools/siem_onboard.sh              # live HEC push
bash tools/siem_onboard.sh --dry-run    # validate script + sample file only
```

**Day-1 SOC onboarding:** [onboard/README.md](onboard/README.md) · [lab3-siem/ONBOARDING.md](../../ENTERPRISE.md)

## Tests

```bash
pytest rag-protection-proxy/tests/test_siem_pack.py -q
```
