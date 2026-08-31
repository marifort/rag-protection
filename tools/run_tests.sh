#!/usr/bin/env bash
# Run pytest with repo .venv (creates/repairs venv + installs deps if needed).
#
# CE-only CI: Tier 2 integration tests skip via @ee_required (~13 tests).
# CE/EE boundary: pytest -q tests/test_ce_ee_seams.py (always runs).
# Full Tier 2 coverage: bash tools/dev_install_ee.sh first.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROXY="${ROOT}/rag-protection-proxy"
VENV="${ROOT}/.venv"

venv_is_broken() {
  [[ ! -x "${VENV}/bin/python" ]] && return 0
  # A venv copied or moved from another directory keeps the original absolute
  # paths in its activate script and resolves the wrong interpreter.
  if [[ -f "${VENV}/bin/activate" ]] && ! grep -qF "${VENV}" "${VENV}/bin/activate"; then
    return 0
  fi
  return 1
}

if [[ ! -d "${VENV}" ]] || venv_is_broken; then
  bash "$(dirname "$0")/setup_venv.sh"
fi

PY="${VENV}/bin/python"
echo "==> Using ${PY}"
"${PY}" -m pip install -q -r "${PROXY}/requirements.txt" -r "${PROXY}/requirements-dev.txt"

cd "${PROXY}"
exec "${PY}" -m pytest "$@"
