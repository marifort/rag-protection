# Technology Stack

What this project uses, what it deliberately avoids, and how the custom RAG pipeline is organized.

---

## Summary

| Layer | Technology | Notes |
|-------|------------|-------|
| Python | 3.11+ (`requires-python`) | **CI and CE Docker image: 3.13.** Local venv: [LOCAL_SETUP.md](../ce/guide/LOCAL_SETUP.md) |
| HTTP API | FastAPI + Uvicorn | `app.py` |
| LLM client | `httpx` → OpenAI-compatible `/chat/completions` | Docker Model Runner by default — **no external LLM subscription** |
| Document store | SQLite (default) or Qdrant via `VectorDocumentStore` | `RAG_STORE_BACKEND=vector` for semantic retrieval |
| Auth / ACL | PyJWT + demo tokens + OIDC/JWKS | `acl.py`, `acl_policy.yaml` |
| Config | PyYAML + Pydantic dataclasses | `config.py`, `policy.yaml` |
| Metrics | prometheus-client | `/metrics` endpoint |
| Tests | pytest + pytest-asyncio | `tests/` |

**LangChain, LlamaIndex, Haystack, and similar RAG frameworks are not used.**

---

## Why no LangChain?

This project is a **security gateway**, not a general-purpose RAG toolkit. A thin, auditable pipeline is preferable:

| Concern | Custom pipeline | LangChain-style framework |
|---------|-----------------|---------------------------|
| **Auditability** | Fixed order in `pipeline.py`; every step is explicit | Abstractions and chains can obscure control flow |
| **Dependencies** | Seven runtime packages | Large transitive dependency trees |
| **Guardrail integration** | Scanners wired directly before/after LLM | Would require custom callbacks or wrappers |
| **Store contract** | `DocumentStore.search()` — swappable backend | Framework-specific retriever interfaces |
| **Deployment** | Single FastAPI container, ~minimal image | Heavier runtime, version coupling |

The v1 P0 release adds an optional vector backend **behind the same `search()` interface** — still without adopting a full RAG framework. See [V1_P0_FEATURES.md](../ce/README.md) and [ARCHITECTURE.md § Vector Database](../ce/README.md#vector-database-for-testing).

### Integrating with LangChain, Pinecone, LlamaIndex (E7)

The proxy does **not** embed LangChain. Buyers on existing stacks integrate via **HTTP**:

| Pattern | API | When |
|---------|-----|------|
| Full gateway | `POST /v1/query` | Default — all four guardrails |
| Proxy corpus | `POST /v1/ingest` | Quarantine workflow + proxy store |
| BYO Pinecone | `POST /v1/scan` | Scan at ingest; customer owns vectors + ACL filter |

**Docs:** [INTEGRATIONS.md](INTEGRATIONS.md) · [E7_2_LANGCHAIN_PINECONE.md](../../ENTERPRISE.md) · **Examples:** [examples/langchain/README.md](../../examples/langchain/README.md)

---

## Technology strategy (Python vs Rust)

**Decision (2026-06):** Keep the **Python monolith** (FastAPI) as the default implementation through first Enterprise customers and E4/E5. Do **not** start a full Python → Rust rewrite before paid pilots and production connectors land.

Commercial context: [SUCCESS_POTENTIAL.md](../ce/README.md) · execution priority: [GTM_90_DAY.md](../ce/README.md) · engineering backlog: [NEXT_STEPS.md](../ce/README.md).

### Summary

| Question | Answer |
|----------|--------|
| **Is the API already REST?** | **Yes** — FastAPI exposes `POST /v1/query`, `/v1/ingest`, admin routes. Buyers integrate via HTTP, not Python. |
| **Full rewrite to Rust?** | **No (now)** — low ROI; delays GTM and E5 connectors; discards 128 tests and E1–E5 coverage. |
| **Hybrid Rust gateway + Python ML?** | **Maybe later** — only if measured scale or procurement requires it. |
| **Scale without Rust?** | **Yes** — E4.2 stateless replicas, external Qdrant/pgvector, optional connector workers (E5.7). |

### Why Python fits this product

| Factor | Implication |
|--------|-------------|
| **Latency profile** | `run_query()` spends most time in `LLMClient.chat()` (seconds). ACL, regex scanners, and citation checks are milliseconds — Rust saves little end-to-end. |
| **ML guardrails (E3)** | `sentence-transformers` drives vector retrieval, ML injection (`scanners/injection_ml.py`), and entailment (`guardrails/citation.py`). Rust needs ONNX/candle or a Python sidecar anyway. |
| **Future E6** | Presidio/spaCy NER is Python-native — reinforces staying Python or a dedicated ML service. |
| **Security buyer** | Thin, readable `pipeline.py` supports auditability during POC — a core selling point per [TECH_STACK.md § Why no LangChain](#why-no-langchain). |
| **Open core (MIT)** | Python lowers fork, contribute, and self-host friction for Community Edition. |
| **Commercial priority** | **E5.6/E5.7** Drive stack and **E4.4** compliance pack **shipped** — paid pilots matter more than runtime language — see [SUCCESS_POTENTIAL.md § What moves the needle](../ce/README.md#what-moves-the-needle). |

### What would port cleanly vs painfully

| Module | Rust portability | Notes |
|--------|------------------|-------|
| `app.py` (HTTP routes) | **Easy** | `axum` / `actix-web` |
| `acl.py` (JWT, OIDC/JWKS) | **Easy** | `jsonwebtoken`, JWKS crates |
| Regex scanners (`scanners/*`) | **Easy** | `regex` crate |
| `audit.py`, `admin_auth.py` | **Easy** | Straightforward I/O |
| `store.py`, `vector_store.py` | **Easy** | `sqlx` / `rusqlite`, official `qdrant-client` crate |
| `config.py`, `models.py` | **Easy** | `serde` + `serde_yaml` |
| `pipeline.py`, `context_builder.py` | **Medium** | Orchestration logic; re-test entire matrix |
| `embeddings.py` | **Hard** | Model load, cache, parity with MiniLM |
| E3 ML injection + entailment | **Hard** | Tied to embedder; E6 makes this worse |
| Connectors (E2/E5) | **Medium** | OAuth + Drive/Notion APIs — rewrites working code |
| Operator UI (`ui/static/`) | **N/A** | Static files; language-agnostic |
| Test suite (87 tests) | **High cost** | Full regression rebuild |

### Optional future: hybrid architecture

If a customer needs higher gateway throughput or smaller per-pod memory **after** ML is proven necessary, split by concern — not a full language migration:

```text
┌─────────────────────────────────────┐
│  Rust gateway (axum)                │
│  REST /v1/query, /v1/ingest         │
│  ACL, JWT, orchestration, regex     │
│  audit, rate limits (E4.5)          │
└──────────┬──────────────────────────┘
           │ HTTP or gRPC (internal)
           ▼
┌─────────────────────────────────────┐
│  Python ML service (optional)       │
│  embeddings, injection_ml, NER      │
│  sentence-transformers / Presidio   │
└─────────────────────────────────────┘
           │
           ▼
     Qdrant / pgvector / LLM (external)
```

**Public REST contract stays unchanged** — same paths and JSON schemas documented in [ARCHITECTURE.md § API Surface](../ce/README.md#api-surface). Enterprise buyers integrate against HTTP, not implementation language.

A lighter partial split (no Rust): **connector scheduler** (E5.7 — **shipped**, in-process) calling existing ingest APIs — aligns with [NEXT_STEPS.md § E5](../ce/README.md#phase-e5--operator-ux--production-connectors-46-weeks) without rewriting the core gateway.

### When to revisit

| Trigger | Action |
|---------|--------|
| **Pre-revenue / pre-pilot** | Stay Python; prioritize [GTM_90_DAY.md](../ce/README.md); enable E5.6 + E5.7 when pilot uses Drive |
| **Customer asks about performance** | Profile first; offer E4.2 replicas + external vector DB before Rust |
| **Measured gateway CPU >> LLM wait** (rare) | Spike Rust for hot-path scanners only |
| **Customer mandates no Python in prod** | Roadmap Rust gateway + Python ML sidecar (or ONNX in Rust) |
| **Post–$1M ARR, proven QPS pressure** | Evaluate hybrid; keep CE reference implementation in Python |

### Effort vs payoff (indicative, solo developer)

| Option | Effort | Commercial payoff (now) |
|--------|--------|-------------------------|
| Keep Python; GTM + enable E5.6/E5.7 | 4–6 weeks | **High** |
| Rust gateway + Python ML sidecar | 10–16 weeks | Low–medium until scale is a deal blocker |
| Full Rust parity + test rebuild | 4–9 months | **Low** — regression and GTM risk |

### Sales-facing answer

> *The gateway exposes a stable REST API and can scale horizontally. The reference implementation is Python for transparency and rapid security review. Enterprise deployments can add dedicated replicas and, if required, a performance-optimized gateway tier — without changing your integration contract.*

Do **not** lead with Rust in outbound; lead with **retrieval-time ACL** per [COMMERCIAL.md § Competitive differentiation](../ce/README.md#competitive-differentiation).

---

## Runtime dependencies

From `rag-protection-proxy/pyproject.toml` / `requirements.txt`:

| Package | Role |
|---------|------|
| `fastapi` | REST API, dependency injection, static UI |
| `uvicorn` | ASGI server |
| `httpx` | Async HTTP client for LLM calls |
| `pyyaml` | Policy and ACL file loading |
| `pydantic` | Request/response models |
| `PyJWT[crypto]` | JWT (HS256) and OIDC/JWKS (RS256) group extraction |
| `prometheus-client` | Query/ingest counters |
| `qdrant-client` | Vector store when `RAG_STORE_BACKEND=vector` |
| `sentence-transformers` | Chunk/query embeddings for vector retrieval. **Not** a reranker today. Paid D would use the same package’s `CrossEncoder` — [POST_ACL_RERANK_DESIGN.md](../ce/README.md) |

Dev only: `pytest`, `pytest-asyncio`.

Paid post-ACL rerank (not shipped) adds **no** `cohere` / `voyageai` dependency; HTTP sidecar uses existing **httpx**. Design: [POST_ACL_RERANK_DESIGN.md](../ce/README.md).

Paid HyDE / query expansion (not shipped) reuses **LLMClient** + existing embeddings / RRF; no LangChain. Design: [HYDE_QUERY_EXPANSION_DESIGN.md](../ce/README.md).

---

## Module map

```text
rag_protection_proxy/
├── app.py                 # FastAPI routes, startup seed, admin endpoints
├── pipeline.py            # Query orchestration (ACL → scan → LLM → verify)
├── store.py               # SQLite ingest, create_document_store(), ACL-filtered search
├── vector_store.py        # Qdrant VectorDocumentStore, ACL metadata filter in query
├── embeddings.py          # Sentence-transformer + hash embedder (tests)
├── acl.py                 # Demo tokens, HS256 JWT, OIDC/JWKS, group hierarchy
├── config.py              # Policy / ACL / sample doc loaders
├── context_builder.py     # System prompt + XML context isolation
├── llm.py                 # OpenAI-compatible chat client (httpx)
├── models.py              # Pydantic schemas
├── audit.py               # In-memory security event buffer
├── guardrails/
│   ├── input_pipeline.py  # Post-retrieval chunk scanning
│   ├── output_pipeline.py # Post-generation answer scanning
│   └── citation.py        # Grounding + system-prompt leak detection
└── scanners/
    ├── pii.py             # Email, phone, SSN, credit card
    ├── secrets.py         # API keys, connection strings
    ├── prompt_injection.py# Override phrases, HTML comments, base64
    └── url_threat.py      # Private IPs, disallowed domains
```

---

## LLM integration

`LLMClient` posts directly to an OpenAI-compatible endpoint — no SDK abstraction layer:

```text
POST {RAG_LLM_BASE_URL}/chat/completions
{
  "model": "ai/gemma3-qat",
  "messages": [ system + user with <retrieved_untrusted_context> ],
  "temperature": 0.2,
  "max_tokens": 512
}
```

Default backend: [Docker Model Runner](https://docs.docker.com/ai/model-runner/) (`compose.yml`). Any OpenAI-compatible URL works via `RAG_LLM_BASE_URL`. Laptop paths (Desktop vs `compose.ci.yml`, typical Ollama URLs): [LLM_BACKENDS.md](../ce/guide/LLM_BACKENDS.md).

### Docker Model Runner baseline (no external LLM subscription)

**Decision (2026-06):** Use **Docker Model Runner** as the default chat LLM for local dev, demos, POCs, and the product baseline. **No paid third-party LLM subscription** (OpenAI, Anthropic, Azure OpenAI, etc.) is required to run or sell guardrail evaluations.

| Item | Default |
|------|---------|
| Model | `ai/gemma3-qat` |
| Endpoint | `http://model-runner.docker.internal/engines/v1` (Compose injects via `models.llm` binding) |
| API key | `RAG_LLM_API_KEY=not-needed` |
| Config | `compose.yml`, `.env.example`, `policy.yaml` → `llm.*` |

Compose wires the proxy to Model Runner automatically:

```yaml
models:
  llm:
    model: ${MODEL_RUNNER_MODEL:-ai/gemma3-qat}
services:
  rag-protection-proxy:
    models:
      llm:
        endpoint_var: RAG_LLM_BASE_URL
        model_var: RAG_LLM_MODEL
```

**Prerequisites (not the same as an LLM subscription):**

| Requirement | Notes |
|-------------|-------|
| Docker Desktop **4.40+** | Model Runner enabled (Settings → AI) |
| First-time model pull | Network to download `ai/gemma3-qat` once; inference stays local |
| Host resources | About **16 GB RAM** is the realistic demo floor (Desktop + first model load). See [LLM_BACKENDS.md](../ce/guide/LLM_BACKENDS.md). |

### What works without a paid LLM API

| Use case | Model Runner sufficient? |
|----------|--------------------------|
| Local dev + `bash tools/smoke_rag_proxy.sh` | **Yes** |
| Guardrail demos (ACL, DLP, injection, citation) | **Yes** — when query reaches generation |
| ACL-only paths (no LLM call) | **Yes** — e.g. engineer blocked on payroll |
| [COMMERCIAL_SUMMARY.md § 2-week POC](../ce/README.md#2-week-proof-of-concept) | **Yes** — pass criteria test **security**, not answer quality |
| Air-gapped / private-LLM positioning | **Yes** — see [compliance/DATA_FLOW.md](../ce/README.md) |
| Enterprise self-hosted narrative | **Yes** — LLM is **customer-configured**; local Model Runner counts as on-prem |

This product competes on **security guardrails**, not chat UX or answer benchmarks. A small local model is appropriate for baseline and first paid pilots.

### Other dependencies (not LLM subscriptions)

| Component | When needed | External cost? |
|-----------|-------------|----------------|
| **Chat LLM** (Model Runner) | Query reaches `LLMClient.chat()` | **No subscription** — local inference |
| **Embeddings** (`sentence-transformers`) | `RAG_STORE_BACKEND=vector` or `hybrid` | **No API** — may download `all-MiniLM-L6-v2` from Hugging Face once; cache under `RAG_DATA_DIR/models` |
| **Hash embedder** | `RAG_EMBEDDING_BACKEND=hash` | None — unit tests only; not for production semantic recall |
| **Qdrant** | Vector/hybrid profile | Self-hosted container — no subscription |
| **OIDC** | Customer POC with real IdP | Customer's Okta/Azure contract — not vendor LLM spend |

**Default SQLite backend** avoids embedding downloads entirely — fastest path for guardrail-only demos.

### Production and customer alternatives

`LLMClient` is endpoint-agnostic. Point `RAG_LLM_BASE_URL` (or `policy.yaml` → `llm.base_url`) at any OpenAI-compatible server — still **no OpenAI subscription required** unless the customer chooses one.

| Deployment | Typical `RAG_LLM_BASE_URL` |
|------------|----------------------------|
| **Local demo (default)** | `http://model-runner.docker.internal/engines/v1` |
| **Host dev (no Compose binding)** | `http://localhost:12434/engines/v1` |
| **Kubernetes / Linux prod** | Customer vLLM, Ollama, TGI, on-prem inference |
| **Optional vendor API** | Customer brings API key — gateway unchanged |

Helm defaults reference Model Runner (`deploy/helm/rag-protection/values.yaml`). For real K8s production, document swapping to the customer's private LLM endpoint in the runbook — same env vars, no code change.

Compliance: [compliance/SUBPROCESSORS.md](../ce/README.md) lists **Customer LLM provider** as customer-configured, not a vendor-mandated OpenAI dependency.

### Sales-facing answer

> *The gateway does not require a commercial LLM API. Reference deployments use Docker Model Runner or any OpenAI-compatible private endpoint (vLLM, Ollama, on-prem). The customer chooses the LLM trust boundary; we secure retrieval, context, and responses regardless of model vendor.*

Defer external LLM subscriptions until a specific customer requires a vendor API for answer quality — that is their subprocessor choice per [compliance/DATA_FLOW.md](../ce/README.md), not a product dependency.

### When `POST /v1/query` invokes the LLM

The **Secured RAG Query** panel in `/ui` and any `curl` to `POST /v1/query` run the same `run_query()` pipeline in `pipeline.py`. The LLM is **conditional** — not every request reaches `LLMClient.chat()`.

| Outcome | LLM called? | Typical response |
|---------|-------------|------------------|
| No ACL-authorized chunks match the query | **No** | `"No authorized documents matched your question in the knowledge base."` |
| Chunks retrieved but **all** blocked by input guardrails | **No** | `"Retrieved content was blocked by security guardrails."` (`blocked: true`) |
| At least one chunk passes input scan | **Yes** | Model summarizes sanitized context; citation + output guardrails run afterward |
| LLM unreachable (Model Runner down, timeout) | **Attempted** | Fallback string from `llm.py` — not a grounded answer |
| Citation or output guardrail fails after generation | **Yes** (already ran) | Safe fallback replaces the raw model output (`blocked: true`) |

`include_audit` only adds recent audit events to the JSON response; it does **not** skip or trigger the LLM.

**UI example (does invoke LLM):** `/ui` → Secured RAG Query → preset `exec-demo-token` → query *"What is the Q1 payroll total?"* → **Run Query**. The executive token can retrieve `hr-payroll`; after DLP redacts the sample SSN, the proxy calls the chat model. Use `employee-demo-token` with the same payroll prompt to demo **ACL-only** behavior (no retrieval → no LLM). See [ARCHITECTURE.md § Guardrail Demo Walkthrough](../ce/README.md#guardrail-demo-walkthrough).

### Query Lab and the local LLM

CE **Query Lab** (and the legacy `/ui` Secured RAG Query panel) call the same `POST /v1/query` endpoint. With default Compose settings that means the **local Docker Model Runner** chat model (`ai/gemma3-qat`) — not a cloud API — whenever the pipeline reaches generation.

| Demo | Local LLM called? |
|------|-------------------|
| `hr-demo-token` / `exec-demo-token` + FAQ or payroll sample | **Yes** — chunks pass ACL + input scan |
| `employee-demo-token` + payroll | **No** — ACL miss → empty retrieval |
| Injection demo / jailbreak query | **No** — query blocked before retrieval |
| Poisoned / high-risk chunks only | **No** — `all_chunks_blocked` after retrieval |

### Why empty retrieval skips the LLM (not a general chatbot)

This product is a **secured RAG gateway**, not open chat. With no ACL-authorized matching chunks, calling the model would answer from **parametric memory** (and the system prompt), not from customer documents. That breaks the contract:

- Factual answers must come from **retrieved, ACL-allowed, sanitized** chunks
- Citation / output checks need grounded context to verify against
- An empty-retrieval miss is often an **ACL denial**, not “the KB is empty” — an LLM reply could invent or leak what the user is not allowed to see

So the proxy returns the static miss string and **does not** call `LLMClient.chat()`. A general assistant *would* still generate; this gateway’s job is governed, grounded answers when RAG context exists.

### Empty retrieval vs all chunks blocked by input guardrails

Operators sometimes conflate “nothing relevant in the KB” with “retrieved content was blocked.” They are different outcomes:

| Situation | Pipeline state | Response | Security block? |
|-----------|----------------|----------|-----------------|
| Irrelevant / no ACL match / empty `top_k` | `retrieved` is empty | *“No authorized documents matched your question in the knowledge base.”* | **No** — soft miss, no LLM |
| Top‑k matched, but every chunk fails input scan | Retrieval succeeded; DLP / injection / risk ≥ `input.block_threshold` | *“Retrieved content was blocked by security guardrails.”* (`block_reason: all_chunks_blocked`) | **Yes** — audited block, no LLM |

**Rationale for `all_chunks_blocked`:** retrieval already chose those chunks as the best matches. If all are poisoned, high-risk PII/secrets, or injection, there is **no safe context** left. Calling the LLM with an empty prompt would either invent an answer or still risk leakage/hijack. The proxy refuses generation.

**If documents are merely irrelevant:** they never enter that path — scoring/ACL yields an empty `retrieved` set → soft miss, not `all_chunks_blocked`.

### What the LLM actually does

Local documents are the **source of truth**; the chat model is a **writer**, not a knowledge base.

| Layer | Job |
|-------|-----|
| Store + ACL + scanners | Which text is allowed and safe |
| Chat LLM | Natural-language synthesis of that text (select, paraphrase, combine, cite titles) |
| Citation / output checks | Reject answers that drift off the chunks |

The system prompt (`context_builder.py`) requires answering **only** from `<retrieved_untrusted_context>` blocks, treating retrieved text as untrusted data (never follow embedded instructions). Without the LLM you would dump raw chunks; without the docs you would get ungrounded chat. Here the model is last-mile **summarization** over already-fetched local content.

### Retrieval Explainability vs what reaches the LLM

Query Lab’s **Retrieval Explainability** table (enable `include_retrieval_trace`) shows per-candidate outcomes. Green / `ok` means `selected (ranked survivor)` — chunks that passed quarantine, ACL, score, and `top_k`.

**Those are not automatically the LLM prompt.** Selected chunks still run through **input guardrails**. Only survivors that also pass that scan are placed in `<retrieved_untrusted_context>` with the user query and sent to the model. Selected-but-`blocked` rows appear in **Retrieved Chunks** with `blocked: true` and never become context.

```text
candidates → ACL / quarantine / score / top_k
         → selected (green in explainability)
         → input scan (DLP, injection, risk)
         → context_blocks → LLM (+ citation / output)
```

---

## Retrieval

Two backends share the same `DocumentStoreBackend` contract (`search`, `ingest`, `list_documents`). Selected by `RAG_STORE_BACKEND` (default `sqlite`).

### SQLite (default)

`DocumentStore.search()`:

1. Load all chunks joined with document ACL metadata
2. Skip documents the user cannot access (`user_can_access_document`)
3. Score by **token overlap** between query and chunk text
4. Return top-k by score

Best for fast demos and guardrail testing. Paraphrase queries may miss unless keywords overlap.

### Vector (v1 P0, opt-in)

`VectorDocumentStore.search()`:

1. Embed query (`sentence-transformers/all-MiniLM-L6-v2`)
2. Qdrant similarity search with **ACL metadata filter inside the query** (`build_acl_filter`)
3. Return top-k by cosine score

Best for production-like semantic recall and ACL-at-retrieval demos. Details: [V1_P0_FEATURES.md](../ce/README.md).

Chunking: ~600 characters per chunk on `ingest()` (both backends).

---

## Configuration surface

| Variable | Default | Purpose |
|----------|---------|---------|
| `RAG_POLICY_FILE` | `./config/policy.yaml` | Scanner thresholds, LLM settings |
| `RAG_ACL_FILE` | `./config/acl_policy.yaml` | Demo tokens, JWT, groups |
| `RAG_SAMPLE_DOCS` | `./config/sample_documents.json` | Seed corpus |
| `RAG_DATA_DIR` | `./data` | SQLite path |
| `RAG_LLM_BASE_URL` | Model Runner URL | LLM endpoint (any OpenAI-compatible server) |
| `RAG_LLM_MODEL` | `ai/gemma3-qat` | Model name |
| `RAG_LLM_API_KEY` | `not-needed` | API key — empty/`not-needed` for Model Runner |
| `RAG_EMBEDDING_BACKEND` | `sentence_transformer` | `hash` for tests only |
| `RAG_EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Embedding model when vector/hybrid |
| `RAG_ADMIN_API_KEY` | empty | Admin ingest / policy endpoints |

Full threshold reference: [ARCHITECTURE.md § Configuration Reference](../ce/README.md#configuration-reference).

---

## What is not in the stack

| Technology | Status |
|------------|--------|
| LangChain / LangGraph | Not used |
| LlamaIndex | Not used |
| Vector DB (Pinecone, pgvector) | Not used — Qdrant shipped as opt-in backend |
| Qdrant | **Shipped v1 P0** — opt-in via `RAG_STORE_BACKEND=vector` |
| Embedding models | Default SQLite needs none; vector backend uses `sentence-transformers` |
| External LLM API subscription | **Not required** — Model Runner or customer private LLM |
| Paid OpenAI / Azure OpenAI | Optional — customer choice via `RAG_LLM_BASE_URL` + API key |
| External observability (Datadog, Splunk) | Planned enterprise |
| Corporate IdP (Okta, Azure AD) | **Shipped v1 P0** — OIDC/JWKS in `acl.py` |

---

## Related documentation

- [RETRIEVAL_AND_VECTOR_DB.md](../ce/README.md) — query/ingest flows, vector DB role, no LLM→store path
- [KNOWLEDGE_BASE.md](../ce/README.md) — how ingested documents become answers
- [ARCHITECTURE.md § Component Architecture](../ce/README.md#component-architecture)
- [IMPLEMENTATION_STATUS.md](../ce/README.md) — shipped vs partial vs missing; validate stack; P1/P2 next steps
- [SUCCESS_POTENTIAL.md](../ce/README.md) — why GTM beats language rewrite now
- [NEXT_STEPS.md](../ce/README.md) — E4 replicas, E5 connectors (scale without Rust)
- [compliance/DATA_FLOW.md](../ce/README.md) — LLM trust boundary, air-gapped patterns
- [compliance/SUBPROCESSORS.md](../ce/README.md) — customer-configured LLM provider
- [../rag-protection-proxy/README.md](../ce/README.md) — run and test the service

---

## Document history

| Date | Change |
|------|--------|
| 2026-07-21 | Documented Query Lab ↔ local LLM, empty retrieval vs `all_chunks_blocked`, LLM role, explainability vs LLM context |
| 2026-06-14 | Added [Technology strategy (Python vs Rust)](#technology-strategy-python-vs-rust) |
| 2026-06-14 | Expanded [LLM integration](#llm-integration) — Docker Model Runner baseline, no external LLM subscription |
