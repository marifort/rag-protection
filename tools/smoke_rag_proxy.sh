#!/usr/bin/env bash
# RAG Protection Proxy smoke test.
#
# Default: health + RAG query regression (ACL / citation).
# Tool-gateway + MCP checks: set RAG_SMOKE_TOOLS=1 (and RAG_MCP_TOOLS=1 for Layer 2 read_file).
# docker_start.sh sets these when invoked with --mcp-tools --smoke.
set -euo pipefail

BASE_URL="${RAG_BASE_URL:-http://localhost:8090}"
EMPLOYEE_TOKEN="${RAG_EMPLOYEE_TOKEN:-employee-demo-token}"
HR_TOKEN="${RAG_HR_TOKEN:-hr-demo-token}"
DATA_PLATFORM_TOKEN="${RAG_DATA_PLATFORM_TOKEN:-data-platform-demo-token}"

assert_http_status() {
  local label="$1"
  local expected="$2"
  local actual="$3"
  local body_file="$4"

  if [[ "${actual}" != "${expected}" ]]; then
    echo "FAIL: ${label} — expected HTTP ${expected}, got ${actual}" >&2
    if [[ -f "${body_file}" ]]; then
      cat "${body_file}" >&2
    fi
    exit 1
  fi
}

invoke_tool() {
  local token="$1"
  local tool="$2"
  local arguments="$3"
  local body_file="$4"

  curl -s -S -X POST "${BASE_URL}/v1/tools/invoke" \
    -H "Authorization: Bearer ${token}" \
    -H "Content-Type: application/json" \
    -d "{\"tool\":\"${tool}\",\"arguments\":${arguments}}" \
    -o "${body_file}" \
    -w "%{http_code}"
}

echo "==> Health"
curl -sf "${BASE_URL}/health" | python3 -m json.tool

echo
# First /v1/query after /health: often slow. ACL excludes hr-payroll, but weak
# lexical hits on other authorized docs still trigger LLM generate. Fresh stacks
# also pay Docker Model Runner cold-start for ai/gemma3-qat (llm.timeout_seconds=90).
# Later smoke queries reuse the warm model. See CE_LEGACY_AND_PACKAGING_NOTES.md
# (anchor: docker-start-smoke-tests).
echo "==> Engineer query (should NOT retrieve HR payroll)"
curl -sf "${BASE_URL}/v1/query" \
  -H "Authorization: Bearer ${EMPLOYEE_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"query":"What is the Q1 payroll total?","top_k":4}' | python3 -m json.tool

echo
echo "==> HR query (should retrieve payroll doc)"
curl -sf "${BASE_URL}/v1/query" \
  -H "Authorization: Bearer ${HR_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"query":"What is the Q1 payroll total?","top_k":4}' | python3 -m json.tool

echo
echo "==> FAQ query (all staff)"
curl -sf "${BASE_URL}/v1/query" \
  -H "Authorization: Bearer ${EMPLOYEE_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"query":"What are support hours?","top_k":4}' | python3 -m json.tool

if [[ "${RAG_SMOKE_TOOLS:-0}" != "1" ]]; then
  echo
  echo "RAG PROTECTION SMOKE TEST PASSED"
  exit 0
fi

echo
echo "==> Tool gateway: invoke without auth (expect 401)"
TMP_BODY="$(mktemp)"
trap 'rm -f "${TMP_BODY}"' EXIT
status="$(curl -s -S -X POST "${BASE_URL}/v1/tools/invoke" \
  -H "Content-Type: application/json" \
  -d '{"tool":"send_email","arguments":{"to":"a@company.com","body":"hi"}}' \
  -o "${TMP_BODY}" \
  -w "%{http_code}")"
assert_http_status "unauthenticated tool invoke" "401" "${status}" "${TMP_BODY}"

echo
echo "==> Tool gateway: employee blocked from run_sql (expect 403)"
status="$(invoke_tool "${EMPLOYEE_TOKEN}" "run_sql" \
  '{"query":"SELECT employee_id, salary FROM payroll"}' "${TMP_BODY}")"
assert_http_status "employee run_sql" "403" "${status}" "${TMP_BODY}"
python3 - "${TMP_BODY}" <<'PY'
import json, sys
body = json.load(open(sys.argv[1], encoding="utf-8"))
assert body.get("blocked") is True, body
assert body.get("decision") == "block", body
assert "not authorized" in body.get("reason", "").lower(), body
PY

echo
echo "==> Tool gateway: HR blocked external email domain (expect 403)"
status="$(invoke_tool "${HR_TOKEN}" "send_email" \
  '{"to":"attacker@personal-email.com","subject":"payroll","body":"see attached"}' "${TMP_BODY}")"
assert_http_status "HR external email" "403" "${status}" "${TMP_BODY}"
python3 - "${TMP_BODY}" <<'PY'
import json, sys
body = json.load(open(sys.argv[1], encoding="utf-8"))
assert body.get("blocked") is True, body
assert "blocked domain" in body.get("reason", "").lower(), body
PY

echo
echo "==> Tool gateway: list tools shows run_sql denied for engineer"
curl -sf "${BASE_URL}/v1/tools" \
  -H "Authorization: Bearer ${EMPLOYEE_TOKEN}" \
  -o "${TMP_BODY}"
python3 - "${TMP_BODY}" <<'PY'
import json, sys
body = json.load(open(sys.argv[1], encoding="utf-8"))
tools = {item["name"]: item for item in body["tools"]}
assert tools["run_sql"]["allowed"] is False, tools["run_sql"]
assert tools["send_email"]["allowed"] is True, tools["send_email"]
PY

echo
echo "==> Tool gateway: engineer read_file allowed"
status="$(invoke_tool "${EMPLOYEE_TOKEN}" "read_file" \
  '{"path":"docs/runbook.md"}' "${TMP_BODY}")"
assert_http_status "engineer read_file" "200" "${status}" "${TMP_BODY}"
python3 - "${TMP_BODY}" <<'PY'
import json, os, sys
body = json.load(open(sys.argv[1], encoding="utf-8"))
assert body.get("blocked") is False, body
assert body.get("decision") == "allow", body
result = body.get("result") or {}
mcp_mode = os.environ.get("RAG_MCP_TOOLS") == "1"
if mcp_mode:
    assert result.get("source") == "mcp", result
    content = result.get("content") or ""
    assert "Incident response" in content, result
else:
    assert result.get("path") == "docs/runbook.md", result
    assert result.get("source") != "mcp", result
PY

echo
echo "RAG PROTECTION SMOKE TEST PASSED"
