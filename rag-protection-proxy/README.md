<p align="center">
  <a href="https://github.com/marifort">
    <img src="rag_protection_proxy/ui/static/marifort-company-badge.png" alt="Marifort" width="96" height="96" />
  </a>
</p>

# Marifort Gate (service)

FastAPI service implementing secured RAG per [../docs/product/RAG_Protection.md](../docs/ce/README.md).

**Vendor:** Marifort Systems Inc. · **License:** MIT — see [../LICENSE](../LICENSE).

**Documentation:** start at [../docs/README.md](../docs/README.md) — architecture, knowledge base, tech stack. **v1 P0 features:** [../docs/product/V1_P0_FEATURES.md](../docs/ce/README.md).

---

## Run with Docker (recommended)

From repository root:

```bash
bash tools/build_ce.sh              # React console — not run by docker_start.sh
bash tools/docker_start.sh
bash tools/smoke_rag_proxy.sh
```

**Start without rebuilding** (use when the image is already built):

```bash
bash tools/docker_start.sh --no-build
```

Other flags: `--mcp-tools` (Layer 2 MCP backend), `--smoke` (RAG smoke after start; add `--mcp-tools` for tool-gateway + MCP smoke), `--skip-health`, `--foreground`, `--no-cache` (full rebuild). See [../README.md § Docker start options](../README.md#docker-start-options).

**Layer 2 MCP:**

```bash
bash tools/docker_start.sh --mcp-tools --smoke
bash tools/docker_stop.sh --mcp-tools
```

After editing bind-mounted **Python** source, restart instead of rebuilding:

```bash
docker compose restart rag-protection-proxy
```

After editing **CE React** (`console/`), rebuild the bundle (bind-mounted — no image rebuild):

```bash
bash tools/build_ce.sh
```

UI / Docker matrix: [../docs/commercial/COMPOSE_OVERLAYS.md § React console](../ENTERPRISE.md#react-console-is-not-built-inside-docker).

Rebuild when `Dockerfile` or dependencies change: `bash tools/docker_build.sh` (CE image → `rag-protection-proxy:latest`, `INSTALL_EE_WHEEL=0`).

CE-only Docker guide: [../docs/commercial/COMPOSE_OVERLAYS.md § CE-only Docker](../ENTERPRISE.md#ce-only-docker-for-contributors).

**Optional vector backend (Qdrant + semantic retrieval):**

```bash
docker compose --profile qdrant up -d --build
export RAG_STORE_BACKEND=vector
export RAG_QDRANT_URL=http://localhost:6333
```

```bash
bash tools/docker_build.sh
```

---

## Run with Python

**Python 3.11+** required; **CI and this image use 3.13.** Full venv instructions (libraries, activate, verify): [../docs/ce/guide/LOCAL_SETUP.md](../docs/ce/guide/LOCAL_SETUP.md).

From repository root:

```bash
bash tools/setup_venv.sh
source .venv/bin/activate
cd rag-protection-proxy
export RAG_LLM_BASE_URL=http://localhost:12434/engines/v1   # or Model Runner URL
uvicorn rag_protection_proxy.app:app --host 0.0.0.0 --port 8090
open http://localhost:8090/ui
```

---

## Operator console

`http://localhost:8090/ui` — paste:

- **User bearer token** — demo tokens from `config/acl_policy.yaml`, HS256 JWT, or OIDC access token
- **Admin bearer token** — `RAG_ADMIN_API_KEY` (Policy Viewer/Admin, ingest, reload)

Full admin walkthrough and test matrix: [../docs/product/ADMIN_GUIDE.md](../docs/ce/README.md).

**Secured RAG Query** sends `POST /v1/query` with the selected token. The chat LLM runs only when at least one ACL-authorized chunk passes input guardrails (e.g. payroll query with `employee-demo-token` stops at ACL; same query with `hr-demo-token` reaches the LLM). Details: [../docs/product/TECH_STACK.md § When POST /v1/query invokes the LLM](../docs/product/TECH_STACK.md#when-post-v1query-invokes-the-llm).

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `RAG_POLICY_FILE` | `./config/policy.yaml` | Scanner thresholds, LLM settings |
| `RAG_ACL_FILE` | `./config/acl_policy.yaml` | Demo tokens, JWT, OIDC, group hierarchy |
| `RAG_SAMPLE_DOCS` | `./config/sample_documents.json` | Seed corpus on empty store |
| `RAG_DATA_DIR` | `./data` | SQLite DB path or embedding model cache |
| `RAG_STORE_BACKEND` | `sqlite` | `sqlite` or `vector` (Qdrant) |
| `RAG_QDRANT_URL` | `http://localhost:6333` | Qdrant URL when using vector backend |
| `RAG_QDRANT_COLLECTION` | `rag_chunks` | Qdrant collection name |
| `RAG_EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Embedding model |
| `RAG_OIDC_ENABLED` | `false` | Enable OIDC/JWKS (Okta, Azure AD, Auth0) |
| `RAG_OIDC_ISSUER` | empty | Expected JWT issuer |
| `RAG_OIDC_AUDIENCE` | empty | Expected JWT audience |
| `RAG_OIDC_JWKS_URI` | empty | JWKS endpoint for RS256 validation |
| `RAG_OIDC_UI_CLIENT_ID` | empty | EE Sign in with IdP — OAuth client id |
| `RAG_OIDC_UI_CLIENT_SECRET` | empty | EE Sign in with IdP — client secret (prefer env over YAML) |
| `RAG_OIDC_UI_REDIRECT_URI` | empty | EE callback, e.g. `http://localhost:8090/admin/auth/oidc/login/callback` |
| `RAG_LLM_BASE_URL` | Model Runner URL | OpenAI-compatible base URL |
| `RAG_LLM_MODEL` | `ai/gemma3-qat` | Model name |
| `RAG_ADMIN_API_KEY` | empty | Required for `/v1/ingest` when set |

Full reference: [../docs/product/ARCHITECTURE.md § Configuration](../docs/ce/README.md#configuration-reference). Use cases and examples: [../docs/product/V1_P0_FEATURES.md](../docs/ce/README.md).

---

## Key modules

| Module | Role |
|--------|------|
| `pipeline.py` | Query orchestration (user-query scan → retrieval → guardrails) |
| `guardrails/ingest.py` | Ingest-time security scan and quarantine disposition |
| `store.py` | SQLite backend, `create_document_store()` factory |
| `vector_store.py` | Qdrant retrieval, ACL filter in vector query |
| `embeddings.py` | Sentence-transformer embeddings |
| `acl.py` | Demo tokens, HS256 JWT, OIDC/JWKS — [../docs/guardrails/GUARDRAIL_1_ACL.md](../docs/ce/README.md) |
| `context_builder.py` | XML context isolation — [../docs/guardrails/GUARDRAIL_3_INJECTION.md](../docs/ce/README.md) |
| `llm.py` | OpenAI-compatible client (`httpx`) |
| `guardrails/` | Input/output/citation pipelines — [../docs/guardrails/README.md](../docs/ce/README.md) |
| `scanners/` | PII, secrets, injection, URL |

Module map: [../docs/product/TECH_STACK.md](../docs/product/TECH_STACK.md).

---

## Tests

From repository root (uses repo `.venv`):

```bash
bash tools/run_tests.sh -q -m "not live"    # 128 tests (123 non-live + 5 live markers)
bash tools/run_tests.sh -q -m live          # live-stack tests (requires RUN_INTEGRATION=1)
```

| File | Coverage |
|------|----------|
| `tests/test_rag_protection.py` | ACL, DLP, injection, citation, SQLite search |
| `tests/test_vector_store.py` | Qdrant ACL filter, paraphrase retrieval |
| `tests/test_oidc_auth.py` | HS256 JWT, OIDC/JWKS, roles claim fallback |
| `tests/test_oidc_admin.py` | OIDC/JWT `admin_role_map`, tenant-scoped operator RBAC |
| `tests/test_store_factory.py` | `RAG_STORE_BACKEND` sqlite vs vector |
| `tests/test_ui_and_admin.py` | `/ui`, admin API, ACL-filtered document list, E5.3 operator tenant UI |
| `tests/test_p1.py` | User-query block, ingest reject/quarantine, CHALLENGE mode |
| `tests/test_audit.py` | Persistent audit JSONL, webhook, admin export |
| `tests/test_e2.py` … `tests/test_e5_7_scheduler.py` | E2–E5 enterprise features (see [IMPLEMENTATION_STATUS.md](../docs/ce/README.md#test-coverage-summary)) |
| `tests/test_e5.py -k preview_patterns` | E5.9 Pattern Lab dry-run API |
| `tests/test_e5_5_challenge_queue.py` | E5.5 CHALLENGE queue list, approve, reject, audit |
| `tests/test_e4_4_compliance.py` | E4.4 compliance pack validation |
| `tests/integration/` | SQLite vs vector parity; live compose smoke |

Details: [../docs/product/IMPLEMENTATION_STATUS.md § Test coverage](../docs/ce/README.md#test-coverage-summary) · [../docs/product/V1_P0_FEATURES.md § Tests](../docs/ce/README.md#tests).
