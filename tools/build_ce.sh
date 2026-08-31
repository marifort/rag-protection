#!/usr/bin/env bash
# Full Community Edition (CE) build.
#
# Produces everything needed to serve the MIT CE stack:
#   - (optional) editable install of the rag-protection-proxy Python package
#   - React console bundle (console-core + console-ce)
#       → rag-protection-proxy/rag_protection_proxy/ui/static/ce/
#
# The EE bundle is built separately: tools/build_ee.sh
# Docs: docs/product/CE_EE_BUILD_RUN_DEBUG.md
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

CE_PROXY="${RAG_CE_ROOT:-${REPO_ROOT}/rag-protection-proxy}"
CONSOLE_DIR="${REPO_ROOT}/console"
CE_OUT="${CE_PROXY}/rag_protection_proxy/ui/static/ce"

INSTALL=0
TYPECHECK=0
TEST=0
CLEAN=0
USE_CI=0

print_usage() {
  cat <<'USAGE'
Usage:
  bash tools/build_ce.sh [options]

Builds the CE React console (core + CE app) into
rag-protection-proxy/rag_protection_proxy/ui/static/ce/.

Options:
  --install     Also `pip install -e rag-protection-proxy[dev]` (Python backend)
  --typecheck   Run `npm run typecheck` before building
  --test        Run `npm run test` (Vitest) after building
  --clean       Remove node_modules before installing deps
  --ci          Use `npm ci` (clean, lockfile-exact install) instead of `npm install`
  -h, --help    Show this help

Examples:
  bash tools/build_ce.sh                    # build UI only
  bash tools/build_ce.sh --install          # backend + UI (fresh machine)
  bash tools/build_ce.sh --ci --typecheck   # CI-style build
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --install) INSTALL=1; shift ;;
    --typecheck) TYPECHECK=1; shift ;;
    --test) TEST=1; shift ;;
    --clean) CLEAN=1; shift ;;
    --ci) USE_CI=1; shift ;;
    -h|--help) print_usage; exit 0 ;;
    *) echo "ERROR: Unknown option '$1'." >&2; print_usage; exit 1 ;;
  esac
done

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "ERROR: required command '$1' not found in PATH." >&2
    exit 1
  }
}

require_cmd npm
require_cmd node

if [[ ! -d "${CONSOLE_DIR}" ]]; then
  echo "ERROR: console directory not found at ${CONSOLE_DIR}." >&2
  exit 1
fi

if [[ ${INSTALL} -eq 1 ]]; then
  require_cmd pip
  echo "==> Installing CE proxy package (editable) from ${CE_PROXY} ..."
  pip install -e "${CE_PROXY}[dev]"
fi

cd "${CONSOLE_DIR}"

if [[ ${CLEAN} -eq 1 ]]; then
  echo "==> Cleaning node_modules ..."
  rm -rf node_modules packages/*/node_modules
fi

if [[ ${USE_CI} -eq 1 && -f package-lock.json ]]; then
  echo "==> npm ci ..."
  npm ci
else
  echo "==> npm install ..."
  npm install
fi

if [[ ${TYPECHECK} -eq 1 ]]; then
  echo "==> Typechecking (core + CE) ..."
  npm run typecheck
fi

echo "==> Building console (core library + CE app) ..."
npm run build

if [[ ${TEST} -eq 1 ]]; then
  echo "==> Running tests (Vitest) ..."
  npm run test
fi

echo ""
echo "CE build complete."
echo "  Output: ${CE_OUT}/"
echo "  Serve:  start the proxy, then open http://localhost:8090/ui"
