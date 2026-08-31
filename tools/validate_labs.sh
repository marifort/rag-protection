#!/usr/bin/env bash
# Single parent validation script for every IMPLEMENTED competency lab,
# competitive moat (#8–#11), and additional opportunity (A-item).
# Runs each shipped test suite and prints one aggregated pass/fail summary.
#
# CE proxy suites (rag-protection-proxy/tests/):
#   #7           MCP tool gateway (MVP)      -> test_tools_gateway.py + test_mcp_shim.py
#   #5           SIEM pack (deploy + tests)  -> test_siem_pack.py
#   #2           extraction monitor          -> test_extraction.py
#   #3           canary documents            -> test_canary.py
#   Moat #8      citation hard gate          -> test_e3.py (hard gate tests)
#   Moat #9      audit integrity chain       -> test_audit_integrity.py
#   Moat #11     retrieval explainability    -> test_retrieval_trace.py
#   T0.6 / #18   LLM egress routing          -> test_llm_routing.py
#
# CE tools (tools/*/tests):
#   #6           rag-scan                    -> tools/rag_scan/tests
#   #19          rag-ground                  -> tools/rag_ground/tests
#   #27          mcp-lint                    -> tools/mcp_lint/tests
#   #20          rag-score                   -> tools/rag_score/tests
#   #23          rag-injbench                -> tools/inj_bench/tests
#   #29          acl-backfill                -> tools/acl_backfill/tests
#   #10          rag-redteam                 -> tools/redteam/tests/test_harness.py
#
# EE (rag-protection-enterprise/tests/ — skipped when package not checked out):
#   #4           permission drift            -> test_drift.py
#   #17/#14/#23–#26 packs / digest          -> test_dlp_packs.py, test_evidence_pack.py, etc.
#   P1 #12–#14   ACL sync, tool registry     -> test_acl_sync.py, test_tool_registry.py
#
# Usage:
#   bash tools/validate_labs.sh            # run everything
#   bash tools/validate_labs.sh -k siem    # forward extra args to every pytest suite
#                                          # (suites with no matching tests show SKIP)
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROXY="${ROOT}/rag-protection-proxy"
VENV="${ROOT}/.venv"

if [[ ! -x "${VENV}/bin/python" ]]; then
  echo "==> No venv found; bootstrapping via setup_venv.sh"
  bash "${ROOT}/tools/setup_venv.sh"
fi
PY="${VENV}/bin/python"
echo "==> Using ${PY} ($("${PY}" --version 2>&1))"

echo "==> Ensuring test dependencies are installed"
"${PY}" -m pip install -q -r "${PROXY}/requirements.txt" -r "${PROXY}/requirements-dev.txt"

EXTRA_ARGS=("$@")

declare -a NAMES=()
declare -a RESULTS=()
overall=0

has_kw_filter() {
  local arg
  for arg in "${EXTRA_ARGS[@]}"; do
    [[ "${arg}" == -k || "${arg}" == -k=* ]] && return 0
  done
  return 1
}

run_suite() {
  local name="$1"; local workdir="$2"; shift 2
  local rc=0
  echo ""
  echo "=============================================================="
  echo "==> ${name}"
  echo "=============================================================="
  if ( cd "${workdir}" && "${PY}" -m pytest "$@" ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"} ); then
    rc=0
  else
    rc=$?
  fi
  if [[ "${rc}" -eq 0 ]]; then
    NAMES+=("${name}"); RESULTS+=("PASS")
  elif [[ "${rc}" -eq 5 ]] && has_kw_filter; then
    # pytest exit 5 = no tests collected / all deselected by -k filter
    NAMES+=("${name}"); RESULTS+=("SKIP (filtered)")
  else
    NAMES+=("${name}"); RESULTS+=("FAIL"); overall=1
  fi
}

run_suite_if_exists() {
  local name="$1"
  local workdir="$2"
  shift 2
  local first="$1"
  if [[ ! -e "${workdir}/${first}" ]]; then
    NAMES+=("${name}"); RESULTS+=("SKIP (not installed)")
    return 0
  fi
  run_suite "${name}" "${workdir}" "$@"
}

# --- CE tools ---
run_suite "#6         rag-scan (config scanner)"   "${ROOT}" tools/rag_scan/tests -q
run_suite "#19        rag-ground (grounding)"      "${ROOT}" tools/rag_ground/tests -q
run_suite "#27        mcp-lint (manifest linter)"  "${ROOT}" tools/mcp_lint/tests -q
run_suite "#20        rag-score (posture card)"    "${ROOT}" tools/rag_score/tests -q
run_suite "#23        rag-injbench (inj benchmark)" "${ROOT}" tools/inj_bench/tests -q
run_suite "#29        acl-backfill (ACL migration)"  "${ROOT}" tools/acl_backfill/tests -q
run_suite "#10        rag-redteam (red-team harness)" "${ROOT}" tools/redteam/tests/test_harness.py -q
run_suite "#7         MCP tool gateway (MVP)"      "${PROXY}" tests/test_tools_gateway.py tests/test_tools_challenge_queue.py tests/test_mcp_shim.py -q -m "not live"

# --- CE proxy: labs 3, 9, 10 + competitive moats #8, #9, #11 ---
run_suite "#5         SIEM pack (CE)"              "${PROXY}" tests/test_siem_pack.py -q
run_suite "#2         extraction monitor (CE)"     "${PROXY}" tests/test_extraction.py -q
run_suite "#3         canary documents (CE)"       "${PROXY}" tests/test_canary.py -q
run_suite "Moat #8    citation hard gate (CE)"     "${PROXY}" \
  tests/test_e3.py::test_hard_citation_gate_blocks_unsupported_substantive_claim \
  tests/test_e3.py::test_hard_citation_gate_allows_fully_grounded_answer \
  tests/test_e3.py::test_per_claim_citations_return_chunk_ids -q
run_suite "Moat #9    audit integrity chain (CE)"  "${PROXY}" tests/test_audit_integrity.py -q
run_suite "Moat #11   retrieval explainability (CE)" "${PROXY}" tests/test_retrieval_trace.py -q
run_suite "#18        LLM egress routing (CE)"       "${PROXY}" tests/test_llm_routing.py -q

EE="${ROOT}/rag-protection-enterprise"

# --- EE items (present only when the private enterprise package is checked out) ---
run_suite_if_exists "#4         permission drift (EE)" "${EE}" tests/test_drift.py -q
run_suite_if_exists "#17        DLP compliance packs (EE)" "${EE}" tests/test_dlp_packs.py -q
run_suite_if_exists "#17/#22    entitlements + baselines (EE)" "${EE}" tests/test_entitlements.py tests/test_baselines.py -q
run_suite_if_exists "#23        EE injection corpus (EE)" "${EE}" tests/test_inj_corpus.py -q
run_suite_if_exists "#21        egress / SSRF packs (EE)" "${EE}" tests/test_egress_packs.py -q
run_suite_if_exists "#26        weekly security digest (EE)" "${EE}" tests/test_security_digest.py -q
run_suite_if_exists "P1 #12     ACL sync v2 (EE)" "${EE}" tests/test_acl_sync.py -q
run_suite_if_exists "P1 #13     tool registry SKU (EE)" "${EE}" tests/test_tool_registry.py -q
run_suite_if_exists "P1 #14     evidence pack (EE)" "${EE}" tests/test_evidence_pack.py -q

echo ""
echo "=============================================================="
echo "  VALIDATION SUMMARY (labs, moats & A-items)"
echo "=============================================================="
for i in "${!NAMES[@]}"; do
  printf "  [%s]  %s\n" "${RESULTS[$i]}" "${NAMES[$i]}"
done
echo "--------------------------------------------------------------"
if [[ "${overall}" -eq 0 ]]; then
  echo "  ALL SUITES PASSED"
else
  echo "  ONE OR MORE SUITES FAILED"
fi
echo "=============================================================="

exit "${overall}"
