#!/usr/bin/env bash
# Stop the RAG Protection Proxy stack.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=docker_common.sh
source "${SCRIPT_DIR}/docker_common.sh"

REMOVE_VOLUMES=0
MCP_TOOLS=0
EE=0
QDRANT=0
PINECONE=0

print_usage() {
  cat <<'USAGE'
Usage:
  bash tools/docker_stop.sh [options]

Options:
  --ee          Stop EE stack (compose.ee.yml + MCP via include + mcp-tools profile)
  --mcp-tools   Stop Layer 2 stack (compose.mcp-tools.yml + mcp-tools profile)
  --qdrant      Include Qdrant (compose profile qdrant); also auto-enabled when
                RAG_STORE_BACKEND is vector or hybrid
  --vector      Deprecated alias for --qdrant
  --pinecone    Include Pinecone Local (compose profile pinecone)
  --volumes     Remove persistent rag-data volume
  -h, --help    Show this help

Examples:
  bash tools/docker_stop.sh
  bash tools/docker_stop.sh --ee
  bash tools/docker_stop.sh --ee --qdrant
  bash tools/docker_stop.sh --pinecone
  bash tools/docker_stop.sh --ee --qdrant --pinecone   # clear both local vector sidecars
  bash tools/docker_stop.sh --mcp-tools
  bash tools/docker_stop.sh --volumes
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
    --volumes)
      REMOVE_VOLUMES=1
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

cd "${REPO_ROOT}"
load_env
maybe_enable_qdrant_from_env
if [[ ${QDRANT} -eq 1 ]]; then
  enable_qdrant_profile
fi
if [[ ${PINECONE} -eq 1 ]]; then
  enable_pinecone_profile
fi

if [[ ${REMOVE_VOLUMES} -eq 1 ]]; then
  compose down -v --remove-orphans
  echo "Stack stopped and volumes removed."
else
  compose down --remove-orphans
  echo "Stack stopped (volumes preserved)."
fi
