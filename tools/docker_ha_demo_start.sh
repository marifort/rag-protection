#!/usr/bin/env bash
# Start the Docker two-proxy demo (nginx + proxy-a/b + Qdrant). No Kubernetes.
#
# Same honesty bar as Helm --ha-demo: shared Qdrant, no audit JSONL, per-replica
# /data. Not E4.2 HA.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=docker_common.sh
source "${SCRIPT_DIR}/docker_common.sh"

BUILD=1
EE=0

print_usage() {
  cat <<'USAGE'
Usage:
  bash tools/docker_ha_demo_start.sh [options]

Two proxy containers behind nginx on ${RAG_PORT:-8090}. Windows/Linux LAN
clients use http://<this-host-ip>:8090 (open the firewall). Not E4.2 HA.

Stop the single-replica Compose stack first if it already owns 8090:
  bash tools/docker_stop.sh --qdrant
  bash tools/docker_stop.sh --ee --qdrant   # if that stack is EE

Options:
  --ee         EE image (compose.ee.yml + compose.ha-demo.ee.yml)
  --no-build   Use the existing rag-protection-proxy image
  -h, --help

Then:
  bash tools/docker_ha_demo_smoke.sh
  bash tools/docker_ha_demo_failover.sh
  bash tools/docker_ha_demo_stop.sh          # add --ee if you started with --ee
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ee)
      EE=1
      shift
      ;;
    --no-build)
      BUILD=0
      shift
      ;;
    -h|--help)
      print_usage
      exit 0
      ;;
    *)
      echo "ERROR: Unknown option '$1'." >&2
      print_usage >&2
      exit 1
      ;;
  esac
done

cd "${REPO_ROOT}"
if [[ "${EE}" -eq 1 ]]; then
  ensure_ee_checkout
  configure_compose_ha_demo_ee
else
  configure_compose_ha_demo
fi
load_env
enable_qdrant_profile

BASE_URL="http://localhost:${RAG_PORT:-8090}"

if lsof -nP -iTCP:"${RAG_PORT:-8090}" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "NOTE: host port ${RAG_PORT:-8090} is already in use. Stop Compose, Helm port-forward, or set RAG_PORT." >&2
fi

if [[ "${BUILD}" -eq 1 ]]; then
  echo "Building rag-protection-proxy ..."
  compose build rag-protection-proxy
fi

echo "Starting two-proxy demo (nginx + a/b + Qdrant) ..."
compose up -d --remove-orphans qdrant rag-protection-proxy-a rag-protection-proxy-b rag-protection-lb

wait_for_health "${BASE_URL}" 45
print_endpoints "${BASE_URL}"
echo "Smoke both proxies (not the load balancer):  bash tools/docker_ha_demo_smoke.sh"
echo "Failover demo:                               bash tools/docker_ha_demo_failover.sh"
