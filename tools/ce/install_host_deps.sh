#!/usr/bin/env bash
# Install or print host packages required to clone, build, and test CE.
#
# Installs Git, Node.js 20+, and Python 3.11+ when missing.
# Does **not** install Docker Desktop (GUI app + Model Runner). See the README.
#
# Default is dry-run (prints commands). Pass --apply to run them.
set -euo pipefail

# Homebrew (`$PWD must be set`) and relative script paths fail if this
# terminal is sitting in a folder that was deleted (getcwd ENOENT).
if ! pwd >/dev/null 2>&1; then
  echo "==> This terminal's folder no longer exists; switching to \$HOME" >&2
  cd "${HOME}"
  export PWD
fi
if [[ "${BASH_SOURCE[0]}" != /* && ! -e "${BASH_SOURCE[0]}" ]]; then
  echo "ERROR: this terminal's directory was deleted, so a relative script path will not work." >&2
  echo "       Run:  cd ~" >&2
  echo "       Then: cd /path/to/rag-protection && bash tools/ce/install_host_deps.sh" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
APPLY=0
MIN_NODE_MAJOR=20
MIN_PY="3.11"

die() { echo "ERROR: $*" >&2; exit 1; }
log() { echo "==> $*"; }

print_usage() {
  cat <<'USAGE'
Usage:
  bash tools/ce/install_host_deps.sh [options]

Host packages for Community Edition: Git, Node.js 20+, Python 3.11+.
Does not install Docker Desktop.

Options:
  --apply     Run installs (Homebrew on macOS; apt on Debian/Ubuntu).
              Without this flag, print the commands only.
  -h, --help  Show this help

Env:
  PYTHON      Preferred Python binary to look for (default: python3.13, then 3.12/3.11/python3)
USAGE
}

run_root() {
  if [[ "$(id -u)" -eq 0 ]]; then
    "$@"
  else
    command -v sudo >/dev/null 2>&1 || die "need root or sudo to install apt packages"
    sudo "$@"
  fi
}

node_major() {
  command -v node >/dev/null 2>&1 || return 1
  node -p "parseInt(process.versions.node.split('.')[0], 10)" 2>/dev/null || return 1
}

node_ok() {
  local major
  major="$(node_major)" || return 1
  [[ "${major}" -ge "${MIN_NODE_MAJOR}" ]]
}

python_ok() {
  local bin="$1"
  command -v "${bin}" >/dev/null 2>&1 || [[ -x "${bin}" ]] || return 1
  "${bin}" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null
}

pick_python() {
  if [[ -n "${PYTHON:-}" ]]; then
    python_ok "${PYTHON}" && echo "${PYTHON}" && return 0
    return 1
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

report_status() {
  echo "Git:     $(command -v git >/dev/null && git --version || echo 'MISSING')"
  if node_ok; then
    echo "Node:    $(node -v)  (npm $(npm -v 2>/dev/null || echo '?'))"
  else
    echo "Node:    MISSING or older than v${MIN_NODE_MAJOR}  ($(command -v node >/dev/null && node -v || echo 'not on PATH'))"
  fi
  local py
  if py="$(pick_python)"; then
    echo "Python:  $("${py}" -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])')  (${py})"
  else
    echo "Python:  MISSING or older than ${MIN_PY}"
  fi
  echo "Docker:  $(command -v docker >/dev/null && docker --version || echo 'not on PATH — install Docker Desktop for the default Compose path')"
}

print_macos() {
  cat <<'EOS'
# macOS (Homebrew) — Git, Node 20+, Python 3.13
# cd ~ first: brew refuses to run if this terminal's folder was deleted.
cd ~
brew install git node python@3.13

# Docker Desktop is a separate GUI app (Model Runner lives there):
#   brew install --cask docker
#   open -a Docker
# then Settings → AI → Enable Docker Model Runner.
EOS
}

print_debian() {
  cat <<'EOS'
# Ubuntu / Debian / WSL — Git, Python 3, Node 20 (NodeSource; distro nodejs is often too old)
sudo apt-get update
sudo apt-get install -y git python3 python3-venv python3-pip curl ca-certificates gnupg
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
  | sudo gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg
echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" \
  | sudo tee /etc/apt/sources.list.d/nodesource.list
sudo apt-get update
sudo apt-get install -y nodejs

# Docker Desktop (Model Runner) or Docker Engine (compose.ci.yml only):
#   https://docs.docker.com/desktop/   or   https://docs.docker.com/engine/install/
EOS
}

apply_macos() {
  command -v brew >/dev/null 2>&1 || die "Homebrew not found. Install from https://brew.sh then re-run."
  # brew requires a real PWD; do not run it from a deleted clone directory.
  cd "${HOME}"
  export PWD
  local pkg
  for pkg in git node python@3.13; do
    if brew list --formula "${pkg}" >/dev/null 2>&1; then
      log "Homebrew already has ${pkg}"
    else
      log "brew install ${pkg}"
      brew install "${pkg}"
    fi
  done
}

apply_debian() {
  log "apt-get update + Git / Python"
  run_root apt-get update
  run_root apt-get install -y git python3 python3-venv python3-pip curl ca-certificates gnupg
  if node_ok; then
    log "Node $(node -v) already satisfies v${MIN_NODE_MAJOR}+"
    return 0
  fi
  log "Install Node.js ${MIN_NODE_MAJOR}.x from NodeSource"
  run_root mkdir -p /etc/apt/keyrings
  curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
    | run_root gpg --batch --yes --dearmor -o /etc/apt/keyrings/nodesource.gpg
  echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" \
    | run_root tee /etc/apt/sources.list.d/nodesource.list >/dev/null
  run_root apt-get update
  run_root apt-get install -y nodejs
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --apply) APPLY=1; shift ;;
    -h|--help) print_usage; exit 0 ;;
    *) die "unknown option: $1 (try --help)" ;;
  esac
done

echo "Community Edition host packages"
echo "Repo: ${REPO_ROOT}"
report_status
echo

os="$(uname -s)"
case "${os}" in
  Darwin)
    if [[ "${APPLY}" -eq 0 ]]; then
      print_macos
      echo
      echo "Dry-run. Pass --apply to brew-install missing formulae (not Docker)."
      exit 0
    fi
    apply_macos
    ;;
  Linux)
    if [[ -r /etc/os-release ]]; then
      # shellcheck disable=SC1091
      . /etc/os-release
    fi
    case "${ID:-}:${ID_LIKE:-}" in
      debian:*|ubuntu:*|*:debian*|*:ubuntu*)
        if [[ "${APPLY}" -eq 0 ]]; then
          print_debian
          echo
          echo "Dry-run. Pass --apply to apt-install missing packages (not Docker)."
          exit 0
        fi
        apply_debian
        ;;
      *)
        echo "No automatic installer for ${ID:-${os}}."
        echo "Need: git, Node.js ${MIN_NODE_MAJOR}+, Python ${MIN_PY}+ (3.13 preferred)."
        [[ "${APPLY}" -eq 1 ]] && die "cannot --apply on this distro"
        exit 0
        ;;
    esac
    ;;
  *)
    echo "Native ${os} is not supported. Use macOS, Linux, or Windows WSL2."
    [[ "${APPLY}" -eq 1 ]] && exit 1
    exit 0
    ;;
esac

echo
log "After install"
report_status
if ! command -v git >/dev/null || ! node_ok || ! pick_python >/dev/null; then
  die "Git, Node v${MIN_NODE_MAJOR}+, or Python ${MIN_PY}+ still missing. Open a new shell if PATH changed."
fi
log "Next: bash tools/ce/bootstrap.sh"
echo "Docker Desktop is still required for compose.yml + Model Runner (not installed by this script)."
