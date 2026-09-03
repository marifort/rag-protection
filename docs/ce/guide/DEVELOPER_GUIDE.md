# Community Edition — Developer Guide

| Field | Value |
|-------|-------|
| **Edition** | Community Edition (CE) |
| **Audience** | CE maintainers, contributors, reviewers, release owners |
| **Status** | Developer ownership runbook · July 2026 |
| **Package** | `rag-protection-proxy` |
| **Scope** | Build, change, test, debug, and release the CE trust surface |
| **Exclusions** | EE implementation, Tier 2/3 operator workflows, private packages |

**Ownership context:** [PRODUCT_OWNERSHIP_GUIDE.md](../../shared/PRODUCT_OWNERSHIP_GUIDE.md)

**CE source truth:** [ARCHITECTURE.md](../../../ENTERPRISE.md) · [DESIGN.md](DESIGN.md) · [FUNCTIONAL_SPECIFICATION.md](FUNCTIONAL_SPECIFICATION.md) · [ADMIN_GUIDE.md](ADMIN_GUIDE.md) · [FEATURE_CATALOG.md](../FEATURE_CATALOG.md) · [Feature tutorials](../learn/README.md)

> This guide tells a developer **where to make a CE change and how to prove it**. The architecture and design guides own system contracts; the functional specification owns required behavior; the admin guide owns operator procedures; and the feature catalog owns capability-level tutorials, commands, and non-claims.

---

## 1. CE ownership boundary

### 1.1 What CE owns

CE owns the standalone, inspectable trust surface:

- FastAPI Tier 1 endpoints for query, ingest, stateless scan, document metadata, tool invocation, audit, health, metrics, and policy reload.
- Demo-token, JWT, and OIDC/JWKS identity resolution plus document ACL enforcement.
- SQLite lexical, Qdrant vector, and hybrid retrieval.
- Query, retrieved-chunk, ingest, citation, and output guardrails.
- Tool policy enforcement and API-driven tool invocation.
- JSONL/in-memory/webhook audit behavior and CE audit analytics.
- The React console shell with exactly five CE workspaces:
  1. **Overview** (`overview`)
  2. **Query Lab** (`query`)
  3. **Documents & Ingest** (`documents`) — ingest / list / delete / quarantine metadata; no preview/approve
  4. **Tool Gateway** (`tools`)
  5. **Audit Log** (`audit`)
- Shipped CE command-line assessment tools under `tools/`.
- CE Docker image, Compose baseline, tests, CI workflows, and CE documentation.

The primary runtime package is:

```text
rag-protection-proxy/rag_protection_proxy/
```

The CE console source is:

```text
console/packages/core/
console/packages/ce/
```

### 1.2 CE non-goals

Do not implement these as CE behavior:

- Tier 2/3 operator APIs or Enterprise route registration.
- Policy form editing, Pattern Lab, policy backup/restore UI, or other EE policy-authoring UX. CE operators edit YAML and call `POST /admin/reload-policy`.
- Connector administration, SCIM administration UI, live source schedulers, or connector panes.
- `pgvector`; it is an EE backend. CE supports `sqlite`, `vector` (Qdrant), and `hybrid`.
- EE React workspaces or compilation of EE pane source into the CE bundle.
- Document quarantine approve-in-place, reject review, body preview, or document inspection. CE supports **metadata list → delete → remediate → re-ingest**.
- Compliance evidence bundles, curated commercial packs, entitlement enforcement, or premium retention governance.
- Multi-replica coordination or a claim of HA.

When a request crosses this boundary, classify it as a seam or EE change before coding. Do not hide an EE dependency behind a CE fallback.

---

## 2. Repository and code map

All paths below are relative to the repository root.

### 2.1 Runtime modules

| Path | CE responsibility | Change when |
|------|-------------------|-------------|
| `rag-protection-proxy/rag_protection_proxy/app.py` | FastAPI app lifecycle, Tier 1 route handlers, auth dependencies, static UI serving, health | Adding/changing a CE endpoint or app-level dependency |
| `rag-protection-proxy/rag_protection_proxy/models.py` | Pydantic API and audit models | A request/response contract changes |
| `rag-protection-proxy/rag_protection_proxy/pipeline.py` | Ordered `run_query()` orchestration | Query flow, early exit, LLM call conditions, or audit flow changes |
| `rag-protection-proxy/rag_protection_proxy/context_builder.py` | Isolation of untrusted retrieved text | Prompt/context boundary changes |
| `rag-protection-proxy/rag_protection_proxy/llm.py` | OpenAI-compatible generation client | Transport, timeout, model request, or response handling changes |
| `rag-protection-proxy/rag_protection_proxy/llm_routing.py` | Classification-to-endpoint routing | LLM egress routing changes |
| `rag-protection-proxy/rag_protection_proxy/acl.py` | User auth, group expansion, document access predicate | Demo/JWT/OIDC user identity or ACL semantics change |
| `rag-protection-proxy/rag_protection_proxy/admin_auth.py` | Operator identity, roles, tenant scope | Admin authorization changes |
| `rag-protection-proxy/rag_protection_proxy/config.py` | Policy/ACL models, loaders, validation, active writable policy path | A policy key, environment override, or validation rule changes |
| `rag-protection-proxy/rag_protection_proxy/tenant_store.py` | Per-tenant store lifecycle | Tenant namespace/store creation changes |
| `rag-protection-proxy/rag_protection_proxy/store.py` | Store protocol, SQLite store, hybrid RRF, factory | Store contract, lexical behavior, hybrid behavior, or backend selection changes |
| `rag-protection-proxy/rag_protection_proxy/vector_store.py` | Qdrant ingest/search and vector ACL filter | Qdrant payload, filter, search, or quarantine behavior changes |
| `rag-protection-proxy/rag_protection_proxy/embeddings.py` | Embedding implementation and cache | Embedding model/backend behavior changes |
| `rag-protection-proxy/rag_protection_proxy/retrieval_trace.py` | Retrieval-decision trace persistence/format | Explainability trace changes |
| `rag-protection-proxy/rag_protection_proxy/audit.py` | Ring buffer, JSONL, webhook, export, filtering, analytics | Audit persistence/query/statistics changes |
| `rag-protection-proxy/rag_protection_proxy/audit_integrity.py` | Hash-chain fields and verification | Tamper-evidence behavior changes |
| `rag-protection-proxy/rag_protection_proxy/otel.py` | Optional OpenTelemetry setup | Tracing changes |

### 2.2 Guardrail modules

| Path | Responsibility |
|------|----------------|
| `rag-protection-proxy/rag_protection_proxy/scanners/base.py` | `Scanner` and `ScannerResult` contract |
| `rag-protection-proxy/rag_protection_proxy/scanners/__init__.py` | Public scanner exports used by pipelines |
| `rag-protection-proxy/rag_protection_proxy/scanners/pii.py` | Regex PII |
| `rag-protection-proxy/rag_protection_proxy/scanners/pii_ner.py` | Optional heuristic NER |
| `rag-protection-proxy/rag_protection_proxy/scanners/secrets.py` | Secret patterns |
| `rag-protection-proxy/rag_protection_proxy/scanners/url_threat.py` | URL/domain/private-range checks |
| `rag-protection-proxy/rag_protection_proxy/scanners/custom_patterns.py` | Policy-defined DLP/secret regexes |
| `rag-protection-proxy/rag_protection_proxy/scanners/prompt_injection.py` | Heuristic injection categories |
| `rag-protection-proxy/rag_protection_proxy/scanners/injection_ml.py` | Optional ML-assisted injection signal |
| `rag-protection-proxy/rag_protection_proxy/guardrails/input_pipeline.py` | Ordered query/chunk/tool-argument scanning |
| `rag-protection-proxy/rag_protection_proxy/guardrails/output_pipeline.py` | Post-generation scanning/redaction |
| `rag-protection-proxy/rag_protection_proxy/guardrails/ingest.py` | Ingest scan and active/quarantine metadata |
| `rag-protection-proxy/rag_protection_proxy/guardrails/risk_scoring.py` | Finding aggregation and ALLOW/CHALLENGE/BLOCK |
| `rag-protection-proxy/rag_protection_proxy/guardrails/citation.py` | Citation overlap, per-claim checks, hard gate |
| `rag-protection-proxy/rag_protection_proxy/guardrails/extraction.py` | Cross-query extraction monitor |
| `rag-protection-proxy/rag_protection_proxy/guardrails/canary.py` | Canary seed/list/detection behavior |
| `rag-protection-proxy/rag_protection_proxy/guardrails/scan.py` | Stateless `/v1/scan` disposition mapping |

CE DLP is regex, custom patterns, secrets/URL checks, and optional heuristic NER. Do not describe it as vendor semantic DLP.

### 2.3 Tool gateway modules

| Path | Responsibility |
|------|----------------|
| `rag-protection-proxy/rag_protection_proxy/tools_gateway/policy.py` | `tool_policy.yaml` parsing and validation |
| `rag-protection-proxy/rag_protection_proxy/tools_gateway/registry.py` | Registry construction and description-injection scan |
| `rag-protection-proxy/rag_protection_proxy/tools_gateway/router.py` | Identity, allowlist, argument, scan, invoke, challenge, audit flow |
| `rag-protection-proxy/rag_protection_proxy/tools_gateway/backends/__init__.py` | Backend argument models and handler maps |
| `rag-protection-proxy/rag_protection_proxy/tools_gateway/backends/mcp_shim.py` | HTTP shim to the isolated MCP backend |
| `rag-protection-proxy/rag_protection_proxy/tools_gateway/challenge_queue.py` | In-memory pending tool challenges |
| `rag-protection-proxy/config/tool_policy.yaml` | Default CE tool definitions |

Tool invocation is API-driven through `POST /v1/tools/invoke`. The CE **Tool Gateway** workspace displays policy and challenge state; it is not a general tool execution console.

### 2.4 Console modules

| Path | Responsibility |
|------|----------------|
| `console/packages/core/src/api/client.ts` | Shared browser API client |
| `console/packages/core/src/auth/AuthContext.tsx` | User/admin token and tenant state |
| `console/packages/core/src/workspace/registry.ts` | Workspace registration/listing contract |
| `console/packages/core/src/layout/AppShell.tsx` | Shared application shell |
| `console/packages/core/src/layout/WorkspaceNavContext.tsx` | Active workspace navigation |
| `console/packages/core/src/enterprise/loadEnterpriseUi.ts` | Optional runtime EE bundle probe; CE must survive failure |
| `console/packages/ce/src/main.tsx` | Registers exactly five CE workspaces and mounts providers |
| `console/packages/ce/src/workspaces/DocumentsIngestPane.tsx` | CE Documents & Ingest (ingest/list/delete; no EE review UX) |
| `console/packages/ce/src/workspaces/OverviewPane.tsx` | Overview workspace |
| `console/packages/ce/src/workspaces/QueryLabPane.tsx` | Query workspace |
| `console/packages/ce/src/workspaces/ToolGatewayPane.tsx` | Tool policy/challenge workspace |
| `console/packages/ce/src/workspaces/AuditLogPane.tsx` | Audit workspace |
| `console/packages/ce/src/audit/` | Audit table, drawer, integrity, analytics, formatting |
| `console/packages/ce/src/retrieval/` | Retrieval trace rendering |
| `console/packages/ce/src/refresh/RefreshContext.tsx` | Shared refresh tick and auto-refresh state |

### 2.5 Build, deploy, tests, and tools

| Path | Responsibility |
|------|----------------|
| `tools/setup_venv.sh` | Create/repair repository `.venv` (Python 3.11+; installs CE requirements + editable proxy). See [LOCAL_SETUP.md](LOCAL_SETUP.md) |
| `tools/run_tests.sh` | Run proxy pytest with repository `.venv` |
| `tools/build_ce.sh` | Build core + CE console into the proxy static tree |
| `tools/docker_start.sh` / `tools/docker_stop.sh` | Compose lifecycle |
| `tools/docker_build.sh` | CE image build |
| `tools/smoke_rag_proxy.sh` | Running-stack CE smoke |
| `tools/workflow_ce_internal.sh` | CE-internal validation workflow |
| `tools/workflow_seam.sh` | Coupled CE/EE seam workflow |
| `rag-protection-proxy/tests/` | Proxy unit/in-process integration tests |
| `console/packages/core/src/**/*.test.ts(x)` | Shared console tests |
| `console/packages/ce/src/**/*.test.ts(x)` | CE console tests |
| `tools/<tool_package>/tests/` | Standalone CLI tests |
| `.github/workflows/` | CI and security gates |

---

## 3. CE-only development setup

**Canonical install (Python version, libraries, activate, verify, troubleshooting):** [LOCAL_SETUP.md](LOCAL_SETUP.md).

### 3.1 Prerequisites

- Python **3.11 or newer**; **CI and the CE Docker image use 3.13**. Prefer 3.13 locally. `tools/setup_venv.sh` refuses anything older than 3.11.
- Node.js **20** or newer (`console/package.json` `engines`).
- npm with the committed `console/package-lock.json`.
- Docker Desktop for image, Compose, Qdrant, MCP, and live-stack checks.
- An OpenAI-compatible LLM endpoint only for query paths that reach generation — [LLM_BACKENDS.md](LLM_BACKENDS.md).

### 3.2 Create the repository virtualenv

From the repository root:

```bash
bash tools/setup_venv.sh
source .venv/bin/activate
```

`tools/setup_venv.sh` creates repo-root `.venv`, installs the files below, and `pip install -e rag-protection-proxy`:

| File | Packages (minimums in the file) |
|------|---------------------------------|
| `rag-protection-proxy/requirements.txt` | fastapi, uvicorn, httpx, pyyaml, pydantic, PyJWT, prometheus-client, qdrant-client, sentence-transformers |
| `rag-protection-proxy/requirements-dev.txt` | pytest, pytest-asyncio (and `-r` examples) |
| `examples/requirements.txt` | langchain-core, pinecone |

Pin 3.13 when creating a **new** venv: `rm -rf .venv && PYTHON=python3.13 bash tools/setup_venv.sh`.

Keep this environment CE-only:

- Do not install a `rag-protection-enterprise` wheel.
- Do not add a private EE checkout to `PYTHONPATH`.
- In this monorepo, do not run `tools/dev_install_ee.sh` if you intend to match public CE CI.

Prove the optional EE package is absent:

```bash
python - <<'PY'
import importlib.util
assert importlib.util.find_spec("rag_protection_enterprise") is None
print("CE-only Python environment confirmed")
PY
```

Then prove the seam:

```bash
bash tools/run_tests.sh -q tests/test_ce_ee_seams.py
```

### 3.3 Install console dependencies

For repeatable lockfile-exact setup:

```bash
cd console
npm ci
cd ..
```

Use `npm install` only when intentionally changing dependencies and `console/package-lock.json`.

---

## 4. Build the CE console

The Dockerfile does not run npm. Build the browser bundle on the host:

```bash
bash tools/build_ce.sh
```

Output:

```text
rag-protection-proxy/rag_protection_proxy/ui/static/ce/
```

CI-style local build:

```bash
bash tools/build_ce.sh --ci --typecheck --test
```

Individual console checks:

```bash
cd console
npm run typecheck
npm run test
npm run build
```

Run the Vite development server in forced CE-only mode:

```bash
cd console
npm run dev:ce-only
```

The production shell also accepts `?ee=off` to skip the optional Enterprise UI probe while debugging.

---

## 5. Run CE

### 5.1 Run on the host

The loader defaults are relative paths, so start the service from `rag-protection-proxy/`:

```bash
source .venv/bin/activate
cd rag-protection-proxy
export RAG_LLM_BASE_URL=http://localhost:12434/engines/v1
export RAG_LLM_MODEL=ai/gemma3-qat
python -m rag_protection_proxy
```

Equivalent explicit uvicorn command:

```bash
uvicorn rag_protection_proxy.app:app --host 0.0.0.0 --port 8090 --reload
```

Open:

```text
http://localhost:8090/ui
http://localhost:8090/docs
http://localhost:8090/health
http://localhost:8090/metrics
```

For host development, state defaults to `rag-protection-proxy/data/` because the process working directory is `rag-protection-proxy/`.

### 5.2 Run with Docker

From the repository root:

```bash
bash tools/build_ce.sh
bash tools/docker_start.sh
bash tools/smoke_rag_proxy.sh
```

Stop:

```bash
bash tools/docker_stop.sh
```

After a bind-mounted Python edit:

```bash
docker compose restart rag-protection-proxy
```

After a React edit:

```bash
bash tools/build_ce.sh
```

The static output is inside the bind-mounted Python package, so a CE console rebuild does not require a Docker image rebuild. Rebuild the image after dependency or Dockerfile changes:

```bash
bash tools/docker_build.sh
```

### 5.3 Run Qdrant

Qdrant is CE. Start its Compose profile and select the vector backend:

```bash
RAG_STORE_BACKEND=vector docker compose --profile qdrant up -d --build
```

The container uses `RAG_QDRANT_URL=http://qdrant:6333` by default. For a host process:

```bash
docker compose --profile qdrant up -d qdrant
export RAG_STORE_BACKEND=vector
export RAG_QDRANT_URL=http://localhost:6333
```

Use `RAG_STORE_BACKEND=hybrid` for lexical + Qdrant reciprocal-rank fusion. `RAG_STORE_BACKEND=pgvector` is **not CE** and must raise the actionable Enterprise `ImportError`.

### 5.4 Run the MCP Layer 2 backend

```bash
bash tools/docker_start.sh --mcp-tools --smoke
bash tools/docker_stop.sh --mcp-tools
```

This adds the isolated MCP filesystem backend. Invocation still enters through the CE proxy API:

```text
POST /v1/tools/invoke
```

---

## 6. Configuration, policy, and data state

### 6.1 Configuration sources

| Path or variable | Purpose |
|------------------|---------|
| `rag-protection-proxy/config/policy.yaml` / `RAG_POLICY_FILE` | Shipped policy source |
| `rag-protection-proxy/config/acl_policy.yaml` / `RAG_ACL_FILE` | Demo users, JWT/OIDC, hierarchy, admin users |
| `rag-protection-proxy/config/tool_policy.yaml` / `RAG_TOOL_POLICY_FILE` | Tool registry, allowlists, backend selection |
| `rag-protection-proxy/config/sample_documents.json` / `RAG_SAMPLE_DOCS` | Seed corpus |
| `RAG_DATA_DIR` | SQLite, active writable policy fallback, audit files/caches |
| `RAG_POLICY_WRITABLE_FILE` | Explicit active writable policy |
| `RAG_TOOL_POLICY_WRITABLE_FILE` | Explicit active writable tool policy |
| `RAG_STORE_BACKEND` | `sqlite`, `vector`, or `hybrid` in CE |
| `RAG_AUDIT_FILE` | Persistent audit JSONL |
| `RAG_LLM_BASE_URL`, `RAG_LLM_MODEL`, `RAG_LLM_API_KEY` | OpenAI-compatible generation endpoint |

### 6.2 Active policy state

At startup, `app.py` calls:

```text
config.ensure_writable_policy_file()
config.load_policy(active_path)
```

The path rules in `config.py` are:

1. `RAG_POLICY_WRITABLE_FILE`, when set.
2. The source `RAG_POLICY_FILE`, when writable.
3. Otherwise `RAG_DATA_DIR/policy.yaml`.

Docker mounts `/app/config` read-only and sets:

```text
RAG_POLICY_FILE=/app/config/policy.yaml
RAG_POLICY_WRITABLE_FILE=/data/policy.yaml
```

Therefore the first Docker start seeds host `data/policy.yaml`; later restarts load that persisted copy. Editing `rag-protection-proxy/config/policy.yaml` does **not** override an existing `data/policy.yaml`.

The tool policy uses the parallel helpers in `tools_gateway/policy.py`. When its configured source is read-only, `ensure_writable_tool_policy_file()` seeds `RAG_DATA_DIR/<source filename>` (normally `data/tool_policy.yaml`, or `data/tool_policy.mcp.yaml` for the MCP overlay). Later loads and reloads use that persisted copy. `RAG_TOOL_POLICY_WRITABLE_FILE` overrides the fallback.

CE reloads YAML through:

```bash
curl -sS -X POST http://localhost:8090/admin/reload-policy \
  -H 'Authorization: Bearer rag-admin-demo-key'
```

Reload refreshes policy, ACL, and tool policy state. CE does not provide the EE policy-editing UI. Edit the active YAML deliberately, validate it, then reload.

### 6.3 Runtime data

Docker bind-mounts repository `data/` at `/data`:

- `data/policy.yaml` — persisted active Docker policy.
- `data/tool_policy.yaml` — persisted active default tool policy when the source mount is read-only.
- `data/audit.jsonl` — default Compose audit sink.
- SQLite database files — tenant store state when using SQLite/hybrid.
- Other runtime caches or backup/dead-letter files configured under `RAG_DATA_DIR`.

Qdrant state is in the named `qdrant-data` volume, not in SQLite. Resetting one backend does not reset the other. Rebuild does **not** migrate SQLite → Qdrant; hybrid list/count still read SQLite. Full operator FAQ: [QDRANT_CONFIGURATION_AND_TESTING.md](../../product/QDRANT_CONFIGURATION_AND_TESTING.md).

### 6.4 ACL placement differs by backend

This distinction is a security invariant:

- **SQLite:** `store.py` loads rows, rejects quarantined rows, checks `user_can_access_document(...)`, and only then scores authorized text. ACL is application-side **before scoring**.
- **Qdrant:** `vector_store.py` builds and sends an ACL metadata filter inside the Qdrant search query. Unauthorized points must not be returned as candidates.
- **Hybrid:** both legs enforce their own ACL rule before fusion.

Never “simplify” this into a post-retrieval or prompt-only filter.

---

## 7. Request change points

### 7.1 Query request

`POST /v1/query` enters at:

```text
rag-protection-proxy/rag_protection_proxy/app.py
  query()
    → rag_protection_proxy.pipeline.run_query()
```

Change points, in order:

1. **Contract:** `models.py` — `QueryRequest`, `QueryResponse`, related nested models.
2. **Authentication and tenant:** `app.py` — `_require_auth()`, `_store_for_auth()`, `_policy_for_auth()`.
3. **User-query scan:** `pipeline.py` → `guardrails/input_pipeline.py`.
4. **Retrieval and trace:** `pipeline.py`, `store.py`, `vector_store.py`, `retrieval_trace.py`.
5. **Canary/extraction behavior:** `guardrails/canary.py`, `guardrails/extraction.py`.
6. **Per-chunk scan:** `guardrails/input_pipeline.py`.
7. **LLM route and context:** `llm_routing.py`, `context_builder.py`, `llm.py`.
8. **Citation/output:** `guardrails/citation.py`, `guardrails/output_pipeline.py`.
9. **Audit:** `pipeline.py` and `audit.py`.
10. **Console:** `console/packages/ce/src/workspaces/QueryLabPane.tsx` and retrieval components.

Preserve the no-LLM rule: blocked query, empty ACL-filtered retrieval, severe extraction decision, or all blocked chunks must terminate before `llm.py`.

### 7.2 Ingest request

`POST /v1/ingest` enters at `app.py::ingest()`:

1. `models.py::DocumentIngestRequest` validates the request.
2. `admin_auth.py` and `app.py` enforce `ingest_admin` plus tenant scope.
3. `guardrails/ingest.py` scans and chooses active/quarantine metadata.
4. `store.py` or `vector_store.py` writes chunks and metadata.
5. `audit.py` records the ingest decision.

Quarantined CE documents follow:

```text
GET /v1/documents/quarantined   # metadata only
DELETE /v1/documents/{id}
POST /v1/ingest                 # remediated content
```

Do not add CE document body preview or approve/reject-in-place. Canary documents are protected from deletion and return HTTP 409.

### 7.3 Tool request

`POST /v1/tools/invoke` enters at `app.py::tools_invoke()`:

1. `models.py::ToolInvokeRequest`.
2. `acl.py` user identity.
3. `tools_gateway/policy.py` loaded policy.
4. `tools_gateway/registry.py` tool lookup and description scan.
5. `tools_gateway/router.py` group, size, pattern, domain, schema, and input-scan checks.
6. `tools_gateway/backends/` handler.
7. `audit.py`, normally with `kind="tool_invoke"`.

The CE console does not replace this API path. Add API tests before changing the policy-oriented Tool Gateway pane.

---

## 8. How to add CE behavior

### 8.1 Add a scanner

1. Add `rag-protection-proxy/rag_protection_proxy/scanners/<name>.py`.
2. Implement `scanners.base.Scanner.scan(text) -> ScannerResult`.
3. Use stable `Finding.scanner` and `Finding.category` values; bound severity to `0.0..1.0`.
4. Export the scanner from `scanners/__init__.py`.
5. Insert it at the intended point in `guardrails/input_pipeline.py` and/or `guardrails/output_pipeline.py`.
6. If configurable, add dataclass fields, YAML loading, defaults, validation, and environment behavior in `config.py` plus `config/policy.yaml`.
7. Decide whether sanitized text flows to later scanners and count redactions consistently.
8. Add direct scanner tests and pipeline aggregation/threshold tests.
9. Update guardrail docs and the CE feature catalog if externally observable.

Do not instantiate a heavyweight model per request without documenting and testing the performance effect.

### 8.2 Add or change a guardrail

1. Define the policy and threat contract in `config.py`.
2. Put reusable control logic under `guardrails/`; keep `app.py` thin.
3. Wire it into the correct ordered path in `pipeline.py`, `guardrails/ingest.py`, or `guardrails/output_pipeline.py`.
4. Define fail-open/fail-closed behavior explicitly.
5. Record a stable audit kind/detail without raw sensitive text.
6. Test ALLOW, CHALLENGE, BLOCK, disabled, malformed config, and no-LLM early exits.
7. Test SQLite/Qdrant parity if retrieval state changes.

### 8.3 Add a store backend

1. Implement every method required by `store.DocumentStoreBackend`.
2. Add selection to `store.create_document_store()`.
3. Namespace state by `tenant_id`.
4. Enforce ACL before unauthorized text enters scored candidates.
5. Exclude `metadata.status=quarantined`.
6. Preserve list, count, status, delete, detail, and quarantine behavior used by Tier 1 APIs.
7. Add factory tests, backend unit tests, and integration parity tests.
8. Document environment variables and operational persistence.

A CE backend must be implemented and testable without importing EE. Do not make `pgvector` CE; its current factory branch intentionally delegates to Enterprise and raises an actionable `ImportError` when EE is absent.

### 8.4 Add a CE API endpoint

1. Add request/response models to `models.py` rather than accepting an unbounded dictionary when a stable contract exists.
2. Add the route to `app.py`.
3. Select `_require_auth`, `_require_admin_role(...)`, or `_require_admin_any()` deliberately.
4. Apply `_guard_admin_tenant(...)` for tenant-scoped operator data.
5. Return 401 for missing/invalid identity, 403 for authenticated-but-insufficient role/scope, and 404 only for absent resources/routes.
6. Record audit state where the action changes security or data.
7. Add tests to `tests/test_ui_and_admin.py` or a focused `tests/test_<area>.py`.
8. Add the Tier 1 endpoint to architecture/FS/admin/catalog docs.
9. Add seam assertions if its path could overlap an EE namespace.

### 8.5 Add or change a CE console workspace

Current CE product truth is exactly **five** workspaces registered in `console/packages/ce/src/main.tsx`. Adding another CE workspace is a product-surface and seam change, not a routine component addition.

For an approved change:

1. Add `console/packages/ce/src/workspaces/<Name>Pane.tsx`.
2. Use `WorkspaceComponentProps` from `console/packages/core/src/workspace/registry.ts`.
3. Add API methods/types to shared core only when edition-neutral; keep CE presentation in `packages/ce`.
4. Register the pane in `console/packages/ce/src/main.tsx` with `edition: "ce"` and a unique order.
5. Add `<Name>Pane.test.tsx`.
6. Update workspace registry/navigation tests.
7. Verify `VITE_EE=off` and missing `ee-ui.js` behavior.
8. Update architecture, design, FS, user/admin guides, and both feature catalogs so the documented workspace count stays truthful.

Never import private EE pane source from `console/packages/ce` or `console/packages/core`.

### 8.6 Add an audit kind

`models.AuditEvent.kind` is a string, not an enum. To add a kind safely:

1. Choose a stable snake_case value.
2. Emit `AuditEvent(...)` at the decision point.
3. Keep `detail` bounded and free of raw secrets, tokens, or unredacted document content.
4. Include `subject`, `tenant_id`, `source`, decision, risk, and findings when meaningful.
5. Test in-memory query/filter behavior in `tests/test_audit.py`.
6. Test JSONL export/warm behavior if persisted.
7. Update `console/packages/ce/src/audit/types.ts`, `format.ts`, filters, charts, and tests if the UI needs special labeling or grouping.
8. Check integrity-chain behavior in `tests/test_audit_integrity.py`.
9. Update SIEM field/detection docs when downstream consumers need the new kind.

Unknown kinds should remain renderable; avoid UI code that crashes on an unrecognized string.

### 8.7 Add a tool backend

1. Add a validated Pydantic argument model and handler under `tools_gateway/backends/`.
2. Register both in `BACKEND_HANDLERS` and `BACKEND_ARG_MODELS`.
3. Add a policy entry/schema in `config/tool_policy.yaml`.
4. Keep authorization and argument scanning in `tools_gateway/router.py`; do not bypass it in the handler.
5. Add unit tests in `tests/test_tools_gateway.py`; add transport tests such as `tests/test_mcp_shim.py` when applicable.
6. Invoke it in validation through `POST /v1/tools/invoke`.

### 8.8 Add a CLI tool or subcommand

For a new command in an existing tool:

1. Extend `tools/<package>/cli.py`.
2. Keep `main(argv) -> int` testable.
3. Define documented exit codes.
4. Add tests under `tools/<package>/tests/`.
5. Update that tool's README and path-filtered workflow if present.

For a new standalone tool, follow the shipped package pattern:

```text
tools/<package>/pyproject.toml
tools/<package>/__init__.py
tools/<package>/__main__.py
tools/<package>/cli.py
tools/<package>/tests/
tools/<hyphenated-wrapper>
```

Add `[project.scripts]` in the tool `pyproject.toml`, a repository wrapper under `tools/`, unit tests, and a path-filtered `.github/workflows/<tool>.yml` when it is a CI capability. A CE CLI must not require EE imports for its baseline operation; label optional private integrations explicitly.

---

## 9. Tests to add

Match the test to the changed contract:

| Change | Required test location |
|--------|------------------------|
| Scanner | Focused `rag-protection-proxy/tests/test_<scanner>.py` plus pipeline test |
| Query orchestration | `tests/test_rag_protection.py`, `tests/test_p1.py`, or focused feature test |
| Ingest/quarantine | `tests/test_p1.py` and backend parity where relevant |
| SQLite/store factory | `tests/test_store_factory.py`, `tests/test_rag_protection.py` |
| Qdrant/ACL | `tests/test_vector_store.py`, `tests/integration/test_vector_pipeline.py` |
| LLM transport/routing | `tests/test_llm_fallback.py`, `tests/test_llm_routing.py` |
| Identity | `tests/test_oidc_auth.py`, `tests/test_oidc_admin.py` |
| CE API/admin/UI static | `tests/test_ui_and_admin.py` |
| Audit | `tests/test_audit.py`, `tests/test_audit_debug.py`, `tests/test_audit_integrity.py` |
| Tool gateway | `tests/test_tools_gateway.py`, `tests/test_tools_challenge_queue.py`, `tests/test_mcp_shim.py` |
| CE/EE boundary | `tests/test_ce_ee_seams.py` |
| Core console | Adjacent `console/packages/core/src/**/*.test.ts(x)` |
| CE console | Adjacent `console/packages/ce/src/**/*.test.ts(x)` |
| CLI | `tools/<package>/tests/` |

Minimum cases for a security-sensitive behavior:

- Happy path.
- Unauthorized identity and insufficient role.
- Tenant isolation.
- Invalid/malformed input.
- Boundary thresholds.
- Disabled-policy behavior.
- Audit event contents without sensitive leakage.
- Restart/persistence behavior when stateful.
- SQLite and Qdrant behavior when retrieval is affected.
- CE-only behavior with no Enterprise package installed.

---

## 10. Exact validation commands

Run commands from the repository root unless a `cd` is shown.

### 10.1 Focused proxy test

```bash
bash tools/run_tests.sh -q tests/test_<area>.py
```

### 10.2 Full non-live CE proxy suite

```bash
bash tools/run_tests.sh -q -m "not live"
```

### 10.3 In-process integration suite

```bash
bash tools/run_tests.sh -q -m "integration and not live"
```

### 10.4 CE/EE seam proof

```bash
bash tools/run_tests.sh -q tests/test_ce_ee_seams.py
```

### 10.5 Console typecheck, tests, and build

```bash
cd console
npm ci
npm run typecheck
npm run test
npm run build
cd ..
```

Or:

```bash
bash tools/build_ce.sh --ci --typecheck --test
```

### 10.6 CE image and running-stack smoke

```bash
bash tools/build_ce.sh
docker compose build rag-protection-proxy
bash tools/docker_start.sh --no-build
bash tools/smoke_rag_proxy.sh
bash tools/docker_stop.sh
```

### 10.7 Live integration tests

```bash
docker compose up -d --build --wait
RUN_INTEGRATION=1 RAG_BASE_URL=http://localhost:8090 \
  bash tools/run_tests.sh -q -m live
docker compose down
```

GitHub Actions uses `compose.ci.yml` instead — hosted runners have no Model Runner plugin.

### 10.8 Full CE internal workflow

```bash
bash tools/workflow_validate_commit.sh ce
```

### 10.9 Config gate

```bash
bash tools/rag-scan validate \
  --acl rag-protection-proxy/config/acl_policy.yaml

bash tools/rag-scan validate \
  --acl rag-protection-proxy/config/acl_policy.prod.yaml

bash tools/rag-scan check \
  --env prod \
  --acl rag-protection-proxy/config/acl_policy.prod.yaml \
  --severity critical
```

Run tool-specific tests for a changed tool, for example:

```bash
python -m pytest tools/rag_scan/tests -q
python -m pytest tools/rag_ground/tests -q
python -m pytest tools/inj_bench/tests -q
python -m pytest tools/mcp_lint/tests -q
```

---

## 11. CE-only seam rules

### 11.1 Allowed seam pattern

CE may expose an optional hook or capability probe that remains fully functional when EE is absent. Existing examples include:

- `app.py` catching `ImportError` around EE UI mounting.
- `app.state` hooks checked with `getattr(..., None)`.
- `/health` reporting whether Enterprise registered.
- `store.create_document_store()` importing the EE pgvector factory only when `RAG_STORE_BACKEND=pgvector`.
- The browser dynamically probing `ee-ui.js` while preserving four-workspace CE fallback.

The CE default path must not import, instantiate, configure, or require EE.

### 11.2 Prohibited dependencies

Do not:

- Add `rag-protection-enterprise` to CE requirements or `pyproject.toml`.
- Import `rag_protection_enterprise` at unconditional module import time.
- Copy EE modules, routes, entitlement logic, or pane source into CE.
- Add private repository paths to CE Docker build context or CE CI.
- Make a Tier 1 endpoint call a Tier 2/3 endpoint to complete baseline behavior.
- Return a placeholder 200 for an absent EE route. CE-only Tier 2/3 routes must remain unregistered and return 404.
- Register EE workspaces as disabled or greyed-out CE navigation.
- Make CE tests pass only when a sibling Enterprise checkout exists.
- Implement pgvector under the CE package.

### 11.3 Seam-change trigger

Treat a change as a seam when it alters any of:

- A callable, hook, dependency object, route namespace, or model consumed by EE.
- The optional import/registration sequence.
- `/health` Enterprise capability fields.
- CE static paths or dynamic EE bundle loading.
- Store factory behavior used by an EE backend.
- A Tier 1 contract on which EE depends.

Run the seam workflow and coordinate the CE tag/EE pin rather than releasing it as CE internal.

---

## 12. Debugging playbooks

### 12.1 HTTP 404 versus 401/403

Start with:

```bash
curl -sS http://localhost:8090/health
curl -sS http://localhost:8090/openapi.json > /tmp/rag-openapi.json
```

- **404:** route is not registered, path/method is wrong, or it is an EE Tier 2/3 route on CE. Confirm it exists in OpenAPI and `app.py`.
- **401:** missing or invalid bearer token. Check `RAG_ADMIN_API_KEY`, demo tokens, JWT signature, or OIDC settings.
- **403:** identity was accepted but lacks a required group, admin role, or tenant scope. Check `GET /v1/auth/me` or `GET /admin/auth/me`.
- Do not “fix” an expected CE 404 by registering an EE route.

Useful calls:

```bash
curl -sS http://localhost:8090/v1/auth/me \
  -H 'Authorization: Bearer employee-demo-token'

curl -sS http://localhost:8090/admin/auth/me \
  -H 'Authorization: Bearer rag-admin-demo-key'
```

### 12.2 Policy persisted state

Symptoms: a config edit has no effect, reload returns old values, or Docker differs from host.

1. Check Compose environment:

   ```bash
   docker compose exec rag-protection-proxy env | \
     rg 'RAG_(POLICY|ACL|TOOL_POLICY|DATA_DIR)'
   ```

2. Inspect whether `data/policy.yaml` already exists. In Docker it is normally the active file.
3. Edit the active file or deliberately remove/reset it only after preserving needed state.
4. Call `POST /admin/reload-policy`.
5. Read the response and service logs for `PolicyValidationError`.
6. Remember that reload also refreshes ACL and tool policy; it does not migrate existing document metadata.

CE reloads policy; policy editing UI is EE.

### 12.3 LLM URL or model failure

Symptoms: query returns an LLM error, connection refused, timeout, or Docker host URL fails.

1. Check `/health` for `llm_model`.
2. Confirm the query retrieved an authorized, unblocked chunk; otherwise no LLM call is expected.
3. Compare host and container URLs:
   - Host process commonly uses `http://localhost:12434/engines/v1`.
   - Docker defaults to `http://model-runner.docker.internal/engines/v1`.
4. Check effective environment:

   ```bash
   docker compose exec rag-protection-proxy env | rg 'RAG_LLM'
   ```

5. Test the endpoint from the same network namespace as the proxy.
6. Check classification routing in `policy.yaml` and `llm_routing.py`; a route may select a different endpoint.
7. Reproduce with `tests/test_llm_fallback.py` or `tests/test_llm_routing.py`.

### 12.4 Stale or missing UI

Symptoms: old JavaScript, blank `/ui`, missing recent pane changes, or unexpected EE workspaces.

1. Rebuild:

   ```bash
   bash tools/build_ce.sh
   ```

2. Verify the served build headers:

   ```bash
   curl -sSI http://localhost:8090/ui
   ```

3. Hard-refresh the browser and disable cache in developer tools.
4. Confirm output exists under `rag-protection-proxy/rag_protection_proxy/ui/static/ce/`.
5. If Docker is running, confirm the source bind mount is present and restart the proxy if needed.
6. Force CE-only mode with `/ui?ee=off` or `npm run dev:ce-only`.
7. Confirm `console/packages/ce/src/main.tsx` still registers exactly five CE workspaces.

### 12.5 Store/backend failures

Symptoms: documents disappear, Qdrant connection errors, ACL mismatch, or backend switches appear ineffective.

1. Check `/health.store_backend`.
2. Confirm `RAG_STORE_BACKEND` is one of `sqlite`, `vector`, or `hybrid`.
3. For Qdrant:

   ```bash
   curl -sS http://localhost:6333/healthz
   docker compose ps qdrant
   ```

4. Confirm the host uses `localhost:6333` and the proxy container uses `qdrant:6333`.
5. Remember backend state is separate: SQLite files and the Qdrant volume do not mirror automatically.
6. Inspect tenant IDs in `/health`; each tenant has separate store state/collection naming.
7. Run:

   ```bash
   bash tools/run_tests.sh -q tests/test_store_factory.py tests/test_vector_store.py
   bash tools/run_tests.sh -q tests/integration/test_vector_pipeline.py
   ```

8. If `pgvector` is selected in CE, the correct fix is configuration or installing EE—not adding a CE fallback.

### 12.6 ACL discrepancy: Qdrant versus SQLite

If one backend exposes or hides different results:

1. Compare document `allowed_groups`, caller effective groups, tenant, and quarantine status.
2. In SQLite, inspect `store.py` ordering: quarantine check → `user_can_access_document` → score.
3. In Qdrant, inspect `vector_store.build_acl_filter()` and the filter passed into search.
4. In hybrid, prove both legs independently filter before RRF.
5. Add a parity case to `tests/integration/test_vector_pipeline.py`; do not normalize behavior after LLM context construction.

### 12.7 Audit missing, stale, or malformed

1. Check `/health.audit` for buffer, file sink, retention, webhook, and integrity status.
2. Confirm `RAG_AUDIT_FILE`; Docker normally uses `/data/audit.jsonl`.
3. Generate a known query/scan/tool event.
4. Query:

   ```bash
   curl -sS 'http://localhost:8090/admin/audit/events?limit=20' \
     -H 'Authorization: Bearer rag-admin-demo-key'
   ```

5. Verify persistent export:

   ```bash
   curl -sS 'http://localhost:8090/admin/audit/export?limit=20' \
     -H 'Authorization: Bearer rag-admin-demo-key'
   ```

6. For integrity:

   ```bash
   curl -sS http://localhost:8090/admin/audit/integrity/verify \
     -H 'Authorization: Bearer rag-admin-demo-key'
   ```

7. Check retention, file permissions, invalid JSONL warnings, webhook retries, and dead-letter configuration.
8. Do not put raw secrets into `detail` to make debugging easier; use opt-in bounded audit debug previews.

### 12.8 Quarantine confusion

- `GET /v1/documents` is user-ACL scoped and excludes quarantined content from retrieval.
- `GET /v1/documents/quarantined` is admin metadata-only visibility.
- CE has no document approve or body-preview endpoint.
- Delete the quarantined document, remediate externally, and re-ingest it.
- A canary deletion returning 409 is intentional.

---

## 13. CI workflows

### 13.1 Main CI

`.github/workflows/ci.yml` runs on pushes to `main`/`develop` and PRs to `main`:

- **Community Edition (no EE):** Python 3.13, CPU torch, CE dependencies, non-live pytest, in-process integration tests.
- **Operator console (core + CE):** Node 20, `npm ci`, build console-core, typecheck, Vitest, build.
- **Live stack integration (CE):** `compose.ci.yml` (no Docker Model Runner) and `pytest -m live`.

This is the primary required signal for a CE runtime or console change.

### 13.2 Path-filtered CE tool gates

| Workflow | Gate |
|----------|------|
| `.github/workflows/rag-scan.yml` | Dev/prod ACL load and critical production-config scan |
| `.github/workflows/rag-ground.yml` | Grounding tool tests and example JUnit artifact |
| `.github/workflows/rag-injbench.yml` | Injection benchmark tests and committed baseline regression |

When a runtime module affects one of these tools, update the workflow path filters so changes cannot bypass its gate.

### 13.3 Security workflow

`.github/workflows/security.yml` runs scheduled and change-triggered dependency, static-analysis, container, and secret scans. Dependency, Python, requirements, and Docker changes must account for this workflow in addition to main CI.

### 13.4 CI ownership rule

Do not weaken a gate, add `continue-on-error`, or narrow path filters merely to land a failing change. Fix the implementation/test or document and review an intentional baseline change.

---

## 14. Release and change workflow

### 14.1 Classify before implementation

**CE internal** means the externally consumed CE/EE seam is unchanged. Examples:

- Scanner implementation behind the existing pipeline contract.
- CE pane bug fix.
- Audit formatting fix that preserves the event contract.
- SQLite or Qdrant fix under the existing store protocol.
- Documentation-only CE correction.

**Seam change** means EE consumers, optional registration, shared models/routes, static loading, store factories, or CE pin compatibility can change.

### 14.2 CE-internal workflow

Validate:

```bash
bash tools/workflow_validate_commit.sh ce
```

For a focused iteration, run the smallest relevant tests first, then the full non-live suite, console checks if applicable, and Docker smoke for runtime/deployment changes.

Use a CE-only branch/PR. Do not update an EE pin for a genuinely internal change.

### 14.3 Seam workflow

Read the ownership process in [PRODUCT_OWNERSHIP_GUIDE.md](../../shared/PRODUCT_OWNERSHIP_GUIDE.md), then use:

```bash
bash tools/workflow_validate_commit.sh seam --help
```

A seam release requires:

1. CE contract change and seam tests.
2. Full CE validation.
3. New CE release tag (`vX.Y.Z-ce`).
4. EE `CE_PIN` update to that exact tag.
5. EE validation against the pinned CE checkout, not an arbitrary sibling working tree.
6. Coordinated EE release/tag where required.
7. Both docs sets updated for the resulting boundary.

Never point EE at an untagged CE commit for a release.

### 14.4 Before requesting review

```bash
git status --short
git diff --check
bash tools/workflow_validate_commit.sh ce
```

For seam work, replace the last command with the seam workflow and include the CE tag/EE pin plan in the review description.

---

## 15. Documentation update checklist

For any externally observable CE change, check:

- [ ] `docs/editions/community/ARCHITECTURE.md` — components, sequences, endpoint/store/workspace map.
- [ ] `docs/editions/community/DESIGN.md` — principles, contracts, extension points, non-goals.
- [ ] `docs/editions/community/FUNCTIONAL_SPECIFICATION.md` — normative behavior and acceptance criteria.
- [ ] `docs/editions/community/ADMIN_GUIDE.md` — configuration, deployment, operation, troubleshooting.
- [ ] `docs/editions/community/USER_GUIDE.md` — end-user/operator workflow where applicable.
- [ ] `docs/editions/community/FEATURE_CATALOG.md` — canonical capability behavior, commands, validation, limitations.
- [ ] `docs/editions/community/learn/README.md` and the relevant split part — internal business context and non-claims.
- [ ] Guardrail, tool, SIEM, or product deep dive owning the changed detail.
- [ ] API examples and environment-variable reference.
- [ ] CE/EE wording: Tier, entitlement, workspace count, route absence, backend edition.

Accuracy checks:

- [ ] CE console still has exactly five workspaces unless an approved product-surface change updates all source truth.
- [ ] Tool invoke is described as API-driven.
- [ ] Quarantine is metadata list/delete/re-ingest, with no CE document approve/preview claim.
- [ ] CE policy operation is YAML edit + reload; editing UI is EE.
- [ ] pgvector is EE.
- [ ] Qdrant ACL is in the vector query; SQLite ACL is application-side before scoring.
- [ ] DLP is not overclaimed as semantic DLP.
- [ ] Commands use current repository paths.

---

## 16. Developer ownership checklist

### Understand

- [ ] Read [PRODUCT_OWNERSHIP_GUIDE.md](../../shared/PRODUCT_OWNERSHIP_GUIDE.md).
- [ ] Read CE [ARCHITECTURE.md](../../../ENTERPRISE.md), [DESIGN.md](DESIGN.md), and [FUNCTIONAL_SPECIFICATION.md](FUNCTIONAL_SPECIFICATION.md).
- [ ] Review [FEATURE_CATALOG.md](../FEATURE_CATALOG.md) and [learn/README.md](../learn/README.md).
- [ ] Trace one query, one ingest, and one tool invocation from API to audit.
- [ ] Explain the SQLite/Qdrant ACL distinction.
- [ ] Explain the CE quarantine lifecycle and EE exclusion.

### Operate

- [ ] Create and prove a CE-only virtualenv ([LOCAL_SETUP.md](LOCAL_SETUP.md)).
- [ ] Build and open the four-workspace CE console.
- [ ] Run CE on host and Docker.
- [ ] Run SQLite and Qdrant modes.
- [ ] Reload the active persisted policy and explain `config/` versus `data/`.
- [ ] Diagnose a 404, 403, stale UI, unreachable LLM, backend mismatch, and missing audit event.

### Change

- [ ] Add focused tests before or with implementation.
- [ ] Keep API handlers thin and security logic in owned modules.
- [ ] Preserve no-LLM early exits.
- [ ] Preserve ACL-before-scoring/query invariants.
- [ ] Emit bounded, non-sensitive audit details.
- [ ] Keep CE runnable with no EE package, checkout, bundle, or service.
- [ ] Classify CE-internal versus seam before release work.

### Validate and hand off

- [ ] Focused pytest passes.
- [ ] Full non-live CE pytest passes.
- [ ] Seam tests pass.
- [ ] Console typecheck/test/build passes when touched.
- [ ] Docker image and smoke pass when runtime/deployment changed.
- [ ] Tool-specific workflow tests pass when touched.
- [ ] Documentation checklist is complete.
- [ ] Review notes state scope, security invariant, validation, persistence impact, and release classification.

The ownership standard is not merely “tests pass.” A CE owner can identify the active configuration and data state, trace each trust decision, prove standalone operation, and explain exactly where CE ends.
