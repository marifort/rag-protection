# Local setup (Community Edition)

**Audience:** Contributors and evaluators running this tree on a laptop.  
**Goal:** A CE-only Python virtualenv you can activate, test, and run.  
**Canonical pins:** the requirement files listed below — if this page and a file disagree, the file wins.

Docker-only evaluators can skip this page and use the [root README](../../../README.md). Host pytest, `uvicorn`, and editable installs need the venv.

---

## Prerequisites

| Tool | Required | What this repo uses |
|------|----------|---------------------|
| **Python** | **3.11 or newer** | Package marker: `requires-python = ">=3.11"` in [`rag-protection-proxy/pyproject.toml`](../../../rag-protection-proxy/pyproject.toml). **CI and the CE Docker image use 3.13.** Prefer 3.13 locally so wheels match CI. Newer 3.x (for example 3.14) is accepted if `python3 --version` is 3.11+; recreate with 3.13 if pip cannot find wheels. |
| **bash** | Yes for `tools/*.sh` | macOS, Linux, or Windows **WSL** / Git Bash. Native Windows `cmd` is not supported. |
| **Node.js** | 20+ if you rebuild the operator console | CI uses Node **20**. `console/package.json` → `"engines": { "node": ">=20" }`. |
| **Docker Desktop** | Optional for host-only Python; required for default Compose + Model Runner | 4.40+ with [Docker Model Runner](https://docs.docker.com/ai/model-runner/) (**Settings → AI → Enable Docker Model Runner**). Without Desktop, use `compose.ci.yml` + `RAG_LLM_BASE_URL` or host uvicorn below. |

Check the interpreter that `setup_venv.sh` will use:

```bash
python3 --version
```

Expect `3.11`, `3.12`, or `3.13` (or newer). If this prints 3.10 or older, install a newer CPython and point the script at it (see [Pin the interpreter](#pin-the-interpreter)).

---

## Create the virtualenv

Run from the **repository root** (the directory that contains `rag-protection-proxy/` and `tools/setup_venv.sh`):

```bash
bash tools/setup_venv.sh
source .venv/bin/activate
```

The prompt should show `(.venv)`. Confirm:

```bash
which python
python --version
```

`which python` must end with `/.venv/bin/python` (this checkout).

`tools/setup_venv.sh`:

1. Uses `${PYTHON:-python3}` and **refuses** anything older than 3.11.
2. Creates or repairs repo-root **`.venv`** (gitignored). It deletes a leftover `rag-protection-proxy/.venv` if present.
3. Upgrades pip, then installs:
   - [`rag-protection-proxy/requirements.txt`](../../../rag-protection-proxy/requirements.txt) — runtime
   - [`rag-protection-proxy/requirements-dev.txt`](../../../rag-protection-proxy/requirements-dev.txt) — tests (includes examples via `-r`)
   - [`examples/requirements.txt`](../../../examples/requirements.txt) — LangChain / Pinecone samples
4. Editable-installs **`rag-protection-proxy`** (`pip install -e rag-protection-proxy`) if the package is not already importable from this checkout. That matches CE CI.

First run can take several minutes: `sentence-transformers` pulls **PyTorch** and related wheels.

### Pin the interpreter

`setup_venv.sh` only uses `PYTHON` when it **creates** `.venv`. An existing venv keeps its original Python.

```bash
rm -rf .venv
PYTHON=python3.13 bash tools/setup_venv.sh
source .venv/bin/activate
```

Use a full path if `python3.13` is not on `PATH` (`PYTHON=/usr/bin/python3.13`).

### Manual equivalent (same result)

Only needed if you cannot run the script:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r rag-protection-proxy/requirements.txt \
  -r rag-protection-proxy/requirements-dev.txt \
  -r examples/requirements.txt
python -m pip install -e rag-protection-proxy
```

---

## Libraries installed

Minimum versions below match the committed files. Transitive packages (including **torch** via `sentence-transformers`) are not listed.

### Runtime — `rag-protection-proxy/requirements.txt` (also `[project].dependencies`)

| Package | Minimum | Role |
|---------|---------|------|
| `fastapi` | 0.115.0 | HTTP API |
| `uvicorn[standard]` | 0.32.0 | ASGI server |
| `httpx` | 0.27.0 | LLM and outbound HTTP |
| `pyyaml` | 6.0.2 | Policy / ACL YAML |
| `pydantic` | 2.9.0 | Request/response models |
| `PyJWT[crypto]` | 2.9.0 | HS256 demo JWT and OIDC/JWKS |
| `prometheus-client` | 0.21.0 | `/metrics` |
| `qdrant-client` | 1.12.0 | Vector store when `RAG_STORE_BACKEND=vector` or `hybrid` |
| `sentence-transformers` | 3.0.0 | Embeddings for vector/hybrid retrieval |

Default retrieval is **SQLite** (no Qdrant process). The Qdrant and embedding libraries are still installed so you can switch backends without another pip run. The first **vector** query may download `sentence-transformers/all-MiniLM-L6-v2` into `RAG_DATA_DIR`.

### Dev — `rag-protection-proxy/requirements-dev.txt` and `[project.optional-dependencies] dev`

| Package | Minimum | Role |
|---------|---------|------|
| `pytest` | 8.3.0 | Unit / in-process tests |
| `pytest-asyncio` | 0.24.0 | Async tests |
| `httpx` | 0.27.0 | Already a runtime dep; repeated for extras |

`pip install -e "rag-protection-proxy[dev]"` is optional after `setup_venv.sh` (the script already installed the extras plus the editable package).

### Examples — `examples/requirements.txt`

| Package | Constraint | Role |
|---------|------------|------|
| `langchain-core` | ≥ 0.3.0 | Pattern A / C samples only — **not** used by the proxy pipeline |
| `pinecone` | `>=6.0.0,<9` | Optional cloud SDK; local Pattern C demos use HTTP against Pinecone Local |

---

## Keep the environment CE-only

This repository is Community Edition. Do **not**:

- `pip install rag-protection-enterprise` (or any Enterprise wheel)
- Put a private Enterprise checkout on `PYTHONPATH`
- Reuse a virtualenv from a monorepo that already has Enterprise installed

Prove the optional package is absent:

```bash
python - <<'PY'
import importlib.util
assert importlib.util.find_spec("rag_protection_enterprise") is None
import rag_protection_proxy
print("CE-only OK", rag_protection_proxy.__file__)
PY
```

`pip list` should show `rag-protection-proxy` and must **not** show `rag-protection-enterprise`.

---

## Run tests

From the repository root (venv does not need to be activated; the wrapper uses `.venv`):

```bash
bash tools/run_tests.sh -q -m "not live"
```

Live Compose tests need Docker and `RUN_INTEGRATION=1` — see [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md).

---

## Run the proxy on the host

Config paths are relative, so start from `rag-protection-proxy/`:

```bash
source .venv/bin/activate
cd rag-protection-proxy
export RAG_LLM_BASE_URL=http://localhost:12434/engines/v1
export RAG_LLM_MODEL=ai/gemma3-qat
python -m rag_protection_proxy
```

Equivalent:

```bash
uvicorn rag_protection_proxy.app:app --host 0.0.0.0 --port 8090 --reload
```

Open `http://localhost:8090/ui` and `http://localhost:8090/health`. Expect `"enterprise_installed": false`.

Host `RAG_LLM_BASE_URL` must be reachable from your laptop (typically `http://localhost:12434/engines/v1` when Model Runner TCP is enabled). Do not use `model-runner.docker.internal` unless the process is inside Compose.

Any OpenAI-compatible chat endpoint works (`RAG_LLM_BASE_URL`, `RAG_LLM_MODEL`, `RAG_LLM_API_KEY`). Copy [`.env.example`](../README.md) to `.env` for Docker. Host uvicorn reads the `export`s above (and `config/*.yaml`); it does not require `.env` unless you source it yourself.

**Compose without Model Runner:** `compose.yml` needs the Docker Model plugin. If you are on Docker Engine / Colima, start with `docker compose -f compose.ci.yml up -d --build --wait` and set `RAG_LLM_BASE_URL` in `.env`. Inside that container, `localhost` is the proxy — use `host.docker.internal` for an LLM on the host.

---

## Operator console (Node)

The CE image does not run `npm`. Rebuild the UI on the host after `console/` edits:

```bash
cd console
npm ci
cd ..
bash tools/build_ce.sh
```

Output: `rag-protection-proxy/rag_protection_proxy/ui/static/ce/`.

---

## Editors (Cursor / VS Code)

`.venv` is not on `PATH` until you activate it. This repo’s [`.vscode/settings.json`](../README.md) defines a **zsh (.venv)** terminal profile that sources `.venv` for **new** integrated terminals.

1. Command Palette → **Python: Select Interpreter** → `./.venv/bin/python` for **this** folder.
2. Close existing terminal tabs, then open a new terminal (prompt should show `(.venv)`).
3. Or in any shell: `source .venv/bin/activate`.

---

## Recreate

```bash
deactivate 2>/dev/null || true
rm -rf .venv
bash tools/setup_venv.sh
source .venv/bin/activate
```

---

## Troubleshooting

| Symptom | What to do |
|---------|------------|
| `error: Python 3.11+ required` | Install 3.11+ (prefer 3.13) and rerun with `PYTHON=...`. |
| `python3` is 3.9 (old macOS / Xcode) | Install CPython from python.org or Homebrew; do not use the system 3.9. |
| pip fails building `torch` / `sentence-transformers` | Recreate the venv with **3.13** (CI’s version) so wheels resolve. |
| `No module named rag_protection_proxy` | Run `bash tools/setup_venv.sh` again (editable install) or `cd rag-protection-proxy` before pytest/uvicorn. |
| `enterprise_installed: true` on `/health` | That process has Enterprise loaded. Recreate `.venv` and do not install the EE package. If you hit Docker on `:8090`, you may be on an EE image — stop it or use a free port. |
| Tests pass, `:8090` still looks like EE | Host venv and Docker are independent. Rebuild/start the **CE** Compose stack or run uvicorn from this venv. |
| Integrated terminal has no `(.venv)` | Activate manually; pick the interpreter; open a **new** terminal. |
| `uvicorn` cannot find `config/policy.yaml` | `cd rag-protection-proxy` first. |
| `'models' support requires Docker Model plugin` | Enable Model Runner in Docker Desktop, or use `compose.ci.yml` + `RAG_LLM_BASE_URL` (root README). |

---

## Related

| Document | Contents |
|----------|----------|
| [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md) | Change, test, and release CE |
| [CE_EE_BUILD_RUN_DEBUG.md](../../product/CE_EE_BUILD_RUN_DEBUG.md) | Host vs Docker vs Helm |
| [TECH_STACK.md](../../product/TECH_STACK.md) | Why these libraries |
| [ADMIN_GUIDE.md](ADMIN_GUIDE.md) | Operate a running CE |
| [ENTERPRISE.md](../../../ENTERPRISE.md) | What CE does not include |
