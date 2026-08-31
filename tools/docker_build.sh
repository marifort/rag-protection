#!/usr/bin/env bash
# Build the RAG Protection Proxy Docker image via Compose.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=docker_common.sh
source "${SCRIPT_DIR}/docker_common.sh"

NO_CACHE=0
PULL=0

print_usage() {
  cat <<'USAGE'
Usage:
  bash tools/docker_build.sh [options]

Options:
  --no-cache    Build without Docker layer cache
  --pull        Pull newer base images before build
  -h, --help    Show this help

Examples:
  bash tools/docker_build.sh
  bash tools/docker_build.sh --no-cache

Builds CE image rag-protection-proxy:latest (INSTALL_EE_WHEEL=0).
See docs/commercial/COMPOSE_OVERLAYS.md § CE-only Docker for contributors.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-cache)
      NO_CACHE=1
      shift
      ;;
    --pull)
      PULL=1
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

cd "${REPO_ROOT}"
ensure_env_file

args=(build rag-protection-proxy)
if [[ ${NO_CACHE} -eq 1 ]]; then
  args+=(--no-cache)
fi
if [[ ${PULL} -eq 1 ]]; then
  args+=(--pull)
fi

echo "Building rag-protection-proxy from ${COMPOSE_FILE} ..."
compose "${args[@]}"
echo "Docker build complete."
