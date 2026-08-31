# #5 — SIEM pack + prebuilt detections

> **Which doc?** **Card** (this page) = behavior / policy · **Demo** = show it · **Learn** = teach it · **Lab** = GTM depth
>
> [Demo](../demos/05-siem-pack.md) · [Learn](../learn/01-core-moats.md#5-siem-pack--prebuilt-detections) · [Lab](../../../ENTERPRISE.md) · [Tutorial](../tutorials/09-implemented-features-walkthrough.md#part-c-siem-pack-onboarding-lab-3-5)

| Field | Value |
|-------|-------|
| **Edition** | Pack (CE deploy artifact) |
| **Status** | Shipped |
| **Legacy alias** | Lab 3 |
| **Runtime code** | None — uses existing `audit.py` pipeline |
| **Tests** | `tests/test_siem_pack.py` |

**Demo:** [../demos/05-siem-pack.md](../demos/05-siem-pack.md) · **Tutorial:** [T09 §C](../tutorials/09-implemented-features-walkthrough.md#part-c-siem-pack-onboarding-lab-3-5)

---

## What & why

POCs die in **SOC review**: *"Great demo — how does this alert Splunk?"*

The runtime already emits structured audit events (JSONL, webhook, export). #5 packages **14 prebuilt detections**, dashboards, field guide, and SOC runbook — **no proxy code changes**.

---

## How it works

```text
audit.record(AuditEvent)  ← existing pipeline
  → JSONL file / HEC webhook / export API
  → deploy/siem/ (Splunk + Datadog artifacts)
  → SIEM_FIELD_GUIDE.md + SOC_RUNBOOK.md
```

### Ingestion modes

| Mode | Config |
|------|--------|
| **Push** | `RAG_AUDIT_WEBHOOK_URL` + `RAG_AUDIT_WEBHOOK_HEADERS` (HEC token) |
| **Pull** | Forward `RAG_AUDIT_FILE` or scrape `GET /admin/audit/export` |

### Key detections

| Rule | Audit `kind` |
|------|--------------|
| RAG-Corpus-Extraction | `extraction_suspected` |
| RAG-Canary-Triggered | `canary_triggered` |
| RAG-Exfil-HighConfidence | pair: same subject + hour, extraction + canary |
| RAG-Permission-Drift | `permission_drift` |
| RAG-Tool-Invoke-Block | `tool_invoke` + block |

### Artifacts

| Path | Content |
|------|---------|
| `deploy/siem/splunk/` | `props.conf`, `detections.spl`, dashboards |
| `deploy/siem/datadog/` | Pipelines, monitors |
| `tools/siem_onboard.sh` | HEC validator + sample NDJSON |
| [SIEM_FIELD_GUIDE.md](../../SIEM_FIELD_GUIDE.md) | Stable field contract |
| [SOC_RUNBOOK.md](../../SOC_RUNBOOK.md) | Triage playbooks |

---

## Validate (smoke)

```bash
bash tools/siem_onboard.sh --dry-run
cd rag-protection-proxy && pytest tests/test_siem_pack.py -q
```

Full demo: [../demos/05-siem-pack.md](../demos/05-siem-pack.md).

---

## Gaps & non-claims

| In scope | Out of scope |
|----------|--------------|
| Detections on shipped audit schema | Hosted SIEM / log storage |
| Splunk + Datadog starter pack | Customer-specific index tuning (PS) |
| Onboarding script | New logging engine |

---

## Engineering reference

| Artifact | Path |
|----------|------|
| Full spec | [lab3 SPEC](../../../ENTERPRISE.md) |
| Onboarding | [lab3 ONBOARDING](../../../ENTERPRISE.md) |
| Install | [deploy/siem/README.md](../../../deploy/siem/README.md) |
