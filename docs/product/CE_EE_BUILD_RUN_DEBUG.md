# CE / EE — Build, Start & Debug

**Audience:** Engineering, QA, demos
**Status:** Reference runbook for local dev **and** Docker

This is the practical companion to the architecture docs. It covers how to **build**, **start**, and **debug** the Community Edition (CE, MIT) and Enterprise Edition (EE, commercial) stacks — local venv, Docker Compose, and (optional) kind + Helm.

**Related:** [CONSOLE_CE_EE_UI_ARCHITECTURE.md](../ce/README.md) · [CONSOLE_UI_REFACTOR.md](../ce/README.md) · [console/README.md](../../console/README.md) · [../commercial/COMPOSE_OVERLAYS.md](../../ENTERPRISE.md) · [../commercial/CE_EE_MOAT_AND_ENDPOINT_TIERING.md](../../ENTERPRISE.md) · [../commercial/CE_EE_PLUGIN_SEAMS.md](../../ENTERPRISE.md) · [KIND_HELM_LOCAL.md](../../ENTERPRISE.md)

---

## Moving parts

| Piece | What it is | Build output |
|-------|-----------|--------------|
| **Proxy backend** (`rag-protection-proxy`) | FastAPI/uvicorn app; serves everything on `:8090` | Python, no build step |
| **CE UI** (`console/`) | Vite/React monorepo (`core` + `ce` packages) | `rag-protection-proxy/rag_protection_proxy/ui/static/ce/` |
| **EE UI** (`rag-protection-enterprise/ee_ui/`) | Lazy-loaded React bundle | `rag_protection_enterprise/ee_ui/dist/ee-ui.js` → served at `/ui/static/ee/ee-ui.js` |
| **EE backend** (`rag-protection-enterprise`) | `register_enterprise()` — Tier 2 operator routes, connectors, pgvector, rate limits | Python, no build step |
| **MCP backend** (`docker/mcp-filesystem/`) | Layer 2 real MCP server (`supergateway` + `@modelcontextprotocol/server-filesystem`) behind the gateway shim | Docker image `rag-protection-mcp-filesystem:latest` |

CE and EE are **one React app**. CE registers its **five** workspaces at startup (Overview, Query Lab, Documents & Ingest, Tool Gateway, Audit Log); the shell probes `GET /health` and, if `enterprise_installed: true`, dynamically imports `ee-ui.js` and overlays/adds EE sidebar items (Documents gains CHALLENGE/preview/approve; plus Connectors and Policy). If EE is not installed/built, the console silently stays CE-only.

### Backend endpoint tiers (what works without EE)

Installing the EE Python package (`dev_install_ee.sh` or `Dockerfile.ee`) is what registers **Tier 2** and **Tier 3** routes via `register_enterprise()`. Without it, those paths return **404** — not 401/403.

| Tier | Examples | CE-only install | CE + EE install |
|------|----------|-----------------|-----------------|
| **Tier 1** (trust surface) | `POST /v1/query`, `POST /v1/ingest`, `GET /admin/audit/events`, `POST /admin/reload-policy` | ✅ Works | ✅ Works |
| **Tier 2** (operator admin) | `GET /admin/challenges`, `GET /admin/policy-config`, `PATCH /admin/policy-knobs`, pattern preview, `GET /admin/tenants` | ❌ **404** | ✅ Works |
| **Tier 3** (connectors) | `GET /admin/connectors/status`, Drive/Notion ingest, `POST /admin/scim/sync` | ❌ **404** | ✅ Works |

**Important:** `POST /v1/ingest` stays Tier 1 — mid-risk documents are still quarantined server-side in CE-only mode. The CE **Documents & Ingest** workspace supports ingest, corpus list, quarantine **metadata**, and delete/re-ingest. Only the **review workflow** (CHALLENGE queue, approve/reject, inspect/preview) is Tier 2 / EE overlay.

Tier 2 handlers live in `rag-protection-enterprise/rag_protection_enterprise/tier2_routes.py`. Full route map: [CE_EE_MOAT §3](../../ENTERPRISE.md#3-endpoint-tiering-map).

---

## Build scripts

Two full build scripts wrap the steps below:

| Script | Builds | Key flags |
|--------|--------|-----------|
| `tools/build_ce.sh` | CE console (`core` + `ce`) → `ui/static/ce/` | `--install` (pip proxy), `--typecheck`, `--test`, `--clean`, `--ci` |
| `tools/build_ee.sh` | EE bundle → `ee_ui/dist/ee-ui.js` | `--install` (pip CE+EE), `--with-ce`, `--typecheck`, `--clean`, `--ci` |

```bash
# Fresh machine — CE only
bash tools/build_ce.sh --install

# Fresh machine — full EE stack (backend + CE shell + EE bundle)
bash tools/build_ee.sh --install --with-ce

# Fast iteration (deps already installed)
bash tools/build_ce.sh          # rebuild CE bundle
bash tools/build_ee.sh          # rebuild EE bundle
```

Both honor `RAG_CE_ROOT` / `RAG_EE_ROOT` for non-default checkout locations, and require Node ≥ 20 + npm.

---

## Local development

### Install (Python)

**First-time CE venv (version, libraries, activate, verify):** [LOCAL_SETUP.md](../ce/guide/LOCAL_SETUP.md).

```bash
# Repository root (this checkout)
bash tools/setup_venv.sh
source .venv/bin/activate
```

Installing the EE package makes `/health` report `enterprise_installed: true`, enables `mount_ee_ui()`, and registers **Tier 2 + Tier 3** backend routes.

#### CE-only (no Tier 2/3 routes — matches public CI)

`tools/setup_venv.sh` already editable-installs `rag-protection-proxy` plus runtime, dev, and examples requirements. Equivalent manual extras:

```bash
pip install -e "rag-protection-proxy[dev]"
# equivalent: cd rag-protection-proxy && pip install -e . -r requirements-dev.txt
```

**Important:** this does **not** remove `rag-protection-enterprise` if it was installed earlier. For CE-only seam tests or the smoke assertion below, either uninstall EE or use a dedicated venv:

```bash
pip uninstall rag-protection-enterprise -y
# or: python3 -m venv .venv-ce-only && source .venv-ce-only/bin/activate
```

Verify CE-only:

```bash
python -c "from rag_protection_proxy.app import app; assert not getattr(app.state, 'enterprise_registered', False)"
pip list | grep rag-protection   # rag-protection-proxy only
```

#### CE + EE (local dev, full operator stack)

**Recommended** — from repo root:

```bash
bash tools/dev_install_ee.sh
```

Installs `rag-protection-proxy[dev]` and `rag-protection-enterprise[dev]` as editable wheels. Non-default paths: `RAG_CE_ROOT`, `RAG_EE_ROOT`.

**Manual equivalent:**

```bash
pip install -e "rag-protection-proxy[dev]"
pip install -e "rag-protection-enterprise[dev]"
```

Verify CE + EE:

```bash
python -c "from rag_protection_proxy.app import app; assert getattr(app.state, 'enterprise_registered', False)"
pip list | grep rag-protection   # both packages
```

**Optional — EE UI bundle** (Tier 2/3 backend routes work without it; browser EE sidebar panels need the JS build):

```bash
bash tools/build_ee.sh
```

### Build the UI bundles

```bash
bash tools/build_ce.sh              # → ui/static/ce/
bash tools/build_ee.sh              # → ee_ui/dist/ee-ui.js
```

Manual equivalent:

```bash
cd console && npm install && npm run build
cd ../rag-protection-enterprise/ee_ui && npm install && npm run build
```

### Start the proxy

```bash
cd rag-protection-proxy
# Host dev: point the LLM at the host-published Model Runner port (see caveat below)
RAG_LLM_BASE_URL=http://localhost:12434/engines/v1 \
uvicorn rag_protection_proxy.app:app --host 0.0.0.0 --port 8090 --reload
```

Open **http://localhost:8090/ui** and hard-refresh (Cmd+Shift+R). Toolbar tokens: admin `rag-admin-demo-key`, user `employee-demo-token` (or `hr-demo-token`), tenant `default`.

> `--reload` restarts on **Python** changes only. It does **not** rebuild JS — re-run `build_ce.sh` / `build_ee.sh` after UI edits.

> **⚠️ LLM URL differs for host dev vs. Docker.** The default `policy.yaml` points `llm.base_url` at `http://model-runner.docker.internal/engines/v1`, which **only resolves inside Docker Compose**. When you run `uvicorn` directly on the host, that hostname fails DNS resolution (`nodename nor servname provided`), the LLM call falls back to a generic "temporarily unavailable" message, and every query then gets **blocked at citation verification** (`block_reason: citation_verification_failed`). For host dev, override the endpoint with the host-published Model Runner port:
> ```bash
> export RAG_LLM_BASE_URL=http://localhost:12434/engines/v1
> ```
> Requires Docker Desktop → Settings → AI → Model Runner → **Enable host-side TCP support** (port `12434`) and the model pulled (`docker model pull ai/gemma3-qat`). Verify with `curl http://localhost:12434/engines/v1/models`.

> **Customer wheel install on a laptop (no Compose):** [EE_CUSTOMER_DELIVERY.md — Choosing CE vs EE](../../ENTERPRISE.md#choosing-ce-vs-ee) and [Local PC — /tmp demo (CE and EE)](../../ENTERPRISE.md#local-pc--tmp-demo-ce-and-ee). Use bundle `config-sample/` under `/tmp/rag-protection`; set `RAG_STORE_BACKEND=sqlite` unless host Qdrant is up (`RAG_QDRANT_URL=http://localhost:6333`).

### Verify what's live

```bash
# EE package installed?
curl -s http://localhost:8090/health | jq .enterprise_installed        # true = EE installed in THIS process

# Note: enterprise_installed reflects register_enterprise() for the process on :8090 —
# not pip show Version, not release tags. pip install into another venv does not change
# an already-running uvicorn. See EE_CUSTOMER_DELIVERY.md § Choosing CE vs EE.

# EE UI bundle built & mounted?
curl -sI http://localhost:8090/ui/static/ee/ee-ui.js | head -1         # 200 = EE built & mounted

# Which UI shell?
curl -sI http://localhost:8090/ui | grep -i x-rag-protection-ui-build  # ce-v1

# Tier 2 route probe — use rag-admin-demo-key (.env default), not test-admin-key (pytest only)
# CE-only: 404 with bearer | EE: 401 without bearer, 200 with rag-admin-demo-key
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8090/admin/policy-config
curl -s -o /dev/null -w "%{http_code}\n" \
  http://localhost:8090/admin/policy-config \
  -H "Authorization: Bearer rag-admin-demo-key"

# Tier 3 route probe (connectors — EE only)
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8090/admin/connectors/status
```

### Debug CE

CE has a Vite dev server with HMR + source maps — the fastest loop.

```bash
# Terminal 1 — proxy on :8090 (the dev server proxies API calls to it)
cd rag-protection-proxy && uvicorn rag_protection_proxy.app:app --port 8090 --reload

# Terminal 2 — CE dev server on :5174 (hot reload)
cd console && npm run dev
```

Open **http://localhost:5174** and debug in browser DevTools; `/health`, `/v1`, `/admin`, `/ui/static`, `/metrics` are proxied to `:8090`.

> **Seeing EE panels on the CE dev server?** That's expected: `npm run dev` runs the CE shell, but it auto-detects Enterprise (`GET /health` → `enterprise_installed: true` on your `:8090` proxy) and lazy-loads `ee-ui.js`. To debug **CE-only**, skip the Enterprise probe:
>
> ```bash
> npm run dev:ce-only        # sets VITE_EE=off — CE workspaces only
> ```
>
> Or toggle at runtime without restarting the dev server by adding `?ee=off` to the URL:
>
> ```text
> http://localhost:5174/?ee=off
> ```
>
> Both paths force `bootstrapEnterprise` off in `console/packages/ce/src/main.tsx`; the sidebar then shows only Overview, Query Lab, and Audit Log. The **same `?ee=off` toggle works on the production-like `:8090` shell** — open `http://localhost:8090/ui?ee=off` (the toggle is read at runtime from the URL, so no separate build is needed). `VITE_EE=off` is the dev-server-only equivalent baked at build time.

```bash
# Type errors / unit tests for CE (core + ce)
cd console && npm run typecheck
cd console && npm run test              # Vitest
cd console && npm run test -- --watch   # watch mode

# Rebuild only the shared core lib, or only the CE app
cd console && npm run build:core
cd console && npm run build:ce

# CE-only backend seams (no enterprise routes, enterprise_installed:false)
# 12 tests: Tier 2 (8 parametrized) + Tier 3 connector + health + pgvector
cd rag-protection-proxy && pytest tests/test_ce_ee_seams.py -v

# Full CE proxy suite (CE-only CI — ~13 tests skip via @ee_required)
bash tools/run_tests.sh -q -m "not live"

# Tier 2 integration tests — requires EE wheel first
bash tools/dev_install_ee.sh
cd rag-protection-proxy && pytest -q \
  tests/test_ui_and_admin.py \
  tests/test_injection_policy.py \
  tests/test_p1.py \
  tests/test_e2.py -k "policy_config or inspect" \
  tests/test_oidc_admin.py \
  tests/test_url_threat.py

# EE registration smoke (Tier 2 + Tier 3 happy-path)
cd rag-protection-enterprise && pytest tests/test_register_enterprise.py -v

# E5.5 CHALLENGE queue workflow (EE repo — Tier 2 routes)
cd rag-protection-enterprise && pytest tests/test_e5_5_challenge_queue.py -v

# Confirm the CE shell is what /ui serves (expect: ce-v1)
curl -sI http://localhost:8090/ui | grep -i x-rag-protection-ui-build
```

Formal manual test cases mirroring the pytest matrix: [CE_EE_SEAM_TEST_PLAN.md](../../ENTERPRISE.md) (TC-CEEE-000–008).

To debug CE against the production-like `:8090` shell (not the dev server), rebuild and hard-refresh. The proxy on `:8090` must already be running (host `uvicorn` or Docker) — `build_ce.sh` only rebuilds the JS bundle it serves, it does not start anything:

```bash
# CE + EE (default): plain /ui auto-loads EE when the proxy reports enterprise_installed: true
bash tools/build_ce.sh && open http://localhost:8090/ui

# CE-only: ?ee=off skips the Enterprise probe even when EE is installed on the proxy
bash tools/build_ce.sh && open "http://localhost:8090/ui?ee=off"
```

> If `open http://localhost:8090/ui` shows EE panels when you wanted CE-only, that's expected — EE is installed on the proxy and the shell lazy-loads it. Use `?ee=off` (above) for the CE-only view; there's no need to uninstall the EE package or run a separate server.

### Debug EE

EE is a **library bundle** (`ee-ui.js`) with **no dev server** — it is always loaded from the proxy at `/ui/static/ee/ee-ui.js`, even when you view the CE dev server on `:5174`. The loop is rebuild → hard-refresh.

```bash
# Fast type feedback without a full bundle
cd rag-protection-enterprise/ee_ui && npm run typecheck

# EE pane component tests (Vitest + Testing Library, jsdom — no proxy needed)
cd rag-protection-enterprise/ee_ui && npm test
cd rag-protection-enterprise/ee_ui && npm run test:watch   # watch mode

# Rebuild the EE bundle, then hard-refresh the browser (Cmd+Shift+R)
bash tools/build_ee.sh

# EE must be installed for the shell to even attempt loading ee-ui.js
curl -s http://localhost:8090/health | jq .enterprise_installed   # expect: true

# Confirm the EE bundle is served (expect: 200)
curl -sI http://localhost:8090/ui/static/ee/ee-ui.js | head -1

# EE static-serving test (ee-ui.js mounted when packaged) +
# E5 pane-wiring test (bundle registers the EE workspaces)
cd rag-protection-enterprise && pytest tests/test_ee_ui.py -v
cd rag-protection-enterprise && pytest tests/test_e5.py::test_ee_bundle_registers_e5_operator_workspaces -v
```

The `ee_ui` Vitest suite renders each pane factory directly (`createXPane(React, () => auth)` with a stub `useAuth`) and asserts behavior that the legacy monolith used to cover via server-rendered HTML string checks:

| Test file | Covers |
|-----------|--------|
| `src/register.test.ts` | The EE workspaces (Documents & Ingest, Connectors, Policy) register with `edition: 'ee'`, correct ids/labels/order; idempotent |
| `src/workspaces/ConnectorsPane.test.ts` | Status/Drive/Notion cards, SCIM + scheduled-sync buttons, token prompt |
| `src/workspaces/ChallengeQueuePane.test.ts` | Queue headers + token-required empty state (rendered at the top of Documents & Ingest) |
| `src/workspaces/DocumentsPane.test.ts` | Corpus table + ingest form, token prompts, Fill sample, ingest guard |
| `src/workspaces/PolicyPane.test.ts` | Policy Viewer prompt + `GET /admin/policy-config` snapshot; Pattern Lab subtab (`POST /admin/policy/preview-patterns`) — **requires EE wheel on proxy** for live API calls |

Debug EE panes in browser DevTools (source maps come from the vite build). If an EE sidebar item never appears, check in order: `enterprise_installed:true` → `ee-ui.js` returns 200 → no import error in the browser console (the shell silently stays CE-only on any failure).

If a pane loads but API calls fail with **404**, the EE **backend** is not installed — `ee-ui.js` alone is not enough. Run `bash tools/dev_install_ee.sh` (host) or start with `docker_start.sh --ee` (Docker).

### Debug the backend (shared by CE and EE)

```bash
# Auto-restart on Python edits + live request logs
# (export RAG_LLM_BASE_URL=http://localhost:12434/engines/v1 first — see "Start the proxy")
cd rag-protection-proxy && uvicorn rag_protection_proxy.app:app --port 8090 --reload

# Breakpoint debugging: add  in code and run WITHOUT --reload
cd rag-protection-proxy && uvicorn rag_protection_proxy.app:app --port 8090
```

Or launch the IDE Python debugger against module `uvicorn` with args `rag_protection_proxy.app:app --port 8090`.

**EE backend routes** (Tier 2 + Tier 3) require the EE package installed so `register_enterprise()` runs:

```bash
bash tools/dev_install_ee.sh
```

| Module | Tier | What it registers |
|--------|------|-------------------|
| `tier2_routes.py` | 2 | CHALLENGE queue, policy-config/knobs/backups, pattern preview, tenants |
| `connector_routes.py` (and related) | 3 | Drive/Notion ingest, SCIM sync, connector status |
| `rate_limit.py`, `pgvector_store.py` | 3 | Query rate limits, pgvector store backend |

Breakpoint debugging Tier 2 handlers: set breakpoints in `rag-protection-enterprise/rag_protection_enterprise/tier2_routes.py`, start uvicorn **without** `--reload`, and confirm `curl …/admin/policy-config` returns 200 (not 404).

---

## CI / CD (GitHub Actions)

Full process (workflows, triggers, secrets, developer workflow, troubleshooting): **[CI_CD.md](../ce/README.md)**.

Quick reference:

| Repo | Primary workflow | Key jobs |
|------|------------------|----------|
| **CE** | [ci.yml](../ce/README.md) | `test-ce-only`, `console`, `integration-live` |
| **EE** | [EE ](https://github.com/marifort/rag-protection-enterprise/blob/main/.github/workflows/ci.yml) | `ce-plus-ee` (pins [CE_PIN](https://github.com/marifort/rag-protection-enterprise/blob/main/CE_PIN) → `v0.1.1-ce`) |

Also on CE repo: `security.yml` (weekly audit), `rag-scan.yml`, `rag-ground.yml`, and `rag-injbench.yml` (path-filtered PR gates).

When CE/EE seam changes land, promote a new `vX.Y.Z-ce` tag and bump `CE_PIN` — [GIT_LABELS.md § Quick reference](../ce/README.md#quick-reference--ce--ee-check-in) (full procedure: [§ Promotion](../ce/README.md#promotion-procedure--dev-labels--release-tags--ee-ci)).

---

## Docker

The repo uses **stacked compose overlays** plus helper scripts (run from repo root). **`docker_start.sh` does not build the React console** — see [COMPOSE_OVERLAYS.md § React console](../../ENTERPRISE.md#react-console-is-not-built-inside-docker).

| File | Role |
|------|------|
| `compose.yml` | Base CE stack: `rag-protection-proxy` (`Dockerfile`) + optional `qdrant` (`--profile qdrant`) |
| `compose.ee.yml` | EE overlay — swaps in `Dockerfile.ee` (copies `rag_protection_enterprise` into the image) and `include`s the MCP overlay |
| `compose.mcp-tools.yml` | Layer 2 MCP filesystem sidecar (`mcp-tools` profile) |

The CE image copies only `rag_protection_proxy` + `config`; the EE image (`Dockerfile.ee`) **also** copies `rag_protection_enterprise`, so `register_enterprise()` runs, `enterprise_installed` becomes `true`, and **Tier 2 + Tier 3** routes are available.

`compose.yml` bind-mounts host `rag_protection_proxy/` into the container for dev convenience, but **does not** mount `rag_protection_enterprise/`. Uninstalling the EE wheel from a host venv does **not** change a running container — EE remains in the image until you rebuild with the CE `Dockerfile`.

| Image | Tier 1 routes | Tier 2/3 routes | `enterprise_installed` |
|-------|---------------|-----------------|------------------------|
| CE (`Dockerfile`, `INSTALL_EE_WHEEL=0`*) → `rag-protection-proxy:latest` | ✅ | ❌ 404 | `false` |
| EE (`Dockerfile.ee`, `INSTALL_EE_WHEEL=1`*) → `rag-protection-proxy:ee` | ✅ | ✅ | `true` |

\* `INSTALL_EE_WHEEL` is a **documentation build arg** only — not read by any `RUN` step. Edition is determined by which Dockerfile is used; see [COMPOSE_OVERLAYS.md § Where INSTALL_EE_WHEEL is used](../../ENTERPRISE.md#where-install_ee_wheel-is-used-and-where-it-is-not).

**Contributors:** CE-only Docker needs no `rag-protection-enterprise/` checkout. Full matrix: [COMPOSE_OVERLAYS.md § CE-only Docker for contributors](../../ENTERPRISE.md#ce-only-docker-for-contributors).

**Switch Docker from EE back to CE** (after `docker_start.sh --ee` or a prior EE build):

```bash
docker compose down
docker compose build --no-cache
docker compose up -d
curl -s http://localhost:8090/health | jq .enterprise_installed   # expect: false
```

### Kubernetes (kind + Helm)

Compose remains the demo path (`docker_start.sh`). Helm needs a cluster. Local kind, image build/load, Compose-parity EE (`helm_start.sh`), and port-forward drops: [KIND_HELM_LOCAL.md](../../ENTERPRISE.md). Chart defaults: [E1.5](../../ENTERPRISE.md).

```bash
kind create cluster --name rag-protection
bash tools/helm_start.sh                         # first time
bash tools/helm_start.sh --no-build --no-load    # skip image if already loaded
bash tools/helm_port_forward.sh
```

Helm does not replace Compose. After deleting kind, `bash tools/docker_start.sh --ee` still works. There is no `.env` under `deploy/helm/` — `helm_start.sh` copies repo-root `.env` into a Kubernetes Secret.

For **AWS/EKS** (or GKE/AKS), take the chart and the image — kind does not emit a packaged cloud bundle. Drop `helm_start.sh` / `values-ee-local.yaml`. Push the image to a registry, put ALB/Ingress in front of `:8090`, and use a customer values file. Artifact table: [kind-helm-aws.md](../../ENTERPRISE.md).

### Prerequisites

1. Docker Desktop 4.40+ with **Model Runner** enabled (LLM served via `model-runner.docker.internal`).
2. For EE: the `rag-protection-enterprise/` checkout must be present (start script checks via `ensure_ee_checkout`).
3. **Build the UI bundles on the host first** (see caveat below).

### Run CE

```bash
bash tools/docker_start.sh              # CE, detached, builds image, waits for /health
bash tools/docker_start.sh --smoke      # + RAG smoke tests (ingest is Tier 1; CHALLENGE review needs EE)
# raw: docker compose up -d --build
```

CE Docker smoke can still drive `POST /v1/ingest` and query/audit flows. Tier 2 operator workflows (CHALLENGE queue, policy authoring) return **404** on the CE image — use `--ee` for those demos.

### Run EE

```bash
bash tools/docker_start.sh --ee            # EE proxy + MCP Layer 2
bash tools/docker_start.sh --ee --smoke    # + RAG + tool-gateway + MCP smoke checks
# raw (EE always needs --profile mcp-tools):
docker compose -f compose.yml -f compose.ee.yml --profile mcp-tools up -d --build
```

### EE entitlements (full demo)

Entitlements gate **which EE packs and features mount** (import routes, digest scheduler, tool registry, etc.). They are read at container start from `RAG_EE_ENTITLEMENTS`. `docker_start.sh` sources `.env` and **overwrites** a prior shell `export RAG_EE_ENTITLEMENTS=...` — put the list in `.env`, then recreate.

**Set in `.env` before start** — changing the value requires `docker_stop.sh --ee` then `docker_start.sh --ee`:

```bash
bash tools/build_ee.sh   # once — EE UI is not built inside docker_start.sh

# Put the list in .env (docker_start.sh sources .env and overwrites a prior export):
# RAG_EE_ENTITLEMENTS=dlp:hipaa,dlp:pci,dlp:gdpr,egress:denylist,egress:healthcare,egress:fintech,egress:saas,egress:public_sector,baseline:healthcare,baseline:fintech,baseline:saas,baseline:public_sector,weekly_digest,evidence_pack,tool_registry,inj_corpus:full

bash tools/docker_stop.sh --ee
bash tools/docker_start.sh --ee
docker exec rag-protection-proxy printenv RAG_EE_ENTITLEMENTS
```

| Check | Command |
|-------|---------|
| EE backend installed | `curl -s http://localhost:8090/health \| jq .enterprise_installed` → `true` |
| Pack licensed | `POST /admin/policy/import-dlp-pack` with `dlp:hipaa` → **200**; without → **403** |
| Digest licensed | `GET /admin/digest/preview` with `weekly_digest` → **200**; without → **404** (route not registered) |
| EE backend missing | Tier 2/3 routes → **404** (wrong image — use `--ee`, not CE `Dockerfile`) |

**Dev shortcut:** `RAG_EE_ENTITLEMENTS=all` or `*` grants every pack/feature.

Full entitlement table, optional `siem_pack` / `drift_monitor`, and combined 15-minute demo script: [LAB5_A1_A9_A10.md § Full EE demo in Docker](../ce/README.md#full-ee-demo-in-docker) · [Tutorial 09](../ce/tutorials/09-implemented-features-walkthrough.md).

### Other combos

```bash
bash tools/docker_start.sh --mcp-tools                              # CE + real MCP filesystem
docker compose --profile qdrant up -d --build                      # CE + Qdrant vector store
docker compose -f compose.yml -f compose.ee.yml --profile mcp-tools --profile qdrant up -d --build
```

### Stop (match the start flag)

```bash
bash tools/docker_stop.sh              # CE
bash tools/docker_stop.sh --ee         # EE
bash tools/docker_stop.sh --mcp-tools
bash tools/docker_stop.sh --volumes    # also drop persistent data volume
```

### Debug CE (Docker)

The CE compose file (`compose.yml`) targets the base image only.

```bash
# Logs / status / shell for the CE container
docker compose logs -f rag-protection-proxy
docker compose ps
docker exec -it rag-protection-proxy /bin/bash

# Live logs in the foreground (Ctrl+C to stop)
bash tools/docker_start.sh --foreground

# CE JS is bind-mounted → rebuild on host + hard-refresh, no image rebuild
bash tools/build_ce.sh

# Proxy source is bind-mounted read-only → pick up Python edits with a restart
docker compose restart rag-protection-proxy

# Fresh image rebuild (deps changed)
bash tools/docker_start.sh --no-cache
```

### Debug EE (Docker)

EE runs under the overlay files, so pass the same `-f`/profile (or use the `--ee` script) for every compose command.

```bash
EE="-f compose.yml -f compose.ee.yml --profile mcp-tools"

# Logs / status / shell for the EE stack
docker compose $EE logs -f rag-protection-proxy
docker compose $EE logs --tail=40 mcp-filesystem     # MCP Layer 2 sidecar
docker compose $EE ps
docker exec -it rag-protection-proxy /bin/bash

# Live logs in the foreground (Ctrl+C to stop)
bash tools/docker_start.sh --ee --foreground

# EE JS is BAKED into the image → rebuild bundle AND image, then restart
bash tools/build_ee.sh
bash tools/docker_start.sh --ee            # re-runs --build

# Verify from inside the running stack
curl -s http://localhost:8090/health | jq .enterprise_installed        # true
curl -sI http://localhost:8090/ui/static/ee/ee-ui.js | head -1         # 200
curl -s -o /dev/null -w "%{http_code}\n" \
  http://localhost:8090/admin/policy-config \
  -H "Authorization: Bearer rag-admin-demo-key"   # 200 = Tier 2 registered

# Fresh image rebuild (EE deps or bundle changed)
bash tools/docker_start.sh --ee --no-cache
```

`compose.yml` bind-mounts the proxy source read-only, so after editing proxy Python just `docker compose [EE flags] restart rag-protection-proxy` — no image rebuild needed (there is no `--reload` in the container). The key CE/EE difference: **CE JS is bind-mounted (rebuild only), EE JS is baked into the image (rebuild + image rebuild)**.

### ⚠️ The UI JS is not built inside Docker

Neither `Dockerfile` nor `Dockerfile.ee` runs `npm run build`; they only copy Python. The console is served from host-built files:

- **CE bundle** → `rag-protection-proxy/rag_protection_proxy/ui/static/ce/` — **bind-mounted** live into the container.
- **EE bundle** → `rag_protection_enterprise/ee_ui/dist/ee-ui.js` — **baked into the EE image** at build time.

Consequences:

- Rebuild CE JS (`build_ce.sh`) + hard-refresh → changes appear **without** rebuilding the image.
- Rebuild EE JS (`build_ee.sh`) → must **rebuild the EE image** (`docker_start.sh --ee` re-runs `--build`) for changes to appear.
- Skip the EE UI build and the backend still reports `enterprise_installed: true`, but `/ui/static/ee/ee-ui.js` 404s and the console stays CE-only.

Always build bundles before the first Docker run:

```bash
bash tools/build_ce.sh
bash tools/build_ee.sh
```

---

## MCP tool gateway — build, run & debug

The proxy ships an identity-bound **tool gateway** (`GET /v1/tools`, `POST /v1/tools/invoke`) with three integration layers. This section is the build/run/debug companion; full operational detail is in the [Layer 2 runbook](../../ENTERPRISE.md).

| Layer | Agent speaks | Backend | Enabled by |
|-------|--------------|---------|------------|
| **1** (default) | HTTP + Bearer | mock backends (`mock_files`, `mock_sql`, `mock_email`) | Always on — base `tool_policy.yaml` |
| **2** | HTTP + Bearer | real MCP server (`mcp-server-filesystem`) via the gateway shim | `tool_policy.mcp.yaml` + `compose.mcp-tools.yml` (`--mcp-tools` / `--ee`) |
| **3** | MCP wire | separate `mcp-gateway` sidecar → HTTP invoke | **Deferred** — profile `mcp-wire` reserved, not implemented |

The **MCP shim** (`rag-protection-proxy/rag_protection_proxy/tools_gateway/backends/mcp_shim.py`) ships **inside** the proxy — it is registered in `BACKEND_HANDLERS` next to the mock backends, so there is no separate proxy build for Layer 2. What Layer 2 adds is (a) a policy file that routes `read_file` to `backend: mcp_filesystem`, and (b) a **separate MCP server container** on an internal-only network.

### Moving parts (Layer 2)

| Piece | Role | Build |
|-------|------|-------|
| `tools_gateway/backends/mcp_shim.py` | MCP **client** — JSON-RPC over Streamable HTTP to the backend | Python, ships in proxy image (no build) |
| `config/tool_policy.mcp.yaml` | Routes `read_file` → `backend: mcp_filesystem`, `mcp_tool: read_text_file` | Config, no build |
| `docker/mcp-filesystem/Dockerfile` | `supergateway` + globally-installed `mcp-server-filesystem` | `docker compose build mcp-filesystem` → `rag-protection-mcp-filesystem:latest` |
| `examples/agentic/mcp_tool_gateway/demo_workspace/` | Read-only `/workspace` mount the MCP server reads from | Files, no build |

> The MCP server is pre-installed at **image build** time because the `mcp-backends` network is `internal: true` (no outbound internet) — a runtime `npx -y` would hang waiting for the npm registry.

### Environment (Layer 2 overlay)

Set by `compose.mcp-tools.yml` (and, transitively, `compose.ee.yml`):

| Variable | Default / value | Purpose |
|----------|-----------------|---------|
| `RAG_TOOL_POLICY_FILE` | `/app/config/tool_policy.mcp.yaml` | Enables the `mcp_filesystem` backend for `read_file` |
| `MCP_FILESYSTEM_URL` | `http://mcp-filesystem:8000/mcp` | Streamable HTTP endpoint the shim POSTs JSON-RPC to |
| `MCP_FILESYSTEM_WORKSPACE_ROOT` | `/workspace` (optional) | Prefix mapped onto relative `path` arguments |
| `MCP_BACKEND_TIMEOUT_SECONDS` | `30` (optional) | httpx timeout for MCP JSON-RPC |

### Build

There is no JS or Python build for Layer 2 — only the MCP server image. `docker_start.sh` builds it automatically whenever MCP is in play:

```bash
# --mcp-tools and --ee both build the mcp-filesystem image (see docker_start.sh)
bash tools/docker_start.sh --mcp-tools           # builds proxy + mcp-filesystem, then starts
bash tools/docker_start.sh --mcp-tools --no-cache # force a clean MCP image rebuild

# Raw: build just the MCP backend image
docker compose -f compose.yml -f compose.mcp-tools.yml build mcp-filesystem
```

### Run

```bash
# CE proxy + real MCP filesystem backend
bash tools/docker_start.sh --mcp-tools
bash tools/docker_start.sh --mcp-tools --smoke    # + RAG + tool-gateway + MCP read_file smoke

# EE always includes the MCP overlay (compose.ee.yml s compose.mcp-tools.yml)
bash tools/docker_start.sh --ee

# Raw compose equivalents (mcp-tools profile is REQUIRED — the backend has no ports)
docker compose -f compose.yml -f compose.mcp-tools.yml --profile mcp-tools up -d --build
docker compose -f compose.yml -f compose.ee.yml       --profile mcp-tools up -d --build
```

Stop with the matching flag, then note the layer switch caveat:

```bash
bash tools/docker_stop.sh --mcp-tools
```

> **Switching Layer 2 → Layer 1:** stop with `--mcp-tools` **first**, then start without it. Otherwise the `mcp-filesystem` container keeps running while the proxy reverts to mock backends.

**Local dev (no Docker).** `uvicorn … app:app` defaults to **Layer 1** (mock backends) — `read_file` returns mock content. To exercise the real shim locally, run the MCP server standalone (published port) and point the proxy at it:

```bash
# 1) Run the MCP filesystem server with a host port (dev only — prod keeps it internal)
docker compose -f compose.yml -f compose.mcp-tools.yml build mcp-filesystem
docker run --rm -p 8000:8000 \
  -v "$PWD/examples/agentic/mcp_tool_gateway/demo_workspace:/workspace:ro" \
  rag-protection-mcp-filesystem:latest \
  --port 8000 --outputTransport streamableHttp --stdio "mcp-server-filesystem /workspace"

# 2) Start the proxy with the MCP policy + URL
cd rag-protection-proxy
RAG_TOOL_POLICY_FILE=config/tool_policy.mcp.yaml \
MCP_FILESYSTEM_URL=http://localhost:8000/mcp \
uvicorn rag_protection_proxy.app:app --port 8090 --reload
```

### Verify what's live

```bash
# Allow path — expect "decision":"allow" and "result.source":"mcp"
curl -s -X POST http://localhost:8090/v1/tools/invoke \
  -H "Authorization: Bearer employee-demo-token" \
  -H 'Content-Type: application/json' \
  -d '{"tool":"read_file","arguments":{"path":"docs/runbook.md"}}' | jq .

# Tool discovery (HTTP stand-in for MCP tools/list) — per-caller allow flags
curl -s http://localhost:8090/v1/tools -H "Authorization: Bearer employee-demo-token" | jq .

# Confirm the proxy actually has the MCP policy + URL wired
docker exec rag-protection-proxy env | grep -E 'MCP|TOOL_POLICY'
```

A `read_file` that returns **mock** content (not `"source":"mcp"`) means the Layer 1 policy is still active — check `RAG_TOOL_POLICY_FILE`.

### Debug

```bash
MCP="-f compose.yml -f compose.mcp-tools.yml --profile mcp-tools"   # or the --ee flags

docker compose $MCP ps                                   # both proxy + mcp-filesystem up?
docker compose $MCP logs --tail=40 mcp-filesystem        # MCP server / supergateway logs
docker logs rag-protection-mcp-filesystem --tail 30

# Simulate a transport failure (TC-L1-L2-009): stop the backend, invoke, restart
docker stop rag-protection-mcp-filesystem
# … invoke read_file → expect 403 "MCP backend error: … transport failed"
docker start rag-protection-mcp-filesystem
```

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `read_file` returns mock content | Layer 1 policy active | Ensure `RAG_TOOL_POLICY_FILE=/app/config/tool_policy.mcp.yaml` (use `--mcp-tools`/`--ee`) |
| `MCP_FILESYSTEM_URL is not set` | Base compose, no MCP overlay | Start with `--mcp-tools` (or `--ee`) so the env is injected |
| `MCP transport failed: timed out` | MCP child never started (e.g. `npx` on the internal net) | Rebuild the image; confirm the command runs `mcp-server-filesystem`, not `npx` |
| `Unexpected MCP content type: unknown` | Old shim without 202/empty-notification handling | Rebuild the `rag-protection-proxy` image |
| `path outside allowed directories` | Absolute path not under `/workspace` | Use relative sandbox paths (`docs/runbook.md`); the shim prefixes `/workspace/` |
| `Caller not authorized for tool read_file` | Caller's groups ∉ `allowed_groups` | Edit `tool_policy.mcp.yaml` / caller groups in `acl_policy.yaml`, then reload policy |

Deeper decision-tree, sequence, and network diagrams: [LAYER2_MCP_RUNBOOK.md](../../ENTERPRISE.md).

### Test

```bash
# Unit / regression — no live stack (mocked MCP transport)
cd rag-protection-proxy
pytest -q tests/test_mcp_shim.py tests/test_tools_gateway.py

# Live smoke against a running stack
bash tools/docker_start.sh --mcp-tools --smoke                              # start + full smoke
RAG_SMOKE_TOOLS=1 RAG_MCP_TOOLS=1 bash tools/smoke_rag_proxy.sh             # smoke on an up stack
```

The MCP smoke check asserts `read_file` returns `"source":"mcp"` with runbook content; tool-gateway checks cover 401 (no bearer), group blocks, SQL/email guards, and `GET /v1/tools` allow flags.

### Static lint (shift-left, no runtime)

Lint an MCP server's `tools/list` manifest for description injection / over-broad scopes **before** wiring it in — the CI counterpart to the runtime gateway:

```bash
tools/mcp-lint scan --manifest tools/mcp_lint/examples/good_tools.json
tools/mcp-lint scan --url http://localhost:8000/mcp          # live MCP server
```

See [README.md](../../tools/mcp_lint/README.md).

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Smoke sits a long time on `Engineer query (should NOT retrieve HR payroll)` | Expected on a fresh stack: first `/v1/query` after `/health` pays Docker Model Runner cold-start and still calls the LLM if other authorized chunks match weakly (payroll itself stays ACL-excluded). HR/FAQ steps afterward are faster. See [CE_LEGACY_AND_PACKAGING_NOTES.md §3](../ce/README.md#docker-start-smoke-tests). |
| Every query blocked with `citation_verification_failed` on host dev | LLM unreachable — `model-runner.docker.internal` doesn't resolve outside Docker. Set `RAG_LLM_BASE_URL=http://localhost:12434/engines/v1` (enable host-side TCP in Model Runner). Confirm via the `LLM request failed` warning in the uvicorn log. Query Lab may show **citation hard gate** with unsupported claims that are the “temporarily unavailable (Errno 8)” fallback — fix the LLM URL, do not disable the gate. |
| Installed only CE wheel but `enterprise_installed: true` / Enterprise logs | Soft register — Enterprise already in the same venv. Fresh venv or `pip uninstall rag-protection-enterprise` — [Choosing CE vs EE](../../ENTERPRISE.md#choosing-ce-vs-ee) |
| Host uvicorn: `Policy file not found` / Qdrant DNS or connection refused | Wrong cwd or `.env` forces `vector` + Compose `qdrant` hostname — [Local PC — /tmp demo](../../ENTERPRISE.md#local-pc--tmp-demo-ce-and-ee) |
| Sidebar missing Documents / CHALLENGE / Connectors | Install EE backend (`dev_install_ee.sh` or EE image); check `enterprise_installed` in `/health` |
| EE panes visible but CHALLENGE/Policy API calls return **404** | EE **UI** built but EE **backend** not installed — run `dev_install_ee.sh` or use `docker_start.sh --ee` |
| `GET /admin/policy-config` returns **404** with EE installed | Wrong image (CE Dockerfile) or `register_enterprise()` failed — check proxy logs for ImportError; reinstall EE wheel |
| CE-only venv / pytest pass but `curl :8090` returns **200** on Tier 2 routes | Docker on `:8090` still runs an **EE image** — independent of `pip uninstall` in the host venv | `curl -s http://localhost:8090/health \| jq .enterprise_installed`; rebuild CE image (`docker compose build --no-cache`) or stop container and use host uvicorn |
| `curl` with `test-admin-key` returns **401** on Tier 2 routes | `test-admin-key` is for **pytest** (`monkeypatch`); live server uses `rag-admin-demo-key` from `.env` / Compose | Use `Authorization: Bearer rag-admin-demo-key`. **401 = route exists (likely EE), auth failed** — not the same as CE-only **404** |
| Uninstalled EE from venv; `enterprise_installed` still `true` on `:8090` | EE package is **baked into the Docker image**; only `rag_protection_proxy/` is bind-mounted | Rebuild CE image (see Docker § switch EE → CE) or stop Docker proxy and run uvicorn from CE-only venv |
| `ee-ui.js` 404, CE-only UI despite EE installed | Build EE bundle (`build_ee.sh`); rebuild EE image if in Docker |
| UI change not showing | JS isn't hot-reloaded on `:8090` — rebuild + hard-refresh, or use `:5174` for CE |
| EE edits not reflected on `:5174` | EE always loads from the proxy — rebuild `ee_ui` even in Vite dev mode |
| No `mcp-filesystem` after EE up | Missing `--profile mcp-tools` — use the script or add the profile |
| `read_file` times out on EE | Proxy configured for MCP but backend not started → restart with the profile |

---

## Related documentation

| Topic | Document |
|-------|----------|
| CE/EE UI architecture (how the split works) | [CONSOLE_CE_EE_UI_ARCHITECTURE.md](../ce/README.md) |
| Endpoint tier map (Tier 1/2/3) | [CE_EE_MOAT_AND_ENDPOINT_TIERING.md](../../ENTERPRISE.md) |
| Backend plugin seams + pytest matrix | [CE_EE_PLUGIN_SEAMS.md](../../ENTERPRISE.md) |
| Dev labels + release-tag promotion (`CE_PIN`) | [GIT_LABELS.md](../ce/README.md) |
| CI/CD process (workflows, secrets, troubleshooting) | [CI_CD.md](../ce/README.md) |
| UI refactor plan & workspace inventory | [CONSOLE_UI_REFACTOR.md](../ce/README.md) |
| Console quick start & URLs | [console/README.md](../../console/README.md) |
| Docker Compose overlays | [../commercial/COMPOSE_OVERLAYS.md](../../ENTERPRISE.md) |
| Customer wheel delivery / host laptop demo / CE vs EE install | [../commercial/EE_CUSTOMER_DELIVERY.md](../../ENTERPRISE.md) |
| MCP Layer 2 runbook | [../commercial/labs/lab1-mcp/LAYER2_MCP_RUNBOOK.md](../../ENTERPRISE.md) |
| MCP integration layers (HTTP / shim / wire) | [../commercial/labs/lab1-mcp/MCP_INTEGRATION_LAYERS.md](../../ENTERPRISE.md) |
| Tool gateway demo (agent + curl) | [../../examples/agentic/mcp_tool_gateway/README.md](../../examples/agentic/mcp_tool_gateway/README.md) |
| CE/EE seam QA test plan | [CE_EE_SEAM_TEST_PLAN.md](../../ENTERPRISE.md) |
