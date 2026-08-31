# LangChain integration examples

Examples for wiring **RAG Protection Proxy** into LangChain workflows.

| Doc job | Open |
|---------|------|
| **Learn (plain English + install)** | [docs/ce/learn/02-runtime-and-operations.md § Integration Patterns](../../docs/ce/learn/02-runtime-and-operations.md#integration-patterns-abc) |
| **Hands-on tutorial** | [docs/ce/tutorials/03 §9](../../docs/ce/tutorials/03-extensions-troubleshooting-and-integrations.md#9-langchain-and-pinecone-integration-e7) |
| **Engineering contract** | [docs/ee/phases/e7/E7_2_LANGCHAIN_PINECONE.md](../../ENTERPRISE.md) |
| **Scan API** | [docs/ee/phases/e7/E7_1_SCAN_API.md](../../ENTERPRISE.md) |
| **Product hub** | [docs/product/INTEGRATIONS.md](../../docs/product/INTEGRATIONS.md) |

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| Proxy running | `bash tools/docker_start.sh` from repo root |
| Pinecone Local (Pattern C real upsert) | `bash tools/docker_start.sh --pinecone` — pulls `ghcr.io/pinecone-io/pinecone-index:latest` |
| Python deps | `bash tools/setup_venv.sh` then `source .venv/bin/activate` |
| Standalone pip | `pip install -r examples/requirements.txt` plus `httpx` from [requirements.txt](../../rag-protection-proxy/requirements.txt) |
| Cloud Pinecone (optional) | Customer account + index; not required when using `--pinecone` |

## Environment

```bash
export BASE=http://localhost:8090
export RAG_PROTECTION_URL=$BASE          # or: http://localhost:8090
export RAG_PROTECTION_ADMIN_KEY=rag-admin-demo-key   # ingest / scan (Pattern C)
export RAG_PROTECTION_USER_TOKEN=hr-demo-token       # query (Pattern A)
# Pinecone Local (compose profile pinecone) — defaults match compose.yml:
export PINECONE_INDEX_HOST=http://localhost:5081
export PINECONE_API_KEY=pclocal          # ignored by Pinecone Local
export PINECONE_DIMENSION=8              # must match compose DIMENSION
export PINECONE_NAMESPACE=pattern-c-demo
```

An empty `RAG_PROTECTION_URL` falls back to `http://localhost:8090`.

## Examples

| Script | Pattern | APIs | Status |
|--------|---------|------|--------|
| [full_gateway_query.py](full_gateway_query.py) | **A** — full gateway | `POST /v1/query` | **Works today** |
| [byo_pinecone_ingest.py](byo_pinecone_ingest.py) | **C** — scan before Pinecone | `POST /v1/scan` + local upsert | **Works today** (E7.1 + E7.4 + `--pinecone`) |

Shared client: [examples/python/rag_protection_client.py](../python/rag_protection_client.py)

## Pattern selection

```text
Can users call POST /v1/query?
  YES → full_gateway_query.py (all four guardrails)

Must keep Pinecone for vectors?
  YES → byo_pinecone_ingest.py + [transformers.py](transformers.py)
        + implement allowed_groups filter in Pinecone at query time
```

**Pattern C in one paragraph:** CE scans document text at ingest (`POST /v1/scan`) for input DLP and injection; you embed and upsert the returned `sanitized_text` into **your** Pinecone index with `allowed_groups` metadata; you filter that metadata at query time from IdP groups. CE does **not** enforce Pinecone ACL, citation, or output DLP on that path—see the [learn entry](../../docs/ce/learn/02-runtime-and-operations.md#integration-patterns-abc) and [ACL gap table](../../ENTERPRISE.md#acl-gap--what-to-tell-security-reviewers).

## Quick start — Pattern C with Pinecone Local

```bash
# Prefer sqlite so --pinecone does not also pull in Qdrant via RAG_STORE_BACKEND=vector|hybrid
# In .env: RAG_STORE_BACKEND=sqlite

bash tools/docker_stop.sh --qdrant --pinecone   # clear leftover sidecars
bash tools/docker_start.sh --pinecone
bash tools/setup_venv.sh && source .venv/bin/activate
export RAG_PROTECTION_URL=http://localhost:8090
export RAG_PROTECTION_ADMIN_KEY=rag-admin-demo-key
python examples/langchain/byo_pinecone_ingest.py
```

**Expected:** HR memo accepted; poisoned ticket rejected; **one** vector upserted to Pinecone Local at `http://localhost:5081` (namespace `pattern-c-demo`). Without `--pinecone`, the script still scans and prints a placeholder.

**Notes:**
- Image `ghcr.io/pinecone-io/pinecone-index:latest` is **linux/amd64** (emulated on Apple Silicon).
- Pinecone Local is an in-memory emulator — not production, not a CE store backend (proxy still uses sqlite/qdrant/pgvector).
- **No UI for Local upserts:** `http://localhost:5081/` is 404 (API only). Documents & Ingest shows the **proxy** corpus only — `hr-memo-1` from this script will not appear there. Inspect with:

```bash
curl -s -X POST http://localhost:5081/describe_index_stats \
  -H "Content-Type: application/json" -H "Api-Key: pclocal" \
  -H "X-Pinecone-Api-Version: 2025-01" -d '{}' | python3 -m json.tool
curl -s -X GET "http://localhost:5081/vectors/fetch?ids=hr-memo-1&namespace=pattern-c-demo" \
  -H "Api-Key: pclocal" \
  -H "X-Pinecone-Api-Version: 2025-01" | python3 -m json.tool
```

- Cloud Pinecone: use [console.pinecone.io](https://app.pinecone.io). Proxy Documents UI requires Pattern A/B ingest (`POST /v1/ingest`), not Pattern C.
- Stop with `bash tools/docker_stop.sh --pinecone`.

## Switching Qdrant ↔ Pinecone Local

| Goal | `.env` | Docker |
|------|--------|--------|
| CE/EE semantic retrieval | `RAG_STORE_BACKEND=vector` (or `hybrid`) | `bash tools/docker_start.sh --qdrant` (or `--ee --qdrant`) — **or** plain `docker_start.sh` with no flags; Qdrant still starts from `.env` |
| Pattern C examples | `RAG_STORE_BACKEND=sqlite` | `bash tools/docker_start.sh --pinecone` (or `--ee --pinecone`) |

**Note:** `RAG_STORE_BACKEND=vector|hybrid` starts Qdrant on any `docker_start.sh`, even with neither `--qdrant` nor `--pinecone`. `--pinecone` does not turn Qdrant off.

Always stop the other sidecar first — Compose leaves running containers up:

```bash
bash tools/docker_stop.sh --ee --qdrant --pinecone
```

Full matrix: [COMPOSE_OVERLAYS § Switching](../../ENTERPRISE.md#switching-qdrant-and-pinecone-local).

## LangChain `DocumentTransformer` (E7.4)

Copy-paste adapter: [transformers.py](transformers.py) — `RAGProtectionScanTransformer` subclasses `BaseDocumentTransformer` and calls `POST /v1/scan` per document.

```python
from langchain_core.documents import Document
from transformers import RAGProtectionScanTransformer
from python.rag_protection_client import RAGProtectionClient

client = RAGProtectionClient("http://localhost:8090", admin_token="rag-admin-demo-key")
transformer = RAGProtectionScanTransformer(client)
safe_docs = transformer.transform_documents(documents)
```

In-repo example only — not published to PyPI until a buyer commits.

## Docker sidecar

Proxy beside the LangChain app: [E7_2 § Docker Compose](../../ENTERPRISE.md#docker-compose-topology).

Pinecone Local profile: `compose.yml` service `pinecone-local` (`--profile pinecone`).

## Related docs

- [E7 hub](../../ENTERPRISE.md)
- [Scan API spec](../../ENTERPRISE.md)
- [Compose overlays](../../ENTERPRISE.md)
- [P1 ingest security (shipped)](../../docs/ce/security/P1_INGEST_SECURITY.md)
