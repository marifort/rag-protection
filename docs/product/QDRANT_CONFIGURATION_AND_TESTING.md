# Qdrant configuration, persistence, and testing

This guide explains how Qdrant fits into RAG Protection: what it stores, when ingest writes to it, how Docker volumes behave across rebuilds, why documents can “still appear” after a backend switch, and how to inspect and test the vector corpus.

**Audience:** operators, QA, and developers enabling `vector` or `hybrid` retrieval.

**Related:** [RETRIEVAL_AND_VECTOR_DB.md](../ce/README.md) · [V1_P0_FEATURES.md](../ce/README.md) · [E3.6 Hybrid retrieval](../../ENTERPRISE.md) · [COMPOSE_OVERLAYS.md](../../ENTERPRISE.md) · [DEVELOPER_GUIDE §6.3](../ce/guide/DEVELOPER_GUIDE.md#63-runtime-data)

---

## Quick answers

| Question | Answer |
|----------|--------|
| Does Qdrant store documents for the app? | **Yes, when** `RAG_STORE_BACKEND` is `vector` or `hybrid`. Default `sqlite` never uses Qdrant. |
| What exactly is stored? | **Chunked** text + embeddings + ACL/metadata payloads — not original files. |
| Does every ingest write to `qdrant-data`? | **Only** for `vector` / `hybrid`, and only if Qdrant is reachable at ingest time. |
| Are old docs re-uploaded into Qdrant on app rebuild? | **No.** Rebuild does not migrate SQLite → Qdrant. Surviving points come from the **persisted `qdrant-data` volume**, or from **re-seeding** `sample_documents.json`. |
| Why do docs still show after switching from `sqlite` to `hybrid`? | Hybrid **lists/counts from SQLite**. The UI can show the old SQLite corpus even when Qdrant was never backfilled. |
| Why a canary fires after retire / the id is missing from Documents? | Hybrid **retrieves** from Qdrant too. A leftover `metadata.canary` point can trip `#3` while SQLite list/retire 404. Operator notes: [03-canary-docs.md](../ce/features/03-canary-docs.md#operator-notes-theft-card-hybrid-retrieval-and-missing-retire-rows). |
| Why do demo docs appear after switching to `vector`? | Startup **re-ingests** the sample corpus into the active backend (Qdrant). Custom SQLite-only docs do **not** migrate. |
| How do I browse points? | Qdrant dashboard at `http://localhost:6333/dashboard`, collection `RAG_QDRANT_COLLECTION` (default `rag_chunks`). |

---

## Configuration

### Environment variables

| Variable | Default | Role |
|----------|---------|------|
| `RAG_STORE_BACKEND` | `sqlite` | `sqlite` · `vector` · `hybrid` · `pgvector` (EE) |
| `RAG_QDRANT_URL` | `http://localhost:6333` | Host process URL. In Compose, proxy uses `http://qdrant:6333`. |
| `RAG_QDRANT_COLLECTION` | `rag_chunks` | Base collection name. Non-default tenants use `{collection}_{tenant_id}`. |
| `RAG_SAMPLE_DOCS` | `./config/sample_documents.json` | Demo corpus re-ingested when a tenant store is first opened in a process. |
| `RAG_DATA_DIR` | `./data` (Compose: `/data`) | SQLite DBs, audit, writable policy — **not** Qdrant storage. |

Factory: `create_document_store()` in `rag-protection-proxy/rag_protection_proxy/store.py`.

### Backend behavior

| Backend | Lexical (SQLite) | Vector (Qdrant) | Ingest writes | List / count / detail | Search |
|---------|------------------|-----------------|---------------|------------------------|--------|
| `sqlite` | Yes | No | SQLite only | SQLite | Token overlap + app-side ACL |
| `vector` | No | Yes | Qdrant only | Qdrant | Embed + similarity + **ACL filter inside Qdrant query** |
| `hybrid` | Yes | Yes | **Both** (same ingest call) | **SQLite** (`HybridDocumentStore` delegates list/count/detail to lexical) | RRF fusion of both legs; each leg applies its own ACL |

`pgvector` is an Enterprise backend and is out of scope for this Qdrant-focused guide.

### Docker: profile and volume

In `compose.yml`:

- Service `qdrant` is under Compose profile **`qdrant`** (legacy name `vector` is normalized to `qdrant` by `docker_start.sh`).
- Storage mount: named volume **`qdrant-data`** → container path **`/qdrant/storage`**.
- Proxy has optional `depends_on: qdrant` so CE can start without the profile.

Start with Qdrant:

```bash
# Explicit
bash tools/docker_start.sh --qdrant

# Or set backend in .env — docker_common.sh auto-enables the qdrant profile for vector|hybrid
RAG_STORE_BACKEND=hybrid   # or vector
bash tools/docker_start.sh
# ↑ starts Qdrant even with no --qdrant / --pinecone flags
```

**Not Pinecone:** `--pinecone` starts Pinecone Local for Pattern C examples only and does **not** cancel `.env` Qdrant auto-start. To switch stacks, see [COMPOSE_OVERLAYS § Switching](../../ENTERPRISE.md#switching-qdrant-and-pinecone-local).

Inside the proxy container, use `RAG_QDRANT_URL=http://qdrant:6333`. From the host (dashboard, curl, host-run uvicorn), use `http://localhost:6333`.

---

## Does Qdrant store documents?

Yes — for `vector` and `hybrid` — but as **retrieval chunks**, not as uploaded files.

On ingest (`VectorDocumentStore.ingest` in `vector_store.py`):

1. Existing points for that `document_id` are deleted (replace semantics).
2. Content is split into chunks (default ~600 characters).
3. Each chunk is embedded.
4. Each chunk is upserted as a Qdrant **point**: vector + **payload**.

Typical payload fields:

| Field | Purpose |
|-------|---------|
| `chunk_id` | e.g. `public-faq::0` |
| `document_id` | Logical document id |
| `chunk_index` | Order within the document |
| `title` | Document title |
| `text` | Chunk body (used as RAG context) |
| `allowed_groups` | ACL labels for in-query filter |
| `metadata` | Classification, quarantine flags, connector fields, etc. |
| `status` | e.g. `active` / `quarantined` |

Compliance note: self-hosted or cloud Qdrant may hold embeddings, chunk text, and ACL metadata. See [SUBPROCESSORS.md](../ce/README.md).

---

## How `qdrant-data` is populated

The Docker volume is **not** filled by copying `./data` or by a Compose “seed” of SQLite into Qdrant. It is filled by **Qdrant’s storage engine** when the proxy upserts points over HTTP.

```text
POST /v1/ingest  (or sample seed, canary, connector ingest)
  → store.ingest(...)
  → for hybrid: SQLite ingest + VectorDocumentStore.ingest
  → qdrant-client upsert → http://qdrant:6333
  → Qdrant writes under /qdrant/storage
  → that directory is the Docker volume qdrant-data
```

Anything that calls the same store API can populate the volume when the backend uses Qdrant:

- `POST /v1/ingest`
- Startup sample corpus sync (`TenantDocumentStore._sync_sample_corpus`)
- Canary seed
- EE connector sync (when it re-ingests)

If Qdrant is down or unreachable at ingest time, those points never land in `qdrant-data` (hybrid may still succeed on the SQLite leg depending on error handling — treat Qdrant availability as required for a complete hybrid write).

---

## Rebuilds and previously ingested documents

### What rebuild does *not* do

There is **no** startup job that:

- copies SQLite documents into Qdrant,
- re-embeds the historical SQLite corpus, or
- “uploads” `./data` into `qdrant-data`.

`acl-backfill` patches **ACL metadata on existing vector points**; it does not migrate content from SQLite.

### What actually preserves Qdrant data across rebuild

If you rebuild or restart the **proxy image/container** without removing volumes, **`qdrant-data` remains**. Qdrant reloads points from `/qdrant/storage`. That is why previously ingested vector/hybrid docs are still searchable after an app rebuild: they were already on the volume from earlier upserts, not because rebuild re-ran ingest for user docs.

Wiping history:

| Action | Effect on Qdrant corpus |
|--------|-------------------------|
| `docker compose restart` / image rebuild | Usually **keeps** `qdrant-data` |
| `docker compose down` (no `-v`) | Keeps named volumes |
| `docker compose down -v` | **Deletes** `qdrant-data` — corpus gone |
| Delete volume manually | Same |

SQLite lives under the bind mount `./data` (Compose: `./data:/data`). Resetting SQLite does **not** reset Qdrant, and vice versa. The stores do **not** mirror automatically.

### Sample corpus re-seed (important nuance)

On first access to a tenant store in a process, `TenantDocumentStore` re-ingests every document from `RAG_SAMPLE_DOCS` / `sample_documents.json` into the **current** backend:

```text
for_tenant(tid)
  → create_document_store(...)   # respects RAG_STORE_BACKEND
  → _sync_sample_corpus(tid)     # store.ingest(...) for each sample doc
```

The in-memory `_seeded` set is per process, so **every proxy start** re-runs sample ingest (idempotent replace by `document_id`).

Consequences:

- After switching to `vector` or `hybrid` and restarting, **demo** docs appear in Qdrant even if you never ingested them while Qdrant was configured — because seeding re-upserts them.
- This is easy to confuse with “my old SQLite corpus was migrated.” Only the sample file is re-seeded; **custom** docs ingested earlier under `sqlite` alone are **not** pushed to Qdrant by this path.

---

## Switching backends: why docs can still “be there”

### Case A — `sqlite` → `hybrid`

This is the usual source of confusion when `.env` ends up as `RAG_STORE_BACKEND=hybrid`.

1. While on `sqlite`, every ingest wrote only to `documents.db` under `RAG_DATA_DIR`.
2. `qdrant-data` was **not** continuously populated.
3. After switching to `hybrid` and rebuilding:
   - **List / count / document detail still read SQLite**, so the UI and many admin views still show the old corpus.
   - Qdrant receives sample re-seed (and any **new** hybrid ingests).
   - Old custom SQLite docs are **not** automatically upserted into Qdrant.

So “all previously ingested docs were there, like for sqlite” often means **SQLite still owns the catalog**, not that Qdrant was backfilled.

Hybrid search fuses lexical + vector. A document that exists only in SQLite can still contribute via the lexical leg; it may be absent from Qdrant until you re-ingest.

### Case D — retire / delete in SQLite, Qdrant point remains

The inverse of Case A. Hybrid **catalog** (Documents & Ingest, `GET /admin/canary/list`, `POST /admin/canary/retire`) is SQLite. Hybrid **search** still fuses Qdrant.

If `./data` was reset, retire ran while Qdrant was down, or the vector delete failed, a canary can remain as a Qdrant point (`metadata.canary: true`) with no SQLite row. Ordinary queries (especially high `top_k`) can retrieve it, `#3` fires and **scrubs** the chunk, and the UI has no row to retire. Scroll/delete by `document_id` on collection `RAG_QDRANT_COLLECTION` (default `rag_chunks`). Full operator path: [canary card — hybrid orphans](../ce/features/03-canary-docs.md#operator-notes-theft-card-hybrid-retrieval-and-missing-retire-rows).

**Do not use `INV4419` / “when is the helpdesk open?” to prove hybrid advantage** on this stack. `public-faq` already owns the hours paraphrase and token `open` overlaps incident runbooks, so hybrid looks identical to lexical. Use unique tokens that do not exist in FAQ/runbooks — [TC-E3-610](../../ENTERPRISE.md#tc-e3-610--isolated-complementary-recall-proof).

### Case B — `sqlite` → `vector`

List/search go only to Qdrant.

- Demo docs from `sample_documents.json` reappear via startup seed.
- Custom docs that lived only in SQLite **disappear** from the app’s store API until re-ingested (SQLite file may still exist on disk but is unused).

### Case C — wipe Qdrant volume, keep `./data`, stay on `hybrid`

SQLite catalog still lists old docs; Qdrant may only have whatever was re-seeded or newly ingested. Semantic recall for unsynced docs is incomplete until you re-ingest.

### Repopulating Qdrant after a wipe or backend switch

1. Re-ingest via `POST /v1/ingest` (hybrid writes both stores).
2. Rely on EE connector sync if the source of truth is Drive/Notion/etc.
3. Do **not** expect rebuild alone to restore custom vector points from SQLite.

---

## Inspecting ingested documents in the Qdrant console

### Dashboard

1. Ensure Qdrant is running (`docker compose ps qdrant`, or start with `--qdrant` / `vector|hybrid` backend).
2. Open **http://localhost:6333/dashboard**.
3. Connect to the local instance (default URL is fine for this stack).
4. Open collection **`rag_chunks`** (or your `RAG_QDRANT_COLLECTION` / tenant-suffixed name).
5. Browse **Points** — each point is a chunk; read `document_id`, `title`, `text`, `allowed_groups`, `status` in the payload.

There is no separate “document browser” in Qdrant beyond points/payloads. Full-document assembly is a proxy concern (`get_document_detail`); in hybrid that still comes from SQLite.

### API checks (host)

```bash
# Health
curl -sS http://localhost:6333/healthz

# Collections
curl -sS http://localhost:6333/collections | jq

# Point count / collection info
curl -sS http://localhost:6333/collections/rag_chunks | jq '.result.points_count'

# Scroll sample payloads (no vectors)
curl -sS -X POST http://localhost:6333/collections/rag_chunks/points/scroll \
  -H 'Content-Type: application/json' \
  -d '{"limit": 5, "with_payload": true, "with_vector": false}' | jq
```

### Proxy-side checks

```bash
curl -sS http://localhost:8090/health | jq '.store_backend, .status'
```

Remember: with `hybrid`, a healthy proxy and a non-empty document list do **not** prove Qdrant holds every listed document. Confirm with the dashboard or scroll API above.

---

## Testing guidance

### Local stack

```bash
# .env (example)
RAG_STORE_BACKEND=hybrid          # or vector
RAG_QDRANT_URL=http://qdrant:6333 # Compose network
RAG_QDRANT_COLLECTION=rag_chunks

bash tools/docker_start.sh --qdrant   # or --ee --qdrant
# smoke helpers also accept env overrides:
RAG_STORE_BACKEND=vector RAG_QDRANT_URL=http://localhost:6333 bash tools/smoke_rag_proxy.sh
```

Host-side tools and smoke scripts that talk to Qdrant from the Mac/Linux host should use `localhost:6333`, not the Docker DNS name `qdrant`.

### Automated tests

| Area | Location |
|------|----------|
| ACL filter, list/count, paraphrase | `rag-protection-proxy/tests/test_vector_store.py` |
| Store factory (`vector` / `hybrid`) | `tests/test_store_factory.py` |
| Hybrid RRF | `tests/test_e3.py` |
| Live / integration pipeline | `tests/integration/test_vector_pipeline.py` |
| Optional live probe VEC001 | `tools/rag-scan --qdrant http://localhost:6333` (or `tools/rag-score --qdrant …`) — flags sampled payloads **missing** `allowed_groups` only; does not classify docs or score over-broad groups (that is ACL002 on `--sample-docs`) |

In-process tests often use `RAG_QDRANT_URL=:memory:` so no Docker Qdrant is required.

Host pytest inherits `.env`. If `RAG_STORE_BACKEND=hybrid` (or `vector`) and `RAG_QDRANT_URL=http://qdrant:6333`, setup fails with `nodename nor servname provided` because `qdrant` is Compose DNS. Override for in-process suites that do not need the live store (example: `test_tools_gateway.py`):

```bash
RAG_STORE_BACKEND=sqlite RAG_QDRANT_URL=:memory: \
  pytest rag-protection-proxy/tests/test_tools_gateway.py -k ssrf_url_in_body -q
```

### Suggested manual verification matrix

| Scenario | Expectation |
|----------|-------------|
| `sqlite` ingest, then open Qdrant dashboard | Collection empty or unchanged (no write path). |
| `vector` or `hybrid` ingest with Qdrant up | New points for that `document_id` in `rag_chunks`. |
| Rebuild proxy, volumes intact | Same points still in dashboard. |
| `down -v`, restart hybrid | Sample docs return via seed; custom SQLite-only history not in Qdrant until re-ingest. |
| Switch `sqlite` → `hybrid` without re-ingest | UI list still shows SQLite docs; Qdrant may only have samples until new ingests. |
| Switch `sqlite` → `vector` | Catalog is Qdrant-only; samples re-seeded; old custom SQLite docs not listed. |

### ACL nuance (do not “simplify” in tests)

- **SQLite:** quarantine + `user_can_access_document` in application code **before** scoring.
- **Qdrant:** `build_acl_filter()` is applied **inside** the vector query; unauthorized points must not return as candidates.
- **Hybrid:** both legs filter before RRF fusion.

See [DEVELOPER_GUIDE §6.4](../ce/guide/DEVELOPER_GUIDE.md#64-acl-placement-differs-by-backend).

---

## Common pitfalls

1. **Assuming list UI ≡ Qdrant contents** under `hybrid` — list is SQLite.
2. **Assuming rebuild migrates** SQLite → Qdrant — it does not.
3. **Confusing sample re-seed with migration** of user-ingested docs.
4. **Wrong Qdrant URL** — `qdrant:6333` in containers, `localhost:6333` on the host. Host pytest with `.env` `RAG_QDRANT_URL=http://qdrant:6333` fails the same way; pin `RAG_STORE_BACKEND=sqlite RAG_QDRANT_URL=:memory:` for in-process tests.
5. **Ingesting while Qdrant is down** — volume never receives those upserts.
6. **Resetting only one store** — `./data` and `qdrant-data` are independent.
7. **Forgetting `--profile qdrant` / `--qdrant`** when `RAG_STORE_BACKEND` is not set to `vector|hybrid` (scripts auto-enable from env when backend needs it).
8. **Assuming Documents & Ingest / canary retire cleared Qdrant** — leftover canary points still retrieve under hybrid and still trip `#3`.

---

## Code map

| Concern | Location |
|---------|----------|
| Backend factory | `store.py` → `create_document_store()` |
| Hybrid dual write / SQLite list | `store.py` → `HybridDocumentStore` |
| Qdrant ingest, search, ACL filter | `vector_store.py` → `VectorDocumentStore`, `build_acl_filter()` |
| Sample corpus on tenant open | `tenant_store.py` → `_sync_sample_corpus()` |
| Compose service + volume | `compose.yml` → `qdrant`, volume `qdrant-data` |
| Auto-enable vector profile | `tools/docker_common.sh` → `maybe_enable_vector_from_env()` |

---

## Related documentation

| Topic | Document |
|-------|----------|
| Retrieval vs LLM roles | [RETRIEVAL_AND_VECTOR_DB.md](../ce/README.md) |
| v1 P0 vector + OIDC | [V1_P0_FEATURES.md](../ce/README.md) |
| Hybrid RRF (E3.6) | [E3_6_HYBRID_RETRIEVAL.md](../../ENTERPRISE.md) |
| Canary trip with no SQLite row | [03-canary-docs.md operator notes](../ce/features/03-canary-docs.md#operator-notes-theft-card-hybrid-retrieval-and-missing-retire-rows) |
| Live complementary-recall proof (unique SKU + disjoint paraphrase) | [TC-E3-610](../../ENTERPRISE.md#tc-e3-610--isolated-complementary-recall-proof) · [E3.6 live proof](../../ENTERPRISE.md#live-complementary-recall-proof-dirty-corpus) |
| Compose profiles / `--qdrant` | [COMPOSE_OVERLAYS.md](../../ENTERPRISE.md) |
| Runtime data & ACL placement | [DEVELOPER_GUIDE.md](../ce/guide/DEVELOPER_GUIDE.md) |
| Vector ACL backfill (metadata only) | [tools/acl_backfill README](../../tools/acl_backfill/README.md) |
| Subprocessor / data categories | [SUBPROCESSORS.md](../ce/README.md) |
