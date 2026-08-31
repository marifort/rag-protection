#!/usr/bin/env bash
# Stop the Docker two-proxy demo started by docker_ha_demo_start.sh.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=docker_common.sh
source "${SCRIPT_DIR}/docker_common.sh"

EE=0
REMOVE_VOLUMES=0

print_usage() {
  cat <<'USAGE'
Usage:
  bash tools/docker_ha_demo_stop.sh [--ee] [--volumes]

Match --ee to how you started. CE is the default (no --ee).
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ee)
      EE=1
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
      print_usage >&2
      exit 1
      ;;
  esac
done

cd "${REPO_ROOT}"
if [[ "${EE}" -eq 1 ]]; then
  configure_compose_ha_demo_ee
else
  configure_compose_ha_demo
fi
load_env
enable_qdrant_profile

if [[ "${REMOVE_VOLUMES}" -eq 1 ]]; then
  compose down -v --remove-orphans
  echo "Two-proxy demo stopped; volumes removed."
else
  compose down --remove-orphans
  echo "Two-proxy demo stopped (volumes preserved)."
fi
