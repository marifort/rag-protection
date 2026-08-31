#!/usr/bin/env bash
# Create or repair the repo-root Python virtualenv (Community Edition).
#
# Requires Python 3.11+. CI and the CE Docker image use 3.13.
# Override the interpreter used to *create* a new venv:
#   PYTHON=python3.13 bash tools/setup_venv.sh
# Recreate from scratch:
#   rm -rf .venv && bash tools/setup_venv.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROXY="${ROOT}/rag-protection-proxy"
VENV="${ROOT}/.venv"
LEGACY_VENV="${PROXY}/.venv"
PYTHON="${PYTHON:-python3}"
REQ="${PROXY}/requirements.txt"
REQ_DEV="${PROXY}/requirements-dev.txt"
REQ_EXAMPLES="${ROOT}/examples/requirements.txt"

if [[ ! -f "${REQ}" || ! -f "${REQ_DEV}" ]]; then
  echo "error: expected ${REQ} and ${REQ_DEV} (run from a full CE checkout)." >&2
  exit 1
fi

if [[ -d "${LEGACY_VENV}" ]]; then
  echo "==> Removing legacy virtualenv at ${LEGACY_VENV} (use repo-root .venv)"
  rm -rf "${LEGACY_VENV}"
fi

python_at_least_311() {
  local bin="$1"
  "${bin}" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'
}

python_version_string() {
  local bin="$1"
  "${bin}" -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])'
}

if ! command -v "${PYTHON}" >/dev/null 2>&1 && [[ ! -x "${PYTHON}" ]]; then
  echo "error: '${PYTHON}' not found. Install Python 3.11+ (CI and Docker use 3.13)." >&2
  echo "hint: PYTHON=python3.13 bash tools/setup_venv.sh" >&2
  exit 1
fi

if ! python_at_least_311 "${PYTHON}"; then
  echo "error: Python 3.11+ required (package requires-python). Tried: ${PYTHON}" >&2
  "${PYTHON}" --version >&2 || true
  echo "hint: PYTHON=python3.13 bash tools/setup_venv.sh" >&2
  echo "      CI and the CE image use 3.13; 3.13 is the recommended local version." >&2
  exit 1
fi

venv_is_broken() {
  [[ ! -x "${VENV}/bin/python" ]] && return 0
  # A venv copied or moved from another directory keeps the original absolute
  # paths in its activate script and resolves the wrong interpreter.
  if [[ -f "${VENV}/bin/activate" ]] && ! grep -qF "${VENV}" "${VENV}/bin/activate"; then
    return 0
  fi
  if ! python_at_least_311 "${VENV}/bin/python"; then
    return 0
  fi
  return 1
}

if [[ -d "${VENV}" ]] && venv_is_broken; then
  echo "==> Removing broken or too-old virtualenv at ${VENV}"
  rm -rf "${VENV}"
fi

if [[ ! -d "${VENV}" ]]; then
  echo "==> Creating virtualenv at ${VENV}"
  echo "    interpreter: ${PYTHON} ($(python_version_string "${PYTHON}"))"
  "${PYTHON}" -m venv "${VENV}"
else
  echo "==> Reusing ${VENV} ($(python_version_string "${VENV}/bin/python"))"
  echo "    recreate with another interpreter: rm -rf .venv && PYTHON=python3.13 bash tools/setup_venv.sh"
fi

PY="${VENV}/bin/python"
echo "==> Installing CE dependencies with ${PY} ($(python_version_string "${PY}"))"
"${PY}" -m pip install --upgrade pip
"${PY}" -m pip install -r "${REQ}" -r "${REQ_DEV}"
if [[ -f "${REQ_EXAMPLES}" ]]; then
  echo "==> Installing examples dependencies"
  "${PY}" -m pip install -r "${REQ_EXAMPLES}"
fi
if "${PY}" -c 'import pathlib, rag_protection_proxy, sys
root = pathlib.Path(sys.argv[1]).resolve()
here = pathlib.Path(rag_protection_proxy.__file__).resolve()
raise SystemExit(0 if str(here).startswith(str(root)) else 1)
' "${PROXY}" 2>/dev/null; then
  echo "==> rag-protection-proxy already importable from ${PROXY}"
else
  echo "==> Editable install rag-protection-proxy"
  "${PY}" -m pip install -e "${PROXY}"
fi

echo "==> Done."
echo "    Python:    $(python_version_string "${PY}")  (${PY})"
echo "    Runtime:   rag-protection-proxy/requirements.txt"
echo "    Dev:       rag-protection-proxy/requirements-dev.txt"
if [[ -f "${REQ_EXAMPLES}" ]]; then
  echo "    Examples:  examples/requirements.txt"
fi
echo "    Editable:  rag-protection-proxy  (do not pip install rag-protection-enterprise)"
echo "    Activate:  source ${VENV}/bin/activate"
echo "    Tests:     bash tools/run_tests.sh -q -m \"not live\""
echo "    Docs:      docs/ce/guide/LOCAL_SETUP.md"
