# Demo: #5 — SIEM pack + onboarding

**~5 minutes.** Show pack layout, validate with `siem_onboard.sh`, walk one detection + runbook path.

**Feature reference:** [../features/05-siem-pack.md](../features/05-siem-pack.md) · **Tutorial:** [T09 §C](../tutorials/09-implemented-features-walkthrough.md#part-c-siem-pack-onboarding-lab-3-5) · **Onboarding:** [lab3 ONBOARDING](../../../ENTERPRISE.md)

---

## 0. Setup (off camera)

```bash
bash tools/docker_start.sh

# Optional live HEC demo:
export RAG_AUDIT_WEBHOOK_URL="https://<splunk>:8088/services/collector/event"
export RAG_AUDIT_WEBHOOK_HEADERS='{"Authorization":"Splunk <HEC_TOKEN>"}'
```

Have open: `deploy/siem/splunk/detections.spl`, [SIEM_FIELD_GUIDE.md](../../SIEM_FIELD_GUIDE.md), [SOC_RUNBOOK.md](../../SOC_RUNBOOK.md).

---

## 1. Frame (30 sec)

Narrative: *"SOC asks how this alerts Splunk. We ship detections on the audit schema you already emit — no new logging engine."*

```text
runtime → audit.record → JSONL / HEC → deploy/siem/ → SOC_RUNBOOK
```

---

## 2. Pack layout (45 sec)

```bash
ls deploy/siem/splunk/
ls deploy/siem/datadog/
head -20 deploy/siem/onboard/README.md
```

Point out: `props.conf`, 14 SPL rules, dashboard XML, Datadog pipeline JSON.

---

## 3. Validate locally — no network (60 sec)

```bash
bash tools/siem_onboard.sh --dry-run
```

**Expected:** sample NDJSON validates against field guide; HTTP push skipped.

Datadog checklist: `bash tools/siem_onboard.sh --datadog`

---

## 4. Live HEC push (optional, 60 sec)

```bash
bash tools/siem_onboard.sh
```

**Expected:** HTTP 200 from Splunk HEC for sample events.

---

## 5. Pair detection story (90 sec)

Run [#2 extraction demo](../demos/02-extraction-monitor.md) or [#3 canary](../demos/03-canary-docs.md), then show:

- **RAG-Corpus-Extraction** / **RAG-Canary-Triggered** in `detections.spl`
- **RAG-Exfil-HighConfidence** when same `subject` fires both in one hour

Triage: [SOC_RUNBOOK.md](../../SOC_RUNBOOK.md) — first action per alert.

---

## 6. Unit suite (off camera)

```bash
cd rag-protection-proxy && pytest tests/test_siem_pack.py -q
```

---

## Close

SIEM pack is packaging on shipped audit — pairs with every moat that emits new `kind` values (#2, #3, #4, #7, #18, …).
