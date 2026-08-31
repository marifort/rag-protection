#!/usr/bin/env bash
# Lab 3 — SIEM HEC onboarding helper (P0).
# Validates push-mode wiring: sample events → Splunk HEC (or generic webhook).
#
# Usage:
#   export RAG_AUDIT_WEBHOOK_URL="https://splunk:8088/services/collector/event"
#   export RAG_AUDIT_WEBHOOK_HEADERS='{"Authorization":"Splunk <HEC_TOKEN>"}'
#   bash tools/siem_onboard.sh
#
# Optional:
#   HEC_TOKEN=... bash tools/siem_onboard.sh --dry-run
#   bash tools/siem_onboard.sh --datadog   # prints Datadog intake checklist
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SAMPLE="${ROOT}/deploy/siem/samples/audit_sample.jsonl"
DETECTIONS="${ROOT}/deploy/siem/splunk/detections.spl"

DRY_RUN=0
MODE="splunk"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --datadog) MODE="datadog"; shift ;;
    -h|--help)
      sed -n '2,12p' "$0"
      exit 0
      ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done

if [[ ! -f "${SAMPLE}" ]]; then
  echo "ERROR: missing ${SAMPLE}" >&2
  exit 1
fi

echo "==> SIEM pack artifacts"
echo "    Field guide:  docs/SIEM_FIELD_GUIDE.md"
echo "    Runbook:      docs/SOC_RUNBOOK.md"
echo "    Detections:   deploy/siem/splunk/detections.spl"
echo "    Sample lines: deploy/siem/samples/audit_sample.jsonl ($(wc -l < "${SAMPLE}" | tr -d ' ') events)"

if [[ "${MODE}" == "datadog" ]]; then
  echo ""
  echo "==> Datadog onboarding checklist"
  echo "  1. Import deploy/siem/datadog/log_pipeline.json"
  echo "  2. Create log-based metrics from deploy/siem/datadog/metrics.md"
  echo "  3. Import deploy/siem/datadog/dashboard.json"
  echo "  4. Set RAG_AUDIT_WEBHOOK_URL to your Datadog log intake URL"
  exit 0
fi

URL="${RAG_AUDIT_WEBHOOK_URL:-}"
if [[ -z "${URL}" && ${DRY_RUN} -eq 0 ]]; then
  echo ""
  echo "WARN: RAG_AUDIT_WEBHOOK_URL not set — pull mode only."
  echo "      Forward RAG_AUDIT_FILE or schedule GET /admin/audit/export"
  exit 0
fi

AUTH_HEADER=""
if [[ -n "${RAG_AUDIT_WEBHOOK_HEADERS:-}" ]]; then
  AUTH_HEADER="$(python3 -c "import json,os; print(json.loads(os.environ['RAG_AUDIT_WEBHOOK_HEADERS']).get('Authorization',''))")"
fi
if [[ -z "${AUTH_HEADER}" && -n "${HEC_TOKEN:-}" ]]; then
  AUTH_HEADER="Splunk ${HEC_TOKEN}"
fi

echo ""
echo "==> Push test → ${URL:-dry-run (no URL)}"
sent=0
failed=0
while IFS= read -r line; do
  [[ -z "${line}" ]] && continue
  payload=$(printf '{"event": %s, "sourcetype": "rag_protection:audit"}' "${line}")
  if [[ ${DRY_RUN} -eq 1 ]]; then
    echo "DRY-RUN would POST: ${line:0:80}..."
    sent=$((sent + 1))
    continue
  fi
  args=(-sS -k -X POST "${URL}" -H "Content-Type: application/json" -d "${payload}")
  if [[ -n "${AUTH_HEADER}" ]]; then
    args+=(-H "Authorization: ${AUTH_HEADER}")
  fi
  if curl "${args[@]}" >/dev/null 2>&1; then
    sent=$((sent + 1))
  else
    failed=$((failed + 1))
    echo "FAIL: could not POST event kind=$(echo "${line}" | python3 -c "import json,sys; print(json.load(sys.stdin).get('kind','?'))")" >&2
  fi
done < "${SAMPLE}"

echo "==> HEC push complete: ${sent} sent, ${failed} failed"
if [[ ${failed} -gt 0 ]]; then
  exit 1
fi

echo ""
echo "==> Next steps (SOC)"
echo "  1. Import deploy/siem/splunk/props.conf sourcetype rag_protection:audit"
echo "  2. Install detections from deploy/siem/splunk/detections.spl"
echo "  3. Import deploy/siem/splunk/dashboard.xml"
echo "  4. Run: pytest rag-protection-proxy/tests/test_siem_pack.py -q"
