#!/usr/bin/env bash
# Configure a Community Edition checkout: .env, Python venv, React console.
#
# Does not install OS packages (see tools/ce/install_host_deps.sh) and does not
# start Docker (see tools/docker_start.sh).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
CHECK_ONLY=0
WITH_HOST_DEPS=0
SKIP_VENV=0
SKIP_CONSOLE=0
SKIP_ENV=0
MIN_NODE_MAJOR=20

die() { echo "ERROR: $*" >&2; exit 1; }
log() { echo "==> $*"; }

print_usage() {
  cat <<'USAGE'
Usage:
  bash tools/ce/bootstrap.sh [options]

Prepare this CE checkout after Git/Node/Python are installed:

  1. Copy .env.example → .env when .env is missing
  2. Create or repair repo-root .venv (tools/setup_venv.sh)
  3. Build the operator console (tools/build_ce.sh --ci)

Options:
  --check           Verify Git, Node 20+, npm, Python 3.11+; do not write files
  --with-host-deps  Run tools/ce/install_host_deps.sh --apply first
  --skip-venv       Do not create .venv
  --skip-console    Do not run npm / build_ce.sh
  --skip-env        Do not copy .env
  -h, --help        Show this help

Env:
  PYTHON   Interpreter for setup_venv.sh (default: python3.13, then 3.12/3.11/python3)
USAGE
}

python_ok() {
  local bin="$1"
  command -v "${bin}" >/dev/null 2>&1 || [[ -x "${bin}" ]] || return 1
  "${bin}" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null
}

pick_python() {
  if [[ -n "${PYTHON:-}" ]]; then
    python_ok "${PYTHON}" && { echo "${PYTHON}"; return 0; }
    die "PYTHON=${PYTHON} is missing or older than 3.11"
  fi
  local c
  for c in python3.13 python3.12 python3.11 python3; do
    if python_ok "${c}"; then
      echo "${c}"
      return 0
    fi
  done
  return 1
}

node_ok() {
  command -v node >/dev/null 2>&1 || return 1
  command -v npm >/dev/null 2>&1 || return 1
  local major
  major="$(node -p "parseInt(process.versions.node.split('.')[0], 10)")" || return 1
  [[ "${major}" -ge "${MIN_NODE_MAJOR}" ]]
}

print_tool_status() {
  echo "Git:     $(command -v git >/dev/null && git --version || echo 'MISSING')"
  if node_ok; then
    echo "Node:    $(node -v)  npm $(npm -v)"
  else
    echo "Node:    MISSING or older than v${MIN_NODE_MAJOR}"
  fi
  local py
  if py="$(pick_python 2>/dev/null)"; then
    echo "Python:  $("${py}" --version 2>&1)  (${py})"
  else
    echo "Python:  MISSING or older than 3.11"
  fi
}

check_prereqs() {
  local failed=0
  if ! command -v git >/dev/null 2>&1; then
    echo "ERROR: git is not on PATH." >&2
    failed=1
  fi
  if ! node_ok; then
    echo "ERROR: Node.js ${MIN_NODE_MAJOR}+ and npm are required (CI uses Node 20)." >&2
    echo "       Install: bash tools/ce/install_host_deps.sh --apply" >&2
    failed=1
  fi
  if ! pick_python >/dev/null 2>&1; then
    echo "ERROR: Python 3.11+ is required (CI and the CE image use 3.13)." >&2
    echo "       Install: bash tools/ce/install_host_deps.sh --apply" >&2
    failed=1
  fi
  [[ "${failed}" -eq 0 ]] || exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check) CHECK_ONLY=1; shift ;;
    --with-host-deps) WITH_HOST_DEPS=1; shift ;;
    --skip-venv) SKIP_VENV=1; shift ;;
    --skip-console) SKIP_CONSOLE=1; shift ;;
    --skip-env) SKIP_ENV=1; shift ;;
    -h|--help) print_usage; exit 0 ;;
    *) die "unknown option: $1 (try --help)" ;;
  esac
done

cd "${REPO_ROOT}"
[[ -d rag-protection-proxy && -f tools/setup_venv.sh ]] || die "run from a CE checkout (missing rag-protection-proxy/ or tools/setup_venv.sh)"

if [[ "${WITH_HOST_DEPS}" -eq 1 ]]; then
  log "Host packages"
  bash "${SCRIPT_DIR}/install_host_deps.sh" --apply
fi

echo "Community Edition bootstrap"
echo "Repo: ${REPO_ROOT}"
print_tool_status
echo

if [[ "${CHECK_ONLY}" -eq 1 ]]; then
  check_prereqs
  log "Prerequisites OK"
  if command -v docker >/dev/null 2>&1; then
    docker --version
  else
    echo "Note: docker not on PATH — needed for bash tools/docker_start.sh"
  fi
  exit 0
fi

check_prereqs

if [[ "${SKIP_ENV}" -eq 0 ]]; then
  if [[ -f .env ]]; then
    log ".env already exists (not overwritten)"
  else
    [[ -f .env.example ]] || die "missing .env.example"
    log "Copy .env.example → .env"
    cp .env.example .env
  fi
fi

if [[ "${SKIP_VENV}" -eq 0 ]]; then
  PY="$(pick_python)"
  log "Python venv with ${PY}"
  PYTHON="${PY}" bash "${REPO_ROOT}/tools/setup_venv.sh"
fi

if [[ "${SKIP_CONSOLE}" -eq 0 ]]; then
  log "React console"
  if [[ -f "${REPO_ROOT}/console/package-lock.json" ]]; then
    bash "${REPO_ROOT}/tools/build_ce.sh" --ci
  else
    bash "${REPO_ROOT}/tools/build_ce.sh"
  fi
fi

echo
log "Checkout ready."
echo "    Config:   .env"
[[ "${SKIP_VENV}" -eq 0 ]] && echo "    Venv:     source ${REPO_ROOT}/.venv/bin/activate"
[[ "${SKIP_CONSOLE}" -eq 0 ]] && echo "    Console:  rag-protection-proxy/rag_protection_proxy/ui/static/ce/"
echo "    Start:    bash tools/docker_start.sh --smoke"
echo "    Host API: source .venv/bin/activate && cd rag-protection-proxy && python -m rag_protection_proxy"
echo "    Docs:     docs/ce/guide/LOCAL_SETUP.md"
