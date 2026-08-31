# Day-1 SOC onboarding (Lab 3 — SIEM pack)

**Audience:** SOC engineer + RAG Protection operator  
**Time:** ~15 minutes push mode · ~30 minutes with Splunk saved-search import

## Talk track (5 minutes)

1. **Problem:** RAG guardrail decisions already land in `audit.py` — SOC needs them in Splunk/Datadog with stable fields and starter detections.
2. **What we ship:** `deploy/siem/` — field guide, 14 detections (incl. extraction + canary pair), dashboards, runbook. **No proxy code changes.**
3. **Push vs pull:** Set `RAG_AUDIT_WEBHOOK_URL` + `RAG_AUDIT_WEBHOOK_HEADERS` (HEC token) for push; or forward `RAG_AUDIT_FILE` / `GET /admin/audit/export` for pull.
4. **Validate:** `bash tools/siem_onboard.sh` posts sample NDJSON; confirm index + sourcetype `rag_protection:audit`.
5. **Triage:** Use [SOC_RUNBOOK.md](../../../docs/SOC_RUNBOOK.md) — critical pair: **RAG-Canary-Triggered** + **RAG-Corpus-Extraction** → **RAG-Exfil-HighConfidence**.

## Onboarding checklist

| Step | Action | Done when |
|------|--------|-----------|
| 1 | Read [SIEM_FIELD_GUIDE.md](../../../docs/SIEM_FIELD_GUIDE.md) | Field stability promise understood |
| 2 | Configure HEC URL + token on proxy | `RAG_AUDIT_WEBHOOK_*` set |
| 3 | Run `bash tools/siem_onboard.sh` | Sample events accepted (HTTP 200) |
| 4 | Import `splunk/props.conf` + `detections.spl` | Saved searches return hits on sample |
| 5 | Import `splunk/dashboard.xml` or Datadog JSON | Panels mirror product audit stats |
| 6 | Walk [SOC_RUNBOOK.md](../../../docs/SOC_RUNBOOK.md) with analyst | L1 knows first action per alert |

## HEC environment (Splunk)

```bash
export RAG_AUDIT_WEBHOOK_URL="https://<splunk>:8088/services/collector/event"
export RAG_AUDIT_WEBHOOK_HEADERS='{"Authorization":"Splunk <HEC_TOKEN>"}'
bash tools/siem_onboard.sh
```

Dry-run (no network):

```bash
bash tools/siem_onboard.sh --dry-run
```

Datadog path:

```bash
bash tools/siem_onboard.sh --datadog
```

## Boundary

- **Not a SIEM** — packaging + professional services for customer-specific index/onboarding.
- **Single-source** — RAG Protection audit events only; no cross-product correlation in the pack.

**Commercial packaging:** [lab3-siem/ONBOARDING.md](../../../ENTERPRISE.md) · **Tutorial:** [Tutorial 09 Part C](../../../docs/ce/README.md#part-c-siem-pack-onboarding-lab-3-5)
