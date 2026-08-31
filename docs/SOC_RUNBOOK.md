# RAG Protection — SOC runbook

**Version:** 1.0 · **Last updated:** 2026-07-09  
**Audience:** SOC L1/L2 analysts  
**Detections:** `deploy/siem/splunk/detections.spl` · **Fields:** [SIEM_FIELD_GUIDE.md](SIEM_FIELD_GUIDE.md)

---

## Quick reference

| Alert | Likely cause | First action | Escalate when |
|-------|--------------|--------------|---------------|
| **RAG-Corpus-Extraction** | Authorized user scraping corpus | Identify `subject`; check `/admin/extraction/watch` or **Audit Log** → `extraction_suspected` ([UI guide](../ENTERPRISE.md)) | `severe` + repeated; pair with canary |
| **RAG-Canary-Triggered** | ACL enforcement failure or scraper hit decoy | **P1** — containment already ran; find `document_id` in `detail` ([UI guide](../ENTERPRISE.md)). Demo/hybrid: a retrieved leftover honeypot also fires — [operator notes](ce/features/03-canary-docs.md#operator-notes-theft-card-hybrid-retrieval-and-missing-retire-rows) | Any production trigger |
| **RAG-Exfil-HighConfidence** | Canary + extraction same hour | Treat as confirmed exfil attempt — also check console **Overview / Audit → Suspected data theft**. Lab false pair: hybrid scrape + leftover honeypot — same operator notes | Immediate IR |
| **RAG-Permission-Drift** | Source ACL changed vs vector metadata | Open drift detail; compare connector job | `critical` label |
| **RAG-ACL-Mapping-Fail** | Unmapped IdP group on ingest | Fix `group_map` in connector config | Any prod tenant |
| **RAG-Inj-Block-UserQuery** | Prompt injection / jailbreak | Review `subject`; check repeat count | Campaign / same user burst |
| **RAG-Tool-Block** | Unauthorized tool call | Review tool policy + subject roles | Privileged tool |
| **RAG-Tool-ExternalEmail** | Blocked email exfil via agent | IR — possible data theft attempt | Always |
| **RAG-DLP-HighVolume** | PII burst in findings | Review subject + time window | HR/PCI labels |
| **RAG-Ingest-Quarantine** | Poisoned/malicious corpus doc | Review quarantine queue in admin UI | Repeated ingest attacks |
| **RAG-Citation-Fail-Spike** | Model/corpus grounding issue | Check LLM health + recent ingest | Customer-facing outage |
| **RAG-Webhook-DeadLetter** | SIEM integration broken | Fix HEC URL/token; replay if needed | Audit gap risk |
| **RAG-Cross-Tenant** | Misconfigured JWT/tenant claim | Platform engineering | Possible data leak |

---

## Triage: RAG-Corpus-Extraction

1. Note `subject`, `tenant_id`, `findings.label` (`elevated` / `severe`).
2. Parse `detail` JSON: `triggered_by`, `trigger_summary`, `coverage`, `breadth_ratio`, `novelty_ratio`, `distinct_documents`, `window_queries`.
3. **If `action=alert` (default):** user was not blocked — decide step-up or account review.
4. **If `action=throttle`/`challenge`:** user received `block_reason=extraction_suspected`.
5. False positives: power users researching broadly — tune `elevated_coverage` / `min_window_queries`.

---

## Triage: RAG-Canary-Triggered

1. **Severity: Critical** — decoy document entered retrieval for a non-auditor subject.
2. Runtime already **scrubbed** the canary from the answer; verify no `canary_token` in downstream logs.
3. Extract `document_id`, `canary_token`, `stage` (`retrieval` vs `output`) from `detail`.
4. Root cause: connector sync bug, group mapping error, or vector ACL bypass — pair with **#4 permission drift** if permissions recently changed.
5. Retire or re-seed canary after fix via `POST /admin/canary/retire` / `seed`. If retire **404s** while hits continue, the decoy may exist only in Qdrant under hybrid — [operator notes](ce/features/03-canary-docs.md#operator-notes-theft-card-hybrid-retrieval-and-missing-retire-rows).

---

## Triage: RAG-Exfil-HighConfidence

Both **canary** and **extraction** fired for the same subject within the correlation window.

1. Open **/ui → Overview** (or **Audit Log**) → **Suspected data theft** — confirm the subject row and **same hour** badge when SIEM-aligned. Curl + UI working sample: [exfil-correlation DEMO_SCRIPT](../ENTERPRISE.md).
2. Click **Open in Audit** / **Filter table** to inspect both kinds for that subject.
3. Open incident ticket; preserve `GET /admin/audit/export?kind=canary_triggered` and `kind=extraction_suspected`.
4. Suspend or throttle subject's access at IdP if policy allows.
5. Review all `query_completed` / `query_trace` for subject in window (enable `audit_debug` only if approved).

On a long-lived **hybrid demo**, this pair can also be leftover reachable honeypots plus breadth from high `top_k` retrieval tests — not a dedicated canary call. Confirm `detail.document_id` still exists in `GET /admin/canary/list`; if 404, check Qdrant. [Operator notes](ce/features/03-canary-docs.md#operator-notes-theft-card-hybrid-retrieval-and-missing-retire-rows).

---

## Triage: injection vs ACL vs drift

| Symptom in logs | Kind / finding | Meaning |
|-----------------|----------------|---------|
| User asked malicious question | `scan_input` + `prompt_injection` | Attack on prompt — not ACL |
| No docs returned | `query_blocked` + empty retrieval detail | Enumeration or over-restrictive ACL |
| Connector can't map group | `acl_mapping_failed` | Config — fail-closed, docs not ingested |
| Permissions changed upstream | `permission_drift` | Living ACL out of sync — fix source or re-sync |

---

## Export for investigations

```bash
curl -s "https://<proxy>/admin/audit/export?kind=extraction_suspected&limit=500" \
  -H "Authorization: Bearer <audit_reader_token>" \
  -o extraction-export.jsonl
```

Use `scrub=false` only when legally approved and policy allows raw previews.

---

## Escalation

| Tier | Team | When |
|------|------|------|
| L2 | App security / platform | Repeated extraction, any canary in prod |
| Engineering | RAG Protection on-call | Webhook dead-letter, cross-tenant |
| IR | Customer SOC / CERT | RAG-Exfil-HighConfidence, tool email block |
