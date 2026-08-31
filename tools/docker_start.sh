#!/usr/bin/env bash
# Build (optional) and start the RAG Protection Proxy stack.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=docker_common.sh
source "${SCRIPT_DIR}/docker_common.sh"

BUILD=1
NO_CACHE=0
PULL=0
SKIP_HEALTH=0
RUN_SMOKE=0
DETACH=1
MCP_TOOLS=0
EE=0
QDRANT=0
PINECONE=0

print_usage() {
  cat <<'USAGE'
Usage:
  bash tools/docker_start.sh [options]

Builds Docker images and starts the compose stack. Does NOT run npm or
build_ce.sh — build the React console on the host first when needed:
  bash tools/build_ce.sh          # CE /ui
  bash tools/build_ee.sh          # EE ee-ui.js (before --ee)

Options:
  --ee            Enterprise stack (compose.ee.yml + MCP via include + mcp-tools profile)
  --mcp-tools     Start Layer 2 stack (compose.mcp-tools.yml + mcp-tools profile)
  --qdrant        Start Qdrant (compose profile qdrant); also auto-enabled when
                  RAG_STORE_BACKEND is vector or hybrid (retrieval mode — not the flag name).
                  With vector|hybrid in .env, plain docker_start.sh starts Qdrant even
                  without --qdrant or --pinecone; --pinecone does not cancel that.
  --vector        Deprecated alias for --qdrant
  --pinecone      Start Pinecone Local index emulator (compose profile pinecone)
                  for Pattern C LangChain examples — not a CE store backend.
                  Does not stop or prevent Qdrant if RAG_STORE_BACKEND=vector|hybrid.  --no-build      Start without rebuilding the image
  --no-cache      Rebuild without Docker layer cache (implies --build)
  --pull          Pull newer base images before build
  --foreground    Run in foreground (docker compose up without -d)
  --skip-health   Do not wait for /health
  --smoke         Run tools/smoke_rag_proxy.sh after startup (RAG checks only)
  -h, --help      Show this help

Examples:
  bash tools/docker_start.sh
  bash tools/docker_start.sh --ee --smoke           # EE + MCP Layer 2
  bash tools/docker_start.sh --ee --qdrant --smoke  # EE + Qdrant hybrid/vector store
  bash tools/docker_start.sh --pinecone             # Pattern C Pinecone Local (sqlite/default store)
  bash tools/docker_start.sh --no-build
  bash tools/docker_start.sh --smoke
  bash tools/docker_start.sh --mcp-tools --smoke    # CE + tool gateway + MCP read_file smoke
  bash tools/docker_start.sh --no-cache --smoke

Switch Qdrant ↔ Pinecone Local (Compose leaves the other container up otherwise):
  bash tools/docker_stop.sh --ee --qdrant --pinecone
  # then either:
  bash tools/docker_start.sh --ee --qdrant --smoke     # CE/EE retrieval via Qdrant
  bash tools/docker_start.sh --ee --pinecone --smoke   # Pattern C examples (set RAG_STORE_BACKEND=sqlite)
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ee)
      EE=1
      shift
      ;;
    --mcp-tools)
      MCP_TOOLS=1
      shift
      ;;
    --qdrant)
      QDRANT=1
      shift
      ;;
    --vector)
      echo "NOTE: --vector is deprecated; use --qdrant (same compose profile)." >&2
      QDRANT=1
      shift
      ;;
    --pinecone)
      PINECONE=1
      shift
      ;;
    --no-build)
      BUILD=0
      shift
      ;;
    --no-cache)
      NO_CACHE=1
      BUILD=1
      shift
      ;;
    --pull)
      BUILD=1
      PULL=1
      shift
      ;;
    --foreground)
      DETACH=0
      shift
      ;;
    --skip-health)
      SKIP_HEALTH=1
      shift
      ;;
    --smoke)
      RUN_SMOKE=1
      shift
      ;;
    -h|--help)
      print_usage
      exit 0
      ;;
    *)
      echo "ERROR: Unknown option '$1'." >&2
      print_usage
      exit 1
      ;;
  esac
done

if [[ ${EE} -eq 1 ]]; then
  configure_compose_ee
elif [[ ${MCP_TOOLS} -eq 1 ]]; then
  configure_compose_mcp_tools
fi

PULL="${PULL:-0}"

cd "${REPO_ROOT}"
if [[ ${EE} -eq 1 ]]; then
  ensure_ee_checkout
fi
load_env
maybe_enable_qdrant_from_env
if [[ ${QDRANT} -eq 1 ]]; then
  enable_qdrant_profile
fi
if [[ ${PINECONE} -eq 1 ]]; then
  enable_pinecone_profile
fi

preflight_compose_config

BASE_URL="http://localhost:${RAG_PORT:-8090}"

if [[ ${BUILD} -eq 1 ]]; then
  build_args=(build rag-protection-proxy)
  if [[ ${NO_CACHE} -eq 1 ]]; then
    build_args+=(--no-cache)
  fi
  if [[ ${PULL} -eq 1 ]]; then
    build_args+=(--pull)
  fi
  echo "Building rag-protection-proxy ..."
  compose "${build_args[@]}"
  if [[ ${MCP_TOOLS} -eq 1 || ${EE} -eq 1 ]]; then
    build_args=(build mcp-filesystem)
    if [[ ${NO_CACHE} -eq 1 ]]; then
      build_args+=(--no-cache)
    fi
    if [[ ${PULL} -eq 1 ]]; then
      build_args+=(--pull)
    fi
    echo "Building mcp-filesystem ..."
    compose "${build_args[@]}"
  fi
fi

up_args=(up)
if [[ ${DETACH} -eq 1 ]]; then
  up_args+=(-d)
fi
up_args+=(--remove-orphans)

if [[ ${EE} -eq 1 ]]; then
  echo "Starting EE stack (enterprise proxy + MCP filesystem backend) ..."
elif [[ ${MCP_TOOLS} -eq 1 ]]; then
  echo "Starting Layer 2 stack (MCP filesystem backend) ..."
elif [[ ${PINECONE} -eq 1 && ${QDRANT} -eq 1 ]]; then
  echo "Starting stack (proxy + Qdrant + Pinecone Local) ..."
elif [[ ${PINECONE} -eq 1 ]]; then
  echo "Starting stack (proxy + Pinecone Local for Pattern C examples) ..."
elif [[ ${QDRANT} -eq 1 ]]; then
  echo "Starting stack (proxy + Qdrant) ..."
else
  echo "Starting stack ..."
fi
compose "${up_args[@]}"

if [[ ${DETACH} -eq 1 && ${SKIP_HEALTH} -eq 0 ]]; then
  wait_for_health "${BASE_URL}"
  print_endpoints "${BASE_URL}"
fi

if [[ ${RUN_SMOKE} -eq 1 ]]; then
  export RAG_BASE_URL="${BASE_URL}"
  if [[ ${MCP_TOOLS} -eq 1 || ${EE} -eq 1 ]]; then
    export RAG_SMOKE_TOOLS=1
    export RAG_MCP_TOOLS=1
  fi
  bash "${REPO_ROOT}/tools/smoke_rag_proxy.sh"
fi

if [[ ${DETACH} -eq 0 ]]; then
  echo "Running in foreground. Press Ctrl+C to stop."
fi
