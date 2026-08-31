# RAG Protection — SIEM field guide

**Version:** 1.0 · **Last updated:** 2026-07-09  
**Audience:** SOC engineers, Splunk/Datadog admins, procurement security review  
**Pack location:** `deploy/siem/` · **Lab spec:** [docs/commercial/labs/lab3-siem/SPEC.md](ce/README.md)

---

## Field-stability promise

Top-level `AuditEvent` fields and `kind` values documented here are **stable across minor releases**. New `kind` values and optional fields may be added; existing fields are not renamed or removed without a major version and migration note. Build detections on:

- `kind`, `decision`, `risk_score`, `subject`, `tenant_id`, `source`, `detail`
- `findings[].scanner`, `findings[].category`, `findings[].severity`, `findings[].label`

`debug` is **opt-in** for webhooks (`audit.debug_webhook: false` by default). Export scrubbing (`audit.scrub_export: true` by default) may redact snippets in `findings` and `detail` on `/admin/audit/export`.

---

## Canonical schema (`models.AuditEvent`)

| Field | Type | SOC use | Example |
|-------|------|---------|---------|
| `timestamp` | float (epoch) | Time index | `1752048000.0` |
| `kind` | string | Event classifier | `extraction_suspected` |
| `decision` | `allow` \| `challenge` \| `block` | Severity input | `block` |
| `risk_score` | float 0–1 | Threshold alerts | `0.9` |
| `source` | string? | Subsystem label | `retrieval.monitor` |
| `subject` | string? | User attribution | `alice.engineer` |
| `tenant_id` | string? | Multi-tenant filter | `default` |
| `findings[]` | array | Scanner hits | see below |
| `detail` | string? | Human summary or JSON blob | `6 docs over 8 queries` |
| `debug` | object? | Forensics (opt-in) | query/chunk previews |

### `findings[]` subfields

| Field | Example |
|-------|---------|
| `scanner` | `extraction`, `canary`, `prompt_injection`, `pii` |
| `category` | `corpus_coverage`, `acl_tripwire`, `injection` |
| `severity` | `0.0`–`1.0` |
| `label` | `severe`, `restricted`, `PCI` |
| `detail` | Free text |

---

## Audit `kind` reference

| `kind` | Emitted by | Detection(s) |
|--------|-----------|--------------|
| `scan_input` | Input guardrails | RAG-Inj-Block-UserQuery |
| `scan_output` | Output guardrails | (extend DLP rules) |
| `query_completed` | Query pipeline summary | Volume / allow rate |
| `query_blocked` | Pipeline blocks | RAG-Inj-Block, RAG-ACL-EmptyRetrieval |
| `query_trace` | Debug query trace | Forensics only |
| `citation_failed` | Citation gate | RAG-Citation-Fail-Spike |
| `retrieval_trace` | Retrieval explainability (#11) | Forensics / ACL tuning |
| `ingest_completed` | Ingest API | RAG-Ingest-Quarantine |
| `connector_sync` | Connector scheduler | Sync health |
| `acl_mapping_failed` | Connector (fail-closed) | RAG-ACL-Mapping-Fail |
| `permission_drift` | Drift monitor (#4) | RAG-Permission-Drift |
| `tool_invoke` | MCP tool gateway (#7) | RAG-Tool-Block, RAG-Tool-ExternalEmail |
| `rate_limited` | EE rate limiter | Volume abuse |
| `extraction_suspected` | Extraction monitor (#2) | **RAG-Corpus-Extraction** |
| `canary_triggered` | Canary tripwire (#3) | **RAG-Canary-Triggered** |
| `ingest_completed` | Ingest | RAG-Ingest-Quarantine |

### Pair signal (high-confidence exfil)

When **`canary_triggered`** and **`extraction_suspected`** appear for the same `subject` within ~1 hour → use **RAG-Exfil-HighConfidence** (see `deploy/siem/splunk/detections.spl`).

---

## Ingestion modes

| Mode | Configuration |
|------|----------------|
| **Push (webhook)** | `RAG_AUDIT_WEBHOOK_URL` + `RAG_AUDIT_WEBHOOK_HEADERS` (Splunk HEC token or Datadog API key) |
| **Pull (file)** | Forward `RAG_AUDIT_FILE` JSONL via customer's log shipper |
| **Pull (API)** | Scheduled `GET /admin/audit/export` (admin RBAC; respect `scrub_export`) |

Retries and dead-letter: `RAG_AUDIT_DEAD_LETTER_FILE` — monitor with **RAG-Webhook-DeadLetter**.

---

## Sample data

`deploy/siem/samples/audit_sample.jsonl` — one line per `kind` for index-time validation and detection dry-runs.

---

## Related docs

| Doc | Purpose |
|-----|---------|
| [SOC_RUNBOOK.md](SOC_RUNBOOK.md) | Alert triage |
| [deploy/siem/README.md](../deploy/siem/README.md) | Install steps |
| [guardrails/P2_PERSISTENT_AUDIT.md](ce/security/P2_PERSISTENT_AUDIT.md) | Runtime audit behavior |
| [compliance/AUDIT_INTEGRITY_AND_EXPORT.md](ce/README.md) | Integrity / export FAQ |
