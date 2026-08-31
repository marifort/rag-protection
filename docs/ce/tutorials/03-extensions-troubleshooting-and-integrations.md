# Tutorial 03 — Extensions, troubleshooting & integrations

> **Lab / A aliases:** none — integration patterns across the `#N` spine ([FEATURE_ID_ALIASES.md](../../shared/FEATURE_ID_ALIASES.md)).

## Part 8 — Optional extensions

Beyond the core walkthrough, these sections cover vector search, corporate IdP, **multi-tenant operator console** (§8.4), **OIDC-mapped admin roles** (§8.5), and policy hot-reload (§8.6).

### 8.1 Vector retrieval (semantic search)

Default SQLite uses lexical token overlap. For semantic recall with the same guardrails:

```bash
docker compose --profile qdrant up -d --build
```

Set in `.env`:

```bash
RAG_STORE_BACKEND=vector
RAG_QDRANT_URL=http://qdrant:6333
```

Restart and confirm `/health` shows `"store_backend": "vector"`. ACL and guardrail behavior stay the same; only retrieval ranking changes.

Guide: [../RETRIEVAL_AND_VECTOR_DB.md](../README.md) · [../V1_P0_FEATURES.md](../README.md).

### 8.2 Corporate identity (OIDC)

For production, replace demo tokens with JWT/OIDC from Okta or Azure AD:

```bash
RAG_OIDC_ENABLED=true
RAG_OIDC_ISSUER=https://your-idp.example/
RAG_OIDC_AUDIENCE=rag-protection-proxy
RAG_OIDC_JWKS_URI=https://your-idp.example/.well-known/jwks.json
```

Restart the proxy. `/health` should show `oidc_enabled: true`.

Runbook: [../../qa/runbooks/OIDC_VALIDATION.md](../../../ENTERPRISE.md).

### 8.4 Multi-tenant operator console (E5.3)

The sample `acl_policy.yaml` includes **tenant-scoped user tokens** for a two-tenant demo:

| User token | Tenant | Groups |
|------------|--------|--------|
| `acme-employee-token` | `acme` | engineering |
| `globex-hr-token` | `globex` | hr |

CE isolates stores per `tenant_id`. EE is not required for that. Query Lab already lists these **user** tokens on a fresh stack. Toolbar **Operator tenant** lists only stores on disk (`GET /admin/auth/me` → `allowed_tenants`), so it usually shows `default` until you complete Exercise A or run a query with those tokens. That is expected. Details: [USER_GUIDE §14](../guide/USER_GUIDE.md#query-lab-presets-vs-operator-tenant).

**Exercise A — Ingest per tenant (CLI)**

```bash
# Ingest into acme namespace
curl -s -X POST 'http://localhost:8090/v1/ingest?tenant_id=acme' \
  -H "Authorization: Bearer rag-admin-demo-key" \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "acme-memo",
    "title": "Acme internal memo",
    "content": "Acme Q2 roadmap focuses on platform reliability.",
    "allowed_groups": ["engineering", "all-staff"]
  }' | python3 -m json.tool

# Ingest into globex namespace
curl -s -X POST 'http://localhost:8090/v1/ingest?tenant_id=globex' \
  -H "Authorization: Bearer rag-admin-demo-key" \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "globex-memo",
    "title": "Globex HR policy",
    "content": "Globex parental leave policy updated for 2026.",
    "allowed_groups": ["hr", "all-staff"]
  }' | python3 -m json.tool
```

**Exercise B — User tokens see only their tenant**

```bash
curl -s http://localhost:8090/v1/documents \
  -H "Authorization: Bearer acme-employee-token" | python3 -m json.tool
# tenant_id: acme — acme-memo visible, globex-memo absent

curl -s http://localhost:8090/v1/documents \
  -H "Authorization: Bearer globex-hr-token" | python3 -m json.tool
# tenant_id: globex — globex-memo visible, acme-memo absent
```

**Exercise C — Operator tenant selector (UI)**

1. Open `/ui` → toolbar **Operator tenant**. If the list is only `default`, finish Exercise A (or Query Lab with `acme-employee-token`) and refresh.
2. Select `acme`.
3. **Documents & Ingest** → ingest a document (or view quarantine).
4. Switch **Operator tenant** to `globex` → corpus and audit views scope to that namespace.
5. **Audit Log** → export NDJSON — lines match the selected tenant when scoped.

**Exercise D — List tenants your admin may access**

On **CE**, `GET /admin/tenants` is **404** (EE Tier 2). Use `/admin/auth/me`:

```bash
curl -s http://localhost:8090/admin/auth/me \
  -H "Authorization: Bearer rag-admin-demo-key" | python3 -m json.tool
# global_admin: true, allowed_tenants: ["default"] until acme/globex stores exist
```

After Exercise A, `allowed_tenants` includes `acme` and `globex`. With Enterprise installed:

```bash
curl -s http://localhost:8090/admin/tenants \
  -H "Authorization: Bearer rag-admin-demo-key" | python3 -m json.tool
```

Manual tests: [../../qa/test-plans/E5_TEST_PLAN.md#e53--tenant-selector](../../../ENTERPRISE.md#e53--tenant-selector) · Deep dive: [../../enterprise/e5/E5_3_TENANT_SELECTOR.md](../../../ENTERPRISE.md)

**Automated UI tests** (no browser required):

```bash
cd rag-protection-proxy
pytest -q tests/test_ui_and_admin.py -k "operator_tenant or append_tenant"
pytest -q tests/test_e5.py::test_ui_build_tag_e5
```

### 8.5 OIDC-mapped operator admin roles (E2.4)

Production operators should not share a static `RAG_ADMIN_API_KEY`. Map **IdP groups** to admin roles in `acl_policy.yaml`:

```yaml
oidc:
  enabled: true
  issuer: https://your-idp.example/
  audience: rag-protection-proxy
  jwks_uri: https://your-idp.example/.well-known/jwks.json
  admin_role_map:
    policy_admin: [rag-platform-admins]
    audit_reader: [rag-soc-readers]
    audit_debug_reader: [rag-soc-debug]
    ingest_admin: [rag-content-admins]
  admin_global_groups: [rag-platform-admins]   # platform ops — all tenants
```

| IdP group in token | Admin role | Typical use |
|--------------------|------------|-------------|
| `rag-soc-readers` | `audit_reader` | SOC export / audit charts only |
| `rag-content-admins` | `ingest_admin` | Ingest + quarantine (no policy reload) |
| `rag-platform-admins` | `policy_admin` (+ others if mapped) | Policy reload, SCIM sync - **global** scope |

**Exercise — validate with live IdP token**

```bash
export OIDC_ACCESS_TOKEN="<access token from Okta/Azure>"

curl -s http://localhost:8090/admin/auth/me \
  -H "Authorization: Bearer $OIDC_ACCESS_TOKEN" | python3 -m json.tool
# auth_method: "oidc", roles: ["audit_reader", ...]

curl -s http://localhost:8090/admin/audit/export \
  -H "Authorization: Bearer $OIDC_ACCESS_TOKEN" -o audit.jsonl
```

**Tenant-scoped operators:** add `tenant_id` on static `admin_users` entries, or issue OIDC tokens with a `tenant_id` claim for ingest-only admins limited to one customer namespace. Cross-tenant ingest returns **403**.

```yaml
admin_users:
  - token: acme-ingest-only
    subject: acme.ingest
    tenant_id: acme
    roles: [ingest_admin]
```

Runbook: [../../qa/runbooks/OIDC_VALIDATION.md#4b-oidc-operator-admin-roles-optional--production-pilots](../../../ENTERPRISE.md#4b-oidc-operator-admin-roles-optional--production-pilots) · [../../enterprise/e2/E2_4_ADMIN_RBAC.md](../../../ENTERPRISE.md) · Tests:

```bash
cd rag-protection-proxy
pytest -q tests/test_oidc_admin.py
pytest -q tests/test_ui_and_admin.py -k admin_auth
```

### 8.6 Policy hot-reload

Edit `rag-protection-proxy/config/policy.yaml` or `acl_policy.yaml`, then:

```bash
curl -s -X POST http://localhost:8090/admin/reload-policy \
  -H "Authorization: Bearer rag-admin-demo-key" | python3 -m json.tool
```

No restart needed for policy and ACL changes. Environment variables (`RAG_*`) still require a restart.

Full settings reference: [../ADMIN_GUIDE.md](../../ce/guide/ADMIN_GUIDE.md).

---

## Part 9 — Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `/health` unreachable | Stack not started | `bash tools/docker_start.sh` |
| Slow `docker_start.sh` | Rebuilds image each run | `bash tools/docker_start.sh --no-build` (after first build) |
| Code/UI changes not visible | Bind-mounted source; container not restarted | `docker compose restart rag-protection-proxy`; hard-refresh browser |
| LLM errors or timeout | Model Runner not ready | Wait 30-60s after start; check Docker Desktop Model Runner |
| Smoke hangs on `Engineer query (should NOT retrieve HR payroll)` | First `/v1/query` after `/health` — Model Runner cold-start + LLM call (ACL still excludes payroll; weak hits on other docs still generate) | Wait for Model Runner; later smoke steps are faster once warm. Details: [CE_LEGACY_AND_PACKAGING_NOTES.md §3](../README.md#docker-start-smoke-tests) |
| Empty answers for FAQ | Corpus not seeded | `bash tools/docker_stop.sh --volumes` then restart |
| Admin API returns 401 | Wrong admin key or OIDC token | Match `RAG_ADMIN_API_KEY` / IdP token; check `GET /admin/auth/me` |
| Ingest returns 403 for admin | Tenant-scoped operator on wrong tenant | Match `tenant_id` query param to admin's `tenant_scope`, or use global admin |
| All queries blocked | Strict policy thresholds | Check Policy Viewer/Admin; compare with defaults in `policy.yaml` |
| Smoke test fails on payroll ACL | Stale data or policy | Reset volumes and re-run smoke |

Reset corpus and start fresh:

```bash
bash tools/docker_stop.sh --volumes
bash tools/docker_start.sh --no-build   # or full build if image missing
bash tools/smoke_rag_proxy.sh
```

Run automated tests (no live stack required):

```bash
bash tools/run_tests.sh -q -m "not live"
```

---

## Part 10 — What you learned

| Concept | Takeaway |
|---------|----------|
| **ACL** | Authorization happens **before** retrieval - unauthorized docs never enter the candidate set |
| **DLP** | Sensitive data is redacted in chunks **before** the LLM sees them |
| **Injection** | Queries and chunks are scanned; surviving context is XML-isolated as untrusted |
| **Citation** | Answers are verified against sources; hallucinations get a safe fallback |
| **LLM gate** | The model runs only when authorized, clean chunks exist |
| **Ingest** | New documents are scanned at write time - reject, quarantine, or approve |
| **Audit** | Every decision is observable for SOC and compliance review |
| **Multi-tenant** | User `tenant_id` isolates corpora (CE). Query Lab presets list Acme/Globex users immediately; **Operator tenant** lists stores on disk and starts as `default` |
| **Operator RBAC** | Least-privilege admin roles; OIDC `admin_role_map` replaces shared API keys in production |
| **Tool gateway** | Identity-bound tool allowlist before side effects - same pattern as retrieval ACL ([#7](./04-agent-mcp-tool-gateway-lab1.md#part-11--agent--mcp-tool-gateway-lab-1)) |

---

## 9. LangChain and Pinecone integration (E7)

Use this section when the buyer already runs **LangChain** and/or **Pinecone** and asks how RAG Protection fits without replacing their stack.

**Plain-English teach + install:** [learn § Integration Patterns A/B/C](../learn/02-runtime-and-operations.md#integration-patterns-abc) (full Pattern C prose, prerequisites, and tutorial).

**Technical guides:** [INTEGRATIONS.md](../../product/INTEGRATIONS.md) · [E7_2_LANGCHAIN_PINECONE.md](../../../ENTERPRISE.md) · [E7_1_SCAN_API.md](../../../ENTERPRISE.md)

### 9.1 Choose a pattern

| Pattern | When | API | What CE owns |
|---------|------|-----|--------------|
| **A — Full gateway** (recommended) | Users can call the proxy for answers | `POST /v1/query` | Identity, retrieval ACL, all four guardrails, LLM path, audit |
| **B — Proxy corpus** | Use proxy store + CE quarantine lifecycle | `POST /v1/ingest` + `POST /v1/query` | Ingest scan/quarantine API plus full query path |
| **C — BYO Pinecone** | Buyer insists on Pinecone (or existing retrieval) | `POST /v1/scan` at ingest (E7.1) | Input DLP + injection at the chosen boundary only |

Pattern A exercises **all four guardrails** including ACL at retrieval. Pattern C scans documents before embedding but **does not** enforce ACL—the customer must filter Pinecone by `allowed_groups` metadata at query time. Never reuse a Pattern A ACL claim in a Pattern C architecture review.

### 9.2 Installation and configuration (shared)

From the repository root:

```bash
bash tools/docker_start.sh --smoke   # or full start without --smoke
export BASE=http://localhost:8090
bash tools/setup_venv.sh && source .venv/bin/activate
```

| Variable | Pattern | Purpose |
|----------|---------|---------|
| `RAG_PROTECTION_URL` | A and C | Proxy base (`http://localhost:8090` or Compose service URL) |
| `RAG_PROTECTION_USER_TOKEN` | A | End-user bearer for `POST /v1/query` (e.g. `hr-demo-token`) |
| `RAG_PROTECTION_ADMIN_KEY` | C (and B ingest) | `ingest_admin` for `POST /v1/scan` / ingest |
| `PINECONE_INDEX_HOST` | C + `--pinecone` | Local emulator data plane (`http://localhost:5081`) |
| `PINECONE_API_KEY` | C | `pclocal` for Local (ignored); cloud key for production |
| `PINECONE_DIMENSION` / `PINECONE_NAMESPACE` | C local | Must match compose `DIMENSION` (default `8`) |

Policy for `/v1/scan` is the **running** live file (`data/policy.yaml` on Docker; `rag-protection-proxy/config/policy.yaml` on host uvicorn)—same `input.*` / `dlp.*` knobs as other CE input paths.

### 9.3 Try Pattern A now (no Pinecone account required)

```bash
export RAG_PROTECTION_URL=$BASE
export RAG_PROTECTION_USER_TOKEN=hr-demo-token
python examples/langchain/full_gateway_query.py
```

**Expected:** support-hours query returns an answer; jailbreak query shows `blocked: true`.

### 9.4 Docker sidecar

Deploy the proxy container on the same network as your LangChain app:

```text
langchain-app  →  RAG_PROTECTION_URL=http://rag-protection-proxy:8090
```

See [E7.2 § Docker Compose](../../../ENTERPRISE.md#docker-compose-topology).

### 9.5 Pattern C — scan before Pinecone upsert

**What:** Keep Pinecone for embed/index/query. Call `POST /v1/scan` (admin token) from a LangChain `DocumentTransformer` **before** embedding. Branch on `disposition`; upsert only `sanitized_text` with `allowed_groups` metadata. At query time, the **customer** applies Pinecone metadata filters from IdP groups.

**How (Pinecone Local in Docker — no cloud account):**

```bash
bash tools/docker_start.sh --pinecone
export RAG_PROTECTION_URL=$BASE
export RAG_PROTECTION_ADMIN_KEY=rag-admin-demo-key
python examples/langchain/byo_pinecone_ingest.py
```

**Expected:** HR memo accepted; poisoned ticket rejected; **one** vector upserted to Pinecone Local at `http://localhost:5081`. Image: `ghcr.io/pinecone-io/pinecone-index:latest` (compose profile `pinecone`). Without `--pinecone`, the script still scans and prints a placeholder.

**How (production / cloud Pinecone):** point your LangChain upsert at the customer index; store `allowed_groups` / `document_id` / `tenant_id` on every vector; filter at query with `{"allowed_groups": {"$in": user_groups}}`. Optional: re-scan retrieved chunks with `/v1/scan` before the LLM (still not full citation/ACL).

Adapters: [byo_pinecone_ingest.py](../../../examples/langchain/byo_pinecone_ingest.py) · [transformers.py](../../../examples/langchain/transformers.py) · [rag_protection_client.py](../../../examples/python/rag_protection_client.py) · [COMPOSE_OVERLAYS.md](../../../ENTERPRISE.md)

**Security review talking point:** Compare Pattern A ACL (`employee-demo-token` vs `hr-demo-token` on payroll) with the ACL gap table in [E7.2 § ACL gap](../../../ENTERPRISE.md#acl-gap--what-to-tell-security-reviewers). Full teach-up: [learn § Pattern C](../learn/02-runtime-and-operations.md#integration-patterns-abc).

### 9.6 Related docs

| Doc | Purpose |
|-----|---------|
| [learn § Integration Patterns](../learn/02-runtime-and-operations.md#integration-patterns-abc) | Plain English, install, tutorial |
| [E7_1_SCAN_API.md](../../../ENTERPRISE.md) | Scan API request/response spec |
| [examples/python/rag_protection_client.py](../../../examples/python/rag_protection_client.py) | Thin HTTP client |
| [qa/test-plans/E7_TEST_PLAN.md](../../../ENTERPRISE.md) | TC-E7-* validation |
