#!/usr/bin/env bash
# Shared helpers for Docker Compose scripts.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${RAG_ENV_FILE:-${REPO_ROOT}/.env}"
ENV_EXAMPLE="${REPO_ROOT}/.env.example"
DEFAULT_BASE_URL="http://localhost:${RAG_PORT:-8090}"

COMPOSE_FILES=()
MCP_TOOLS_ENABLED=0
EE_ENABLED=0
QDRANT_ENABLED=0
PINECONE_ENABLED=0
HA_DEMO_ENABLED=0

configure_compose_defaults() {
  COMPOSE_FILES=("${RAG_COMPOSE_FILE:-${REPO_ROOT}/compose.yml}")
  MCP_TOOLS_ENABLED=0
  EE_ENABLED=0
}

configure_compose_mcp_tools() {
  COMPOSE_FILES=("${REPO_ROOT}/compose.yml" "${REPO_ROOT}/compose.mcp-tools.yml")
  MCP_TOOLS_ENABLED=1
  EE_ENABLED=0
}

configure_compose_ee() {
  COMPOSE_FILES=("${REPO_ROOT}/compose.yml" "${REPO_ROOT}/compose.ee.yml")
  MCP_TOOLS_ENABLED=1
  EE_ENABLED=1
}

configure_compose_ha_demo() {
  COMPOSE_FILES=("${REPO_ROOT}/compose.yml" "${REPO_ROOT}/compose.ha-demo.yml")
  MCP_TOOLS_ENABLED=0
  EE_ENABLED=0
  HA_DEMO_ENABLED=1
  QDRANT_ENABLED=1
}

configure_compose_ha_demo_ee() {
  COMPOSE_FILES=(
    "${REPO_ROOT}/compose.yml"
    "${REPO_ROOT}/compose.ee.yml"
    "${REPO_ROOT}/compose.ha-demo.yml"
    "${REPO_ROOT}/compose.ha-demo.ee.yml"
  )
  MCP_TOOLS_ENABLED=0
  EE_ENABLED=1
  HA_DEMO_ENABLED=1
  QDRANT_ENABLED=1
}

enable_qdrant_profile() {
  QDRANT_ENABLED=1
}

# Deprecated alias — prefer enable_qdrant_profile / --qdrant.
enable_vector_profile() {
  enable_qdrant_profile
}

enable_pinecone_profile() {
  PINECONE_ENABLED=1
}

# Qdrant is profile-gated; enable it when the store backend needs a vector DB.
# Note: RAG_STORE_BACKEND=vector|hybrid names the *retrieval mode*, not the container.
maybe_enable_qdrant_from_env() {
  case "${RAG_STORE_BACKEND:-sqlite}" in
    vector|hybrid)
      QDRANT_ENABLED=1
      ;;
  esac
}

# Deprecated alias.
maybe_enable_vector_from_env() {
  maybe_enable_qdrant_from_env
}

ensure_ee_checkout() {
  local ee_dir="${RAG_EE_ROOT:-${REPO_ROOT}/rag-protection-enterprise}"
  if [[ ! -d "${ee_dir}/rag_protection_enterprise" ]]; then
    echo "ERROR: EE not found at ${ee_dir} — clone rag-protection-enterprise or set RAG_EE_ROOT" >&2
    exit 1
  fi
}

configure_compose_defaults

compose() {
  local args=()
  local file
  local profile
  local raw_profiles=""
  local seen="|"

  for file in "${COMPOSE_FILES[@]}"; do
    args+=(-f "${file}")
  done

  # Compose CLI --profile replaces COMPOSE_PROFILES (observed on Compose v5),
  # so always re-emit env profiles as --profile flags when merging script profiles.
  raw_profiles="${COMPOSE_PROFILES:-}"
  if [[ ${MCP_TOOLS_ENABLED} -eq 1 ]]; then
    raw_profiles="${raw_profiles:+${raw_profiles},}mcp-tools"
  fi
  if [[ ${QDRANT_ENABLED} -eq 1 ]]; then
    raw_profiles="${raw_profiles:+${raw_profiles},}qdrant"
  fi
  if [[ ${PINECONE_ENABLED} -eq 1 ]]; then
    raw_profiles="${raw_profiles:+${raw_profiles},}pinecone"
  fi

  if [[ -n "${raw_profiles}" ]]; then
    # shellcheck disable=SC2086
    # Intentionally word-split on commas (bash 3.2–safe; no mapfile/readarray).
    IFS=',' 
    for profile in ${raw_profiles}; do
      # trim whitespace
      profile="${profile#"${profile%%[![:space:]]*}"}"
      profile="${profile%"${profile##*[![:space:]]}"}"
      [[ -z "${profile}" ]] && continue
      # Legacy compose profile name → qdrant
      if [[ "${profile}" == "vector" ]]; then
        profile="qdrant"
      fi
      case "${seen}" in
        *"|${profile}|"*) continue ;;
      esac
      seen="${seen}${profile}|"
      args+=(--profile "${profile}")
    done
    unset IFS
  fi

  docker compose "${args[@]}" "$@"
}

print_model_runner_hint() {
  echo >&2
  echo "compose.yml needs Docker Desktop 4.40+ with Model Runner:" >&2
  echo "  Settings → AI → Enable Docker Model Runner" >&2
  echo "  https://docs.docker.com/ai/model-runner/" >&2
  echo "Without Desktop: docker compose -f compose.ci.yml up -d --build --wait" >&2
  echo "  and set RAG_LLM_BASE_URL in .env (see README)." >&2
}

# Fail fast before a long image build when the Model plugin is missing.
preflight_compose_config() {
  local log rc=0
  log="$(mktemp)"
  set +e
  compose config >"${log}" 2>&1
  rc=$?
  set -e
  if [[ ${rc} -ne 0 ]]; then
    cat "${log}" >&2
    if grep -qi "models" "${log}"; then
      print_model_runner_hint
    fi
    rm -f "${log}"
    exit 1
  fi
  rm -f "${log}"
}

ensure_env_file() {
  if [[ -f "${ENV_FILE}" ]]; then
    return 0
  fi
  if [[ ! -f "${ENV_EXAMPLE}" ]]; then
    echo "ERROR: Missing ${ENV_FILE} and ${ENV_EXAMPLE}." >&2
    exit 1
  fi
  cp "${ENV_EXAMPLE}" "${ENV_FILE}"
  echo "Created ${ENV_FILE} from .env.example"
}

load_env() {
  ensure_env_file
  # shellcheck disable=SC1090
  set -a
  source "${ENV_FILE}"
  set +a
}

wait_for_health() {
  local base_url="${1:-${DEFAULT_BASE_URL}}"
  local max_attempts="${2:-30}"
  local attempt=1

  echo "Waiting for ${base_url}/health ..."
  while [[ ${attempt} -le ${max_attempts} ]]; do
    if curl -sf "${base_url}/health" | grep -q healthy; then
      echo "Service is healthy."
      return 0
    fi
    sleep 2
    attempt=$((attempt + 1))
  done

  echo "ERROR: Service did not become healthy within $((max_attempts * 2))s." >&2
  compose ps || true
  if [[ ${HA_DEMO_ENABLED} -eq 1 ]]; then
    compose logs --tail=40 rag-protection-lb rag-protection-proxy-a rag-protection-proxy-b || true
  else
    compose logs --tail=40 rag-protection-proxy || true
  fi
  if [[ ${MCP_TOOLS_ENABLED} -eq 1 ]]; then
    compose logs --tail=40 mcp-filesystem || true
  fi
  exit 1
}

print_endpoints() {
  local base_url="${1:-${DEFAULT_BASE_URL}}"
  local layer_note="Layer 1 (mock tool backends)"

  if [[ ${EE_ENABLED} -eq 1 && ${MCP_TOOLS_ENABLED} -eq 1 ]]; then
    layer_note="Enterprise Edition + Layer 2 (MCP filesystem backend on internal network)"
  elif [[ ${MCP_TOOLS_ENABLED} -eq 1 ]]; then
    layer_note="Layer 2 (MCP filesystem backend on internal network)"
  elif [[ ${EE_ENABLED} -eq 1 ]]; then
    layer_note="Enterprise Edition"
  fi

  local extras_note=""
  if [[ ${QDRANT_ENABLED} -eq 1 ]]; then
    extras_note="${extras_note}
  Qdrant (CE store backend):            http://localhost:${RAG_QDRANT_PORT:-6333}  (dashboard /collections)
"
  fi
  if [[ ${HA_DEMO_ENABLED} -eq 1 ]]; then
    extras_note="${extras_note}
  Two-proxy demo (nginx → a/b, shared Qdrant). Not E4.2 HA.
    bash tools/docker_ha_demo_smoke.sh
    bash tools/docker_ha_demo_failover.sh
    LAN clients: http://<this-host-ip>:${RAG_PORT:-8090}/health
"
  fi
  if [[ ${PINECONE_ENABLED} -eq 1 ]]; then
    extras_note="${extras_note}
  Pinecone Local (Pattern C examples):  http://localhost:${RAG_PINECONE_PORT:-5081}  (API only — no browser UI)
    python examples/langchain/byo_pinecone_ingest.py
    # hr-memo-1 is NOT in Documents & Ingest — fetch via API (see COMPOSE_OVERLAYS)
"
  fi

  cat <<EOF

RAG Protection Proxy is running — ${layer_note}.

  Health:   ${base_url}/health
  UI:       ${base_url}/ui
  Metrics:  ${base_url}/metrics
  Query:    POST ${base_url}/v1/query
  Tools:    GET  ${base_url}/v1/tools
  Invoke:   POST ${base_url}/v1/tools/invoke
${extras_note}
Demo tokens (Authorization: Bearer ...):
  employee-demo-token
  hr-demo-token
  exec-demo-token

Smoke test:
  bash tools/smoke_rag_proxy.sh

First /v1/query can take ~1 minute (Model Runner cold start). /health does not wait for the model.

EOF
}
