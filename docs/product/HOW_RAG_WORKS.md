# How RAG works — plain-English primer

**Audience:** Anyone who needs a clear mental model of Retrieval-Augmented Generation in this product — operators, evaluators, engineers new to the stack.  
**Style:** Full prose. Plain English. Depth docs are linked; this page is the conceptual spine.  
**Related:** [RETRIEVAL_AND_VECTOR_DB.md](../ce/README.md) (flows and roles) · [RAG_QUALITY_VS_SECURITY.md](RAG_QUALITY_VS_SECURITY.md) (rerank, HyDE, guardrails, citations — what we ship vs keep in the client chain) · [KNOWLEDGE_BASE.md](../ce/README.md) (where facts come from) · [CLIENT_USAGE.md](CLIENT_USAGE.md) (how clients call the API) · [#2 extraction monitor](../ce/features/02-extraction-monitor.md) (coverage / breadth / novelty)

---

## What RAG is

**Retrieval-Augmented Generation** means: look up relevant company documents first, then ask a language model to answer using that short, selected context. The model is not expected to invent company facts from training memory alone. It is expected to read the pieces the system retrieved and write a grounded reply.

A useful analogy is a library desk. The **corpus** is every book on the shelves (your ingested knowledge base). The user’s **query** is the question. **Retrieval** is the librarian finding a few relevant pages. **Augmentation** is putting those pages on the desk next to the question. **Generation** is the reader (the LLM) writing an answer from what is on the desk. Security in this product sits around that desk: who may see which books, whether the pages contain secrets or hidden instructions, and whether the written answer stays faithful to the sources.

This repository’s proxy runs a **retrieve-then-generate** pipeline. The proxy searches the store, sanitizes chunks, builds the prompt, calls the chat model once, checks citations, and returns a response. The language model never queries the document store or vector database itself. That design is intentional: if the model could search freely, ACL and DLP would be easy to bypass. See [RETRIEVAL_AND_VECTOR_DB.md](../ce/README.md). Popular quality tricks such as **reranking** and **HyDE** belong in the client’s LangChain/LlamaIndex chain (or a named POC exception), not as default proxy search — [RAG_QUALITY_VS_SECURITY.md](RAG_QUALITY_VS_SECURITY.md).

---

## Are all documents in the corpus passed to the LLM with the query?

**No.** The full corpus is never stuffed into the prompt. Only a small number of relevant, ACL-allowed chunks travel with the question — typically controlled by `top_k` on `POST /v1/query` (default **4**, capped in the schema). Everything else stays in the store.

That selectivity is the point of RAG. Sending every document would be too expensive, too slow, and too leaky: the model would see material the user is not allowed to see, and context windows would fill with noise. Retrieval picks candidates by relevance (keyword overlap on the default SQLite backend, or semantic similarity when the vector backend is enabled). ACL filtering ensures those candidates are also ones the caller’s groups may read. If nothing authorized matches, or every retrieved chunk fails input scanning, the pipeline can return a safe message **without** calling the LLM at all ([TECH_STACK.md § When POST /v1/query invokes the LLM](TECH_STACK.md#when-post-v1query-invokes-the-llm)).

So for a payroll question asked by an engineer, the system does not “pass HR’s entire archive plus the FAQ.” It searches, keeps only allowed hits, takes the top few, and only those texts (after scanning) become context for generation.

---

## What “augmentation” means here

**Augmentation** is the step where the retrieved chunks are **added into the prompt** together with the user’s question, before the LLM runs. The model does not answer from the question alone; it answers from **question + short selected context**. That “plus context” step is the “A” in Retrieval-**Augmented** Generation.

In this proxy, after search returns allowed chunks, `context_builder.py` packs them into chat messages, wrapped in isolation markers such as `<retrieved_untrusted_context>` so system instructions stay separate from untrusted document text. That combined message list is what `LLMClient.chat()` sends to the model. Augmentation is therefore a prompt-construction step owned by the gateway, not a separate network protocol and not a second model call.

<a id="what-isolate-means"></a>
### What isolate means

**Isolate** is that packing step. It is not a second search, not a reranker, and not a network hop. After ACL retrieval and chunk scan, each surviving paragraph is wrapped in `<retrieved_untrusted_context>` tags. The system prompt tells the model to treat that text as untrusted **data** — answer from it, never obey instructions that appear inside it.

That defends **indirect prompt injection**: a retrieved ticket or memo can contain “ignore previous instructions.” Input scanning tries to drop or sanitize that. Isolate is defense in depth so a slipped jailbreak string is still labeled untrusted and kept out of the system prompt. The citation gate then checks the answer against those same isolated texts.

Paid quality hops such as post-ACL rerank sit **before** isolate and do not replace it ([POST_ACL_RERANK_DESIGN.md § Isolate](../ce/README.md#isolate)). Wrappers and threat model: [GUARDRAIL_3_INJECTION.md — Structural isolation](../ce/security/GUARDRAIL_3_INJECTION.md).

### What the operator UI shows (and does not show)

**Query Lab does not show the packed LLM prompt.** After a query, the console lists the **retrieved chunks** from the `/v1/query` response — title, document id, score, scan verdict, and text. Those are the same sanitized texts that feed `context_builder.py`, so you can see *what content* was retrieved. The UI does **not** render the full messages object that goes to the model: not the system prompt, not the “Authorized retrieved context” wrapper copy, and not the `<retrieved_untrusted_context>` XML tags. Audit debug (when enabled) may show truncated previews such as `query_preview`, `input_preview`, or `output_preview`; those are forensic snippets, not a dump of the packed context blob either.

---

## What embeddings are in a vector store

An **embedding** is a numeric fingerprint of meaning. An embedding model turns a piece of text — a document chunk at ingest time, or the user’s query at search time — into a list of floating-point numbers (a **vector**). Texts with similar meaning land near each other in that high-dimensional space, even when they do not share the same keywords.

A **vector store** (for example Qdrant in this project) holds those vectors along with payload metadata such as document id, chunk text, and `allowed_groups`. At query time the proxy embeds the question, asks the store for nearby chunk vectors, applies ACL metadata filters, and returns the top matches. That is **semantic retrieval**: matching by meaning rather than only by shared words.

Example: a user asks *“When is the helpdesk open?”* and a FAQ chunk says *“Support hours are Monday–Friday, 9am–6pm Eastern.”* Lexical SQLite search may miss the paraphrase if few tokens overlap. Vector search can still rank that chunk highly because the embeddings are close.

Important boundaries for this product:

- Embeddings and the vector DB answer *which chunks look relevant?* They do **not** redact PII, block injection, or verify citations. Those remain proxy guardrails.
- The chat LLM still does not talk to the vector store. The proxy embeds and searches; then it augments and generates.
- Vector retrieval is **opt-in** (`RAG_STORE_BACKEND=vector`). **Hybrid** (`RAG_STORE_BACKEND=hybrid`) runs lexical SQLite **and** Qdrant, then fuses ranks (E3.6). The default SQLite path does not require an embedding model. To prove hybrid beats either leg alone on a dirty demo corpus, ingest a unique SKU plus a disjoint paraphrase — [TC-E3-610](../../ENTERPRISE.md#tc-e3-610--isolated-complementary-recall-proof). Engineering detail: [RETRIEVAL_AND_VECTOR_DB.md](../ce/README.md) · [QDRANT_CONFIGURATION_AND_TESTING.md](QDRANT_CONFIGURATION_AND_TESTING.md) · [E3.6](../../ENTERPRISE.md) · `embeddings.py` / `vector_store.py`.
- The MiniLM embedder is a **bi-encoder**: question and chunk are fingerprinted **separately**, then compared with cosine. A **cross-encoder reranker** (Paid D, not shipped) instead reads question and chunk **together**. That is a different model and a different job — [POST_ACL_RERANK_DESIGN.md § Bi-encoder vs cross-encoder](../ce/README.md#bi-encoder-vs-cross-encoder).

### What “cosine” means here (not mean square error)

When this project says **cosine** (Qdrant `Distance.COSINE`, `_cosine` helpers, ML injection / citation thresholds), it means **cosine similarity** between two embedding vectors — how aligned their **directions** are — not mean square deviation / mean square error (MSE).

For vectors \(a\) and \(b\):

\[
\text{cosine}(a,b) = \frac{a \cdot b}{\|a\|\,\|b\|}
\]

| Score | Meaning |
|-------|---------|
| **~1.0** | Same direction → very similar meaning |
| **~0.0** | Orthogonal → unrelated |
| **Lower / negative** | Dissimilar |

Embeddings in this proxy are L2-normalized (sentence-transformers `normalize_embeddings=True`, and `HashEmbedder` also unit-normalizes). Cosine is preferred over MSE because similar texts can differ in magnitude while still pointing the same way; MSE would treat that magnitude gap as “error,” which is usually the wrong signal for semantic match.

**Where cosine is used:**

| Path | Role |
|------|------|
| Vector retrieval (`vector_store.py`) | Qdrant ranks chunks by cosine distance/similarity to the query embedding |
| ML injection (`scanners/injection_ml.py`) | Cosine to jailbreak prototype embeddings; default block threshold `0.72` |
| Citation entailment (`guardrails/citation.py`) | Cosine between answer sentences and source-chunk embeddings when entailment is enabled |

With `RAG_EMBEDDING_BACKEND=hash` (tests/CI), those scanners fall back to **lexical** overlap instead of real cosine-on-ML-embeddings.

---

## Coverage, breadth_ratio, and novelty_ratio

These three numbers are **not** part of ordinary RAG answer quality, and they are **not** fields the retrieval engine “returns” as search scores. They belong to this product’s **corpus-extraction monitor** ([#2](../ce/features/02-extraction-monitor.md)): a behavioral check on whether an *authorized* user is quietly walking the knowledge base across many individually allowed queries.

ACL, DLP, and per-query rate limits each see one request at a time. Extraction scoring looks across a **sliding window** of recent retrievals for one subject (`tenant_id` + user). After each allowed query, the monitor records which `document_id`s were touched, then derives three signals. Severity is decided only after the window has enough queries (`window_queries ≥ min_window_queries`): **severe** if coverage ≥ `severe_coverage` or breadth ≥ `breadth_ratio_threshold`; **elevated** (if not already severe) if coverage ≥ `elevated_coverage` or novelty ≥ `novelty_ratio_threshold`; otherwise **none**.

### What coverage is — and what it exposes

**Corpus coverage** asks how much of the whole tenant corpus this person has touched recently. It is distinct documents in the window divided by total tenant document count. Coverage is inactive when the corpus is smaller than `min_corpus_size`, so tiny demo stores do not trip by accident. High coverage means a large share of the knowledge base has already been reached — the natural end state of a scrape. The vulnerability is **authorized corpus reconstruction**: rebuilding large parts of the store through many legitimate-looking questions without needing a bulk export API.

### What breadth is — and what it exposes

**Breadth** (the `breadth_ratio`) asks how widely the subject is spreading across documents relative to how many times they asked. It is distinct documents divided by queries in the window. Staying on one topic keeps breadth low. Hitting many different documents keeps it high. The ratio can exceed `1.0` when a single query returns several documents (for example high `top_k` on a large or bloated store). High breadth looks like walking the shelves — enumeration — not ordinary follow-up Q&A. The vulnerability it surfaces is **authorized breadth abuse / aggregation over retrieval**: an insider or scripted client reconstructing payroll data, runbooks, tickets, or wiki pages piece by piece. Each request can still pass ACL and DLP; the cross-query pattern is what gives the scrape away. In this product, crossing `breadth_ratio_threshold` with a full window raises **severe**.

### What novelty is — and what it exposes

**Novelty** (the `novelty_ratio`) asks how often a new query still unlocks at least one document the subject had not seen yet in the window. It is the share of window queries that added a previously unseen `document_id`. Re-asking about the same sources does not count. High novelty is the “map the unknown” shape of extraction: sustained exploration that keeps expanding the set of touched documents. Breadth asks whether asks are *wide per query*; novelty asks whether asks keep unlocking *new* territory. The vulnerability is the same authorized-extraction family, seen as systematic first-time unlocks rather than sheer spread. In this product, crossing `novelty_ratio_threshold` raises **elevated** only — novelty never drives severe by itself.

Policy knobs live under the `extraction:` block in the active policy YAML (reload with `POST /admin/reload-policy`). Implementation: `guardrails/extraction.py`. UI demos that isolate breadth or novelty (and the query sequences that actually work) are in [lab9 UI_TESTING](../../ENTERPRISE.md#ui-demo-cases-trigger--artifacts).

### How those ratios are “passed back”

Usually they are **not** returned on a normal successful `/v1/query` response. They appear as security telemetry:

- **Audit Log** events with `kind=extraction_suspected`, including finding detail such as `coverage`, `breadth_ratio`, `novelty_ratio`, `triggered_by`, and a human `trigger_summary`
- **Live watch:** `GET /admin/extraction/watch` for elevated/severe subjects still in the in-memory window
- **Query response** only when extraction actually pauses traffic (`action: challenge` or `throttle`): `block_reason=extraction_suspected` plus `block_detail` with the cause line

With the common soft-demo setting `action: alert`, traffic keeps flowing even when audit records elevated/severe. Waiting out `window_seconds` or restarting the proxy clears live watch state; it does not delete historical audit rows.

Do not confuse extraction **corpus coverage** with **citation coverage** (`citations.coverage_ratio` on the query path). Citation coverage asks what fraction of answer sentences were grounded in the retrieved chunks for *this* response. Extraction coverage asks what fraction of the *tenant corpus* a subject has touched across many queries.

---

## What parameters are passed back in general

For the everyday RAG path, the client sends something like a natural-language `query` and optional `top_k`, plus flags such as `include_audit`, `audit_debug`, or `include_retrieval_trace`. The proxy’s `QueryResponse` typically returns:

- **`answer`** — the model’s text, or a safe block / fallback message
- **`blocked`**, **`block_reason`**, **`block_detail`** — when a guardrail or extraction action stopped or challenged the request
- **`chunks`** — the retrieved pieces used (or considered), with ids, document id, title, text, score, and scan status
- **`citations`** — grounding check results when that path runs (including citation `coverage_ratio` and per-claim detail)
- Optional **`retrieval_trace`**, **`audit`**, query/output verdicts, **`subject`**, **`groups`**, and routing metadata

That contract is the FastAPI schema in `rag_protection_proxy/models.py` (`QueryRequest` / `QueryResponse`). Client usage in prose: [CLIENT_USAGE.md](CLIENT_USAGE.md). Extraction ratios, when relevant, ride on audit/admin surfaces as described above — not as ordinary “search hit” fields.

---

## Is there a standard RAG data exchange protocol?

**There is no single industry-standard wire protocol for RAG** the way HTTP is the standard for the web. RAG is an **architecture pattern** (retrieve, then generate), not a mandatory packet format.

In practice, systems exchange data with several different contracts:

| Hop | What people typically use |
|-----|---------------------------|
| Client app ↔ RAG gateway | Custom REST or RPC — here, mainly `POST /v1/query`, `POST /v1/ingest`, related admin/audit endpoints |
| Gateway ↔ chat LLM | Often an OpenAI-style chat completions API (`messages` with roles) |
| Gateway ↔ vector / document store | Store-specific APIs (Qdrant, Pinecone, pgvector, SQLite, …) |
| Agents ↔ tools (adjacent) | Tool schemas and gateways (in this product, HTTP tool invoke and optional MCP backends) — useful for agents, but **not** “the RAG protocol” |

So the conceptual RAG exchange is: **question in → retrieved context + answer (or block) out**. This product’s concrete exchange is its HTTP JSON schemas and audit event kinds. Adjacent standards (OpenAI chat APIs, MCP for tools) may appear in the stack, but none of them alone defines how every RAG system must pass chunks, scores, or security metrics.

---

## End-to-end picture in one paragraph

A user authenticates and asks a question. The proxy scans the question, searches only documents that user’s groups may see, and keeps at most `top_k` relevant chunks. Those chunks are scanned again, then **augmented** into an isolated prompt. The LLM generates an answer from that short context; citation and output checks run before the reply is returned with chunk metadata (and optional audit). Separately, if extraction monitoring is enabled, the proxy remembers which documents that subject retrieved over a sliding window, computes **coverage**, **breadth_ratio**, and **novelty_ratio**, and may alert, challenge, or throttle when the pattern looks like corpus walking. Embeddings, when the vector backend is on, only change *how* relevant chunks are found; they do not replace ACL, DLP, citation, or extraction controls, and they do not put the entire corpus into the model.

---

## Related documentation

| Topic | Document |
|-------|----------|
| Retrieval flows, LLM vs store | [RETRIEVAL_AND_VECTOR_DB.md](../ce/README.md) |
| Rerank, HyDE, guardrails, citations | [RAG_QUALITY_VS_SECURITY.md](RAG_QUALITY_VS_SECURITY.md) |
| Where business facts come from | [KNOWLEDGE_BASE.md](../ce/README.md) |
| How clients call RAG + MCP | [CLIENT_USAGE.md](CLIENT_USAGE.md) |
| Product guardrail requirements | [RAG_Protection.md](../ce/README.md) |
| Corpus-extraction monitor | [ce/features/02-extraction-monitor.md](../ce/features/02-extraction-monitor.md) |
| Qdrant / embeddings ops | [QDRANT_CONFIGURATION_AND_TESTING.md](QDRANT_CONFIGURATION_AND_TESTING.md) |
| Cosine similarity (vs MSE) | [§ What “cosine” means here](#what-cosine-means-here-not-mean-square-error) |
| Pipeline diagrams | [ARCHITECTURE.md](../ce/README.md) |
