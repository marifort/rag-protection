# Framework Integrations — LangChain, Pinecone, BYO RAG

How to integrate **RAG Protection Proxy** with an existing RAG stack without adopting LangChain or LlamaIndex inside the gateway.

**Status:** **E7.1 + E7.4 shipped** (2026-06-25) — `POST /v1/scan`, LangChain `DocumentTransformer`, Pattern C example. Pattern A works today via `POST /v1/query`.

---

## Start here

| Audience | Document |
|----------|----------|
| **Architect / platform engineer** | [E7_FRAMEWORK_INTEGRATIONS.md](../../ENTERPRISE.md) — patterns A–D |
| **LangChain + Pinecone** | [e7/E7_2_LANGCHAIN_PINECONE.md](../../ENTERPRISE.md) |
| **Scan API contract** | [e7/E7_1_SCAN_API.md](../../ENTERPRISE.md) |
| **Runnable examples** | [examples/langchain/README.md](../../examples/langchain/README.md) |
| **HTTP client** | [examples/python/rag_protection_client.py](../../examples/python/rag_protection_client.py) |
| **Rerank / HyDE vs this gateway** | [RAG_QUALITY_VS_SECURITY.md](RAG_QUALITY_VS_SECURITY.md) |
| **Plain-English client usage** | [CLIENT_USAGE.md](CLIENT_USAGE.md) — RAG + MCP via API, Python, UI |
| **Test plan** | [qa/test-plans/E7_TEST_PLAN.md](../../ENTERPRISE.md) |

---

## Three integration patterns

```text
Pattern A (recommended)     POST /v1/query
                            → All four guardrails; proxy owns retrieval + LLM path

Pattern B (proxy corpus)    POST /v1/ingest + POST /v1/query
                            → Quarantine lifecycle; no Pinecone required

Pattern C (BYO Pinecone)    POST /v1/scan at ingest → embed → Pinecone
                            → Input DLP + injection only; ACL is customer-owned
```

**Default POC:** Pattern A. Use Pattern C only when the buyer insists on keeping Pinecone.

Reranking, HyDE, and query expansion stay in the LangChain/LlamaIndex retriever unless a named POC insists on an in-proxy exception — [RAG_QUALITY_VS_SECURITY.md](RAG_QUALITY_VS_SECURITY.md). Pattern A still applies ACL, scanners, and the citation gate to whatever was retrieved.

**Plain-English teach (Pattern C install, config, what/how, ACL gap):** [ce/learn/02-runtime-and-operations.md § Integration Patterns](../ce/learn/02-runtime-and-operations.md#integration-patterns-abc).

---

## Quick start (Pattern A)

```bash
# Terminal 1 — proxy
bash tools/docker_start.sh

# Terminal 2 — example (deps via tools/setup_venv.sh, or pip install httpx langchain-core)
export RAG_PROTECTION_URL=http://localhost:8090
export RAG_PROTECTION_USER_TOKEN=hr-demo-token
python examples/langchain/full_gateway_query.py
```

---

## Quick start (Pattern C — E7.1 + E7.4)

```bash
# Terminal 1 — proxy + Pinecone Local (Pattern C examples)
# .env: RAG_STORE_BACKEND=sqlite
bash tools/docker_stop.sh --qdrant --pinecone
bash tools/docker_start.sh --pinecone

# Terminal 2 — scan API tests + BYO Pinecone ingest demo
bash tools/setup_venv.sh && source .venv/bin/activate
export BASE=http://localhost:8090
export RAG_PROTECTION_URL=$BASE
export RAG_PROTECTION_ADMIN_KEY=rag-admin-demo-key
cd rag-protection-proxy && pytest -q tests/test_e7.py
cd .. && python examples/langchain/byo_pinecone_ingest.py
```

**Expected:** HR memo accepted; poisoned ticket rejected; **one** vector upserted to Pinecone Local (`http://localhost:5081`). Without `--pinecone`, the script falls back to a print placeholder. Customer must still filter Pinecone by `allowed_groups` at query time for ACL.

**No UI:** Documents & Ingest will not list `hr-memo-1`; Pinecone Local has no browser UI. Fetch via API — see [COMPOSE_OVERLAYS § Switching](../../ENTERPRISE.md#switching-qdrant-and-pinecone-local) or [examples/langchain/README.md](../../examples/langchain/README.md).

**Qdrant vs Pinecone Local:** [COMPOSE_OVERLAYS § Switching](../../ENTERPRISE.md#switching-qdrant-and-pinecone-local) — `--qdrant` is the CE store sidecar; `--pinecone` is Pattern C only. `RAG_STORE_BACKEND=vector|hybrid` auto-starts Qdrant even without `--qdrant`.

---

## Docker sidecar

Run the proxy image beside your LangChain application on a shared Compose network. Set `RAG_PROTECTION_URL=http://rag-protection-proxy:8090` in the app container.

Details: [E7_2 § Docker Compose](../../ENTERPRISE.md#docker-compose-topology).

---

## What we deliberately do not build

| Item | Rationale |
|------|-----------|
| LangChain inside the proxy | Auditable custom pipeline — [TECH_STACK.md](TECH_STACK.md) |
| PyPI adapter package (v1) | In-repo examples first; publish when a buyer commits |
| Native Pinecone backend in proxy | BYO Pinecone uses Pattern C; shipped backends are SQLite/Qdrant/pgvector |

---

## Roadmap

| ID | Item | Status |
|----|------|--------|
| E7.1 | `POST /v1/scan` | **Shipped** — [E7_1_SCAN_API.md](../../ENTERPRISE.md) |
| E7.4 | LangChain `DocumentTransformer` | **Shipped** — [transformers.py](../../examples/langchain/transformers.py) |
| E7.2 | LangChain + Pinecone guide | **Validated 2026-06-26** — [E7_TEST_PLAN.md](../../ENTERPRISE.md) |
| E7.3 | Python client + examples | **Validated 2026-06-26** — TC-E7-201/202/301 |
| E7.5 | LlamaIndex component | P4 / deferred — buyer trigger |

**Engineering plan:** [POLISH_SPRINT.md](../ce/README.md) · **Backlog:** [UNRESOLVED_E_BACKLOG.md](../../ENTERPRISE.md)

---

*Document version 1.1 · June 2026 · E7.1 + E7.4 shipped*
