# RAG quality vs security — rerank, HyDE, guardrails, citations

**Audience:** Founder, solutions engineer, evaluators, and anyone who asks whether this product includes popular RAG *quality* tricks (reranking, HyDE, query expansion) as well as *security* controls (strict guardrails, a citation engine).  
**Style:** Full prose. Plain English. Depth docs are linked; this page is the decision spine.  
**Status:** Active — filed 2026-08-23 from a founder product question. **Not a freeze exception.**  
**Related:** [HOW_RAG_WORKS.md](HOW_RAG_WORKS.md) · [RETRIEVAL_AND_VECTOR_DB.md](../ce/README.md) · [ce/security/README.md](../ce/security/README.md) · [gtm/COMPETITIVE_QA.md](../../ENTERPRISE.md) (Q13 · [Q21](../../ENTERPRISE.md#q21-rerank-hyde))

This page answers four questions together:

1. What is **reranking**?
2. What are **HyDE** and **query expansion**?
3. What are **strict guardrails** here?
4. What is the **citation engine** here?

For each: what it is in everyday language, whether this repo already ships it, and how to resolve it depending on what the client actually wants.

---

## Two jobs: answer quality vs document control

Teams often bundle “make RAG better” into one shopping list. That list mixes two jobs.

**Answer quality** asks: given documents this user *may* see, did we pick the *best* few chunks and phrase the question so the model can find them? Popular tools for that job are rerankers (Cohere, Voyage, cross-encoders), HyDE, and query expansion. LangChain, LlamaIndex, and enterprise search platforms already sell them.

**Document control** asks: given this user’s identity, which documents may enter the candidate set *at all*? Then: were those chunks scanned, isolated from system instructions, grounded after generation, and audited? That is this product’s job.

A useful analogy is a library. Quality techniques help the librarian pick the *best pages from the books you are allowed to read*. Security decides *which shelves you may walk*. Mixing those jobs in one SKU confuses the buyer and dilutes the wedge: *AD / Okta groups do not map onto the vector store*.

This proxy runs **retrieve-then-generate**. The proxy searches (with ACL), sanitizes chunks, calls the chat model **once**, then checks citations. The language model does not query the store. That contract is why HyDE (an LLM call *before* search) is a poor default, and why a reranker, if it ever runs here, may only reorder **already authorized** hits.

We sit **with** LangChain or LlamaIndex. We do not replace them. Same line as [COMPETITIVE_QA Q13](../../ENTERPRISE.md).

---

## Scorecard: the four features

| # | Feature | In this product today? | Default resolution |
|---|---------|------------------------|--------------------|
| 1 | **Reranking** | **No** cross-encoder / Cohere-style rerank. Closest: **hybrid retrieval** (lexical + vector fused with reciprocal rank fusion). | Keep the reranker in *their* chain. Optional **post-ACL** rerank only if a named paid POC refuses BYO rerank. |
| 2 | **HyDE and query expansion** | **No.** Retrieval uses the user’s query as-is. The only “expand” in code is ACL **group** inheritance. | Keep in *their* chain. Not a CE/EE feature. SOW-only exception with hard caps. |
| 3 | **Strict guardrails** | **Yes — core product.** Identity → query scan → ACL retrieval → chunk scan → XML isolation → LLM → citation → output scan. | Ship and demo. Tune policy with the client; do not rebuild as “quality.” |
| 4 | **Citation engine** | **Yes — Guardrail 4.** Per-claim mapping, coverage floor, optional entailment rescue, **hard citation gate**. | Ship and demo. Tighten knobs if they need fail-closed grounding. Cross-encoder NLI is [E6.3](../../ENTERPRISE.md) (buyer-triggered). |

**One-line backlog note (do not treat as P2 spare-cycle work):**

> Post-ACL rerank: EE add-on iff a named POC refuses a BYO reranker. HyDE / query expansion: out of product; SOW-only. Not a product-freeze exception.

---

## 1. Reranking

### What it is (plain English)

After search returns a *long* list of maybe-relevant chunks, a **reranker** reads the question together with each candidate and scores “how well does this chunk actually answer the question?” It then keeps only the top few for the prompt.

First-pass search (keyword or vector neighbors) is cheap and a bit sloppy. It is good at *recall*: “don’t miss the right page.” Reranking is slower and more precise. It is good at *precision*: “of these twenty neighbors, these four should go to the model.”

Vendors sell this as a second model (often a **cross-encoder** that sees query and document together, unlike the bi-encoder used to embed the corpus). Cohere Rerank, Voyage rerank, and similar APIs are the names buyers will use.

### Why clients ask

It is a standard RAG blog-post improvement. Teams see better FAQ answers and fewer “wrong chunk in the top 4” failures. Procurement sometimes copies the list from a reference architecture.

### What this repo already does

There is **no** rerank step in `pipeline.py`. Search returns `top_k` from the store, then guardrails run.

What *is* shipped, and is easy to confuse with reranking, is **hybrid retrieval (E3.6)**. When `RAG_STORE_BACKEND=hybrid`, the proxy runs lexical SQLite search and Qdrant vector search, both with ACL, then **fuses** the two ranked lists with **reciprocal rank fusion (RRF)**. Chunks that appear on both lists rise. That improves recall/precision of *first-pass* retrieval. It is not a second model scoring query–document pairs. Depth: [E3.6 — Hybrid retrieval](../../ENTERPRISE.md). Live proof that hybrid returns an exact id lexical finds **and** a paraphrase lexical misses: [TC-E3-610](../../ENTERPRISE.md#tc-e3-610--isolated-complementary-recall-proof) (do not use `INV4419` / helpdesk against `public-faq`).

### How to resolve, depending on the client

| Client interest | What to do |
|-----------------|------------|
| They already rerank in LangChain / LlamaIndex / Cohere | **Coexist.** Prefer **split corpus**: public FAQ may use LangChain + Cohere; HR/PHI uses `POST /v1/query` only. If they need rerank on sensitive text, **in-VPC reranker** after ACL + `POST /v1/scan` (`sanitized_text` only) — not Cohere SaaS. Client diagrams: [CLIENT_ARCHITECTURE_AND_FLOWS.md § 5.3](../../ENTERPRISE.md#53-sensitive-data-and-a-third-party-reranker). If they **insist Cohere sees live query chunks**, they own retrieval; gateway is a scanner: [§ 5.4](../../ENTERPRISE.md#54-if-they-insist-cohere-sees-live-query-chunks). |
| Demo answers feel weak; they think they need a reranker | Turn on **hybrid** for the demo store. Show citation hard gate so ungrounded answers do not ship. If quality is still the complaint, they bring their reranker; you still only see **authorized** candidates. |
| They insist the reranker lives *inside* the proxy | **Paid POC exception**, not a roadmap item. **Confidential docs:** post-ACL `fetch_k` → scan/`sanitized_text` → **in-VPC or private** ranker → `top_k` → existing citation gate. Paying does **not** authorize Cohere SaaS on payroll. Client diagrams: [CLIENT_ARCHITECTURE_AND_FLOWS.md § 5.5](../../ENTERPRISE.md#55-ranking-confidential-documents). |
| They want a nDCG bake-off vs Cohere | **Don’t take it.** Same rule as injection F1 vs Lakera. Compete on engineer vs HR, payroll in or out of `chunks`. |
| They want you to become their RAG platform (rerank + HyDE + connectors + chat) | **Walk.** That is Glean / Onyx / LlamaIndex Cloud, not a retrieval-ACL gateway. |

Rerank is the *less-wrong* of the two quality features: it can sit after ACL without widening who may read what. It is still not worth building on a quiet Sunday with zero named buyers.

### Ranking confidential documents (HR / PHI / payroll) if they pay

**Paying does not make Cohere an approved processor of payroll.** User-may-read is not vendor-may-score. Full diagrams and steps (shareable): [CLIENT_ARCHITECTURE_AND_FLOWS.md § 5.5](../../ENTERPRISE.md#55-ranking-confidential-documents).

| Option | Confidential ranking | Citation gate | Ship today? |
|--------|----------------------|---------------|-------------|
| Hybrid RRF on `POST /v1/query` | Fusion of authorized lists only | Yes | **Yes** |
| [Pattern B](../../ENTERPRISE.md#53b-in-vpc-reranker): they retrieve, scan, in-VPC rank, their LLM | Cross-encoder in **their** VPC | No | Scan yes; they wire rank |
| **Paid D:** ranker called **inside** `POST /v1/query` | `fetch_k` ACL hits → scan → private ranker → `top_k` | **Yes** | **No** — named SOW |
| [§ 5.4](../../ENTERPRISE.md#54-if-they-insist-cohere-sees-live-query-chunks) Cohere SaaS on live chunks | Vendor cloud | No | They wire it; review often **no** |

**SOW shape for paid D:** ACL first; ranker sees `sanitized_text` only; in-VPC or their private URL (not a Cohere SKU); fail closed if ranker is down; no retrieve-then-trust-client-chunk-ids without re-checking ACL; same scanners and hard citation gate. Do not take a nDCG bake-off vs Cohere.

**Spoken:** *Confidential RAG can be reranked if we compress an already-authorized list inside your network. It cannot be reranked in a public rerank API just because you pay.*

**Engineering design (Paid D):** [POST_ACL_RERANK_DESIGN.md](../ce/README.md) — insertion in `pipeline.py`, `CrossEncoder` vs TEI sidecar, libraries, fail closed, tests. Not implemented until that SOW is signed.

---

## 2. HyDE and query expansion

### What they are (plain English)

**Query expansion** rewrites or pads the user’s question before search: synonyms, related phrases, extra keywords. The hope is that a vague question still hits the right document.

**HyDE** (Hypothetical Document Embeddings) is a specific expansion trick. The system asks an LLM, *before retrieval*, to *invent* a paragraph that looks like a good answer. It embeds that hypothetical paragraph and searches for real chunks near it. The invented text is a compass, not a source of truth. Real documents still have to be retrieved afterward.

Both increase **recall**: more ways to match, more of the corpus in play.

### Why clients ask

Same as reranking: they are in every “production RAG” checklist. They help when users ask with different vocabulary than the wiki.

### What this repo already does

**Nothing of this kind.** The user’s query (after input scanning) is what `store.search()` receives. There is no rewrite LLM, no synonym list, no hypothetical document.

The word “expand” appears in ACL code as **`_expand_groups`**: nested IdP groups inherit parent groups. That is permission math, not query rewrite.

### Why this is a poor default *inside* a security gateway

- **Least privilege.** Expansion pulls *more* documents into the candidate set. That fights the wedge (retrieve only what this identity may see) and fights the [extraction monitor](../ce/features/02-extraction-monitor.md) (breadth of corpus walking).
- **LLM before retrieval.** HyDE adds a model call *before* search. This product’s contract is: proxy searches, then one-shot generate. If the model drove search, ACL and DLP would be easier to bypass. See [HOW_RAG_WORKS.md](HOW_RAG_WORKS.md) and [RETRIEVAL_AND_VECTOR_DB.md](../ce/README.md).
- **Injection amplification.** A jailbreak in the user question can be rewritten into a “helpful” hypothetical that then retrieves more of the corpus.
- **Egress and cost.** Another LLM hop, latency, and another place DLP must run.

### How to resolve, depending on the client

| Client interest | What to do |
|-----------------|------------|
| Expansion / HyDE already in their chain | **Coexist.** Their retriever may rewrite; **your** hop still requires identity and ACL on whatever they (or you) actually retrieve. Prefer Pattern A so Guardrail 1 is not skipped. |
| They want better paraphrase hit-rate on *your* demo corpus | Enable **hybrid / vector** search. That is semantic match without inventing documents. |
| They insist HyDE runs inside the proxy | **SOW-only**, written exception. Sequence: scan query → one rewrite or HyDE → scan that text → **ACL** search with JWT groups → same chunk scan, isolation, generate, citation. Invented text is **not** a citation source. Cap one pass. Cannot add groups. Client diagrams: [CLIENT_ARCHITECTURE_AND_FLOWS.md § 5.6](../../ENTERPRISE.md#56-hyde-and-query-expansion). Engineering: [HYDE_QUERY_EXPANSION_DESIGN.md](../ce/README.md). |
| They want expansion to “find more documents” across ACL boundaries | **Walk.** That is the opposite of the product. |
| They treat HyDE as a must-have SKU from you | Redirect: keep LlamaIndex / LangChain for quality; buy this for control. If the deal is “replace our RAG library,” it is the wrong deal. |

Do **not** file HyDE as Community or Enterprise backlog you will pick up “when you have cycles.”

---

## 3. Strict guardrails

### What they are (plain English)

**Guardrails** here are the ordered checks that decide whether a question may run, which documents may be retrieved, whether those chunks are safe to show the model, and whether the answer may leave the building.

They are **strict** when failure **blocks** instead of warning: missing ACL metadata fails closed; poisoned chunks never reach the model; ungrounded answers are replaced with a safe fallback, not shown with a footnote. CHALLENGE mode is the middle setting: hold for an operator instead of silent allow.

This is not a content-moderation API that scores a string you already retrieved (Lakera-style). It is a **retrieval gateway**: identity is required, ACL is mandatory, then scanners, then generation, then citation, then output scan, then audit.

### What this repo already does

Shipped pipeline (see [ce/security/README.md](../ce/security/README.md)):

```text
identity → user-query scan (P1) → ACL retrieval → chunk scan → context isolation → LLM → citation → output scan
```

| Layer | Everyday meaning | Depth |
|-------|------------------|-------|
| **Guardrail 1 — ACL** | The engineer’s token cannot pull HR payroll, even if the vector neighbor list would. Filter **before** chunks exist in memory. | [GUARDRAIL_1_ACL.md](../ce/security/GUARDRAIL_1_ACL.md) · [#1](../ce/features/01-acl-pipeline.md) |
| **Guardrail 2 — DLP** | SSNs, secrets, and policy packs are redacted or blocked on query, chunks, ingest, and output. | [GUARDRAIL_2_DLP.md](../ce/security/GUARDRAIL_2_DLP.md) |
| **Guardrail 3 — Injection** | Hidden “ignore your instructions” in a wiki chunk is scanned and wrapped in un-fakeable XML so the model treats it as untrusted text, not orders. | [GUARDRAIL_3_INJECTION.md](../ce/security/GUARDRAIL_3_INJECTION.md) |
| **Guardrail 4 — Citation** | After the model writes, claims must line up with retrieved sources (see next section). | [GUARDRAIL_4_CITATION.md](../ce/security/GUARDRAIL_4_CITATION.md) |
| **P1 extras** | Query-time scan, ingest quarantine, CHALLENGE. | [P1_USER_QUERY_GUARDRAILS.md](../ce/security/P1_USER_QUERY_GUARDRAILS.md) · [#15](../ce/features/15-ingest-quarantine.md) |
| **Adjacent moats** | Extraction monitor, canaries, drift, tool gateway. | [ce/learn/01-core-moats.md](../ce/learn/01-core-moats.md) |

Honest limits (say them): injection classifiers are heuristic relative to Lakera; NER is not Presidio until [E6.1](../../ENTERPRISE.md); ACL on a **BYO** Pinecone index is the customer’s filter unless traffic goes through `POST /v1/query` ([E7.2](../../ENTERPRISE.md)).

### How to resolve, depending on the client

| Client interest | What to do |
|-----------------|------------|
| “Do you have guardrails?” as a checkbox | **Yes.** Demo engineer vs HR on the same payroll question. That *is* the product. |
| They already bought Lakera / Prompt Shields / AIRS | **Coexist.** Those screen text; we decide which documents become text. Keep both for a second opinion on *authorized* chunks. [COMPETITIVE_QA Q1 / Q16](../../ENTERPRISE.md). |
| They want stricter blocks | Raise input/output thresholds; enable CHALLENGE; turn on **hard citation gate**; keep ACL mapping **fail-closed**. Policy knobs, not new code. |
| They want vendor-grade NER / trained injection | Buyer-triggered E6 packs — [UNRESOLVED_E_BACKLOG.md](../../ENTERPRISE.md). Not spare-cycle work. |
| DIY Qdrant filter “is enough” | Agree filters are necessary; post-filter is not a control. Pre-filter + scan + quarantine + cite + audit. Deal often appears after security review bounces DIY. |

Do not re-explain guardrails as if they were missing. Point at the live pipeline.

---

## 4. Citation engine

### What it is (plain English)

After the model writes an answer, a **citation / grounding engine** checks: did this sentence come from the documents we actually put on the desk, or did the model invent it?

In consumer chat products, “citations” often mean pretty footnotes for UX. **Here they are a security gate.** If grounding fails, the user does not see the raw answer. They see a **safe fallback**, `blocked: true`, and an audit event (`citation_failed` or `citation_hard_gate_failed`).

That is closer to “the answer may not leave the building unless it is backed by retrieved context” than to “render `[1]` links.”

### What this repo already does

Module: `rag_protection_proxy/guardrails/citation.py` (`verify_citations`), after `LLMClient.chat()`, before output DLP.

In everyday terms the checker:

1. Blocks answers that sound like a **system-prompt leak** (“As an AI assistant, my core programming…”).
2. Splits the answer into sentences and asks, for each one, whether it is supported by the **sanitized chunks that went to the model** (token overlap, substring, optional **entailment rescue** with embedding cosine — [E3.5](../../ENTERPRISE.md)).
3. With **per-claim citations** on, records `citations.claims[]`: sentence, `chunk_id`, offsets, supported or not ([E3.4](../../ENTERPRISE.md)).
4. Applies a **coverage floor** (`min_citation_coverage`, default 0.15): enough sentences must be grounded.
5. With **hard citation gate** on (`output.hard_citation_gate`), any *substantive* sentence without a supporting `chunk_id` fails the whole answer — even if the rest was a perfect FAQ quote. That catches mixed answers such as real support hours plus a invented “Q3 revenue grew 40%.” Feature card: [#8](../ce/features/08-citation-hard-gate.md).

**Not shipped:** cross-encoder NLI (planned [E6.3](../../ENTERPRISE.md)), LLM-as-judge, or a footnote renderer for the customer’s chat UI. Operators see claims in Query Lab and Audit; the customer app can display `citations.claims[]` if it wants UX citations.

### How to resolve, depending on the client

| Client interest | What to do |
|-----------------|------------|
| “Do you have a citation engine?” | **Yes**, as a **fail-closed grounding gate**, not as a chat-citation widget. Demo the ungrounded mix (FAQ + invented metric) with hard gate on. |
| They want pretty footnotes in *their* UI | They map `citations.claims[]` in the client. You already return the data. Do not build a chat frontend. |
| FAQ paraphrases fail the overlap check | Enable `output.entailment_check` (E3.5). Still not an LLM judge. |
| Regulated paraphrases still fail / false-pass | Buyer-triggered **E6.3** cross-encoder NLI. Named POC only. |
| They need “every claim cited or block” | `per_claim_citations: true` + `hard_citation_gate: true`. Tune `substantive_min_tokens` so “Yes.” does not trip the gate. |
| Bedrock Guardrails “contextual grounding” | Complementary: that is a cloud quality/grounding check on text they send. Ours is bound to **the chunks this identity retrieved**. Keep both if they want; do not bake off F1. |

---

## How to resolve by client requirement (summary)

Use this table on a call. Full spoken answers: [COMPETITIVE_QA.md](../../ENTERPRISE.md) Q13 and Q21.

| They care about… | Default offer | Escalate only if… |
|------------------|---------------|-------------------|
| Rerank / HyDE / expansion as *their* RAG quality | **Keep it in LangChain / LlamaIndex / Cohere** for **FAQ**. Confidential: hybrid RRF or in-VPC; Cohere SaaS off that hop. | Named POC refuses BYO **and** needs rank **inside** `/v1/query` → post-ACL SOW ([§ 5.5](../../ENTERPRISE.md#55-ranking-confidential-documents)). HyDE in-proxy: [§ 5.6](../../ENTERPRISE.md#56-hyde-and-query-expansion) · [HYDE_QUERY_EXPANSION_DESIGN.md](../ce/README.md). |
| Strict guardrails | **Already shipped.** Demo ACL + DLP + injection + citation. Tune thresholds. | E6 packs if heuristics fail a **signed** deal. |
| Citation / hallucination control | **Already shipped.** Soft coverage + optional hard gate + per-claim API. | E6.3 if embedding entailment is not enough for that buyer. |
| “Spare cycles / P2 / second priority” | **Do not build 1–2.** Freeze: no new surfaces without 4+ qualified conversations or 1 paid engagement, unless a **named buyer** names the gap. | Same named-POC rule as above. |

**POC script when they push on 1 or 2:** keep their reranker or HyDE in the framework; `POST /v1/query` (or a retriever that calls you) is the security boundary; show engineer vs HR on one question; if answers are weak, show hybrid RRF on **authorized** hits, then citation hard gate. Quality sits beside ACL without you becoming a rerank vendor.

**Non-negotiables if quality code ever runs on the proxy path:**

1. ACL first; quality second. Never rerank or expand into unauthorized documents.
2. Reranker is a compressor on an authorized `fetch_k` list, not a new search engine.
3. Query expansion is bounded (one rewrite, scanned, no extra groups).
4. Citation still fails closed on the chunks that actually went to the model.

---

## Backlog rules (not spare-cycle P2)

This is **not** second-priority engineering for when the founder has a free evening. Pre-revenue default is **product freeze**: GTM first ([NEXT_STEPS.md](../ce/README.md) · [FOUNDER_STRATEGY_DECISIONS.md](../../ENTERPRISE.md)). “When I have cycles” is how adjacent quality work displaces outbound.

| Item | Backlog bucket | Trigger to write code |
|------|----------------|----------------------|
| Post-ACL rerank | **Buyer-triggered**, not P2 | Named POC refuses BYO rerank — [POST_ACL_RERANK_DESIGN.md](../ce/README.md) |
| HyDE / query expansion | **Out of product** / SOW exception | Named POC accepts LLM-before-retrieval in writing — [HYDE_QUERY_EXPANSION_DESIGN.md](../ce/README.md) |
| Guardrails 1–4, hard citation gate, hybrid RRF | **Shipped** | Demo, tune policy, E6 only on fidelity failure |
| Cross-encoder NLI (citation precision) | **P3 / E6.3** | Citation precision blocks a regulated POC |

If leftover engineering time exists *after* that week’s outreach, spend it on demo reliability of the **shipped** wedge (hybrid, hard gate, smoke), not a new retriever.

---

## Related documentation

| Topic | Document |
|-------|----------|
| Plain-English RAG primer | [HOW_RAG_WORKS.md](HOW_RAG_WORKS.md) |
| Who searches the store (no LLM → DB) | [RETRIEVAL_AND_VECTOR_DB.md](../ce/README.md) |
| Hybrid RRF (not a reranker) | [E3.6](../../ENTERPRISE.md) |
| Four guardrails index | [ce/security/README.md](../ce/security/README.md) |
| Citation pipeline | [GUARDRAIL_4_CITATION.md](../ce/security/GUARDRAIL_4_CITATION.md) |
| Hard gate knobs | [#8](../ce/features/08-citation-hard-gate.md) |
| Sit with LangChain | [INTEGRATIONS.md](INTEGRATIONS.md) · [E7.2](../../ENTERPRISE.md) |
| Client-facing architecture and flows | [CLIENT_ARCHITECTURE_AND_FLOWS.md](../../ENTERPRISE.md) · [§ 5.3 split / in-VPC](../../ENTERPRISE.md#53-sensitive-data-and-a-third-party-reranker) · [§ 5.5 confidential ranking](../../ENTERPRISE.md#55-ranking-confidential-documents) · [§ 5.6 HyDE / expansion](../../ENTERPRISE.md#56-hyde-and-query-expansion) · [§ 5.4 live Cohere chunks](../../ENTERPRISE.md#54-if-they-insist-cohere-sees-live-query-chunks) |
| Paid D engineering design | [POST_ACL_RERANK_DESIGN.md](../ce/README.md) |
| Paid E HyDE / expansion design | [HYDE_QUERY_EXPANSION_DESIGN.md](../ce/README.md) |
| Spoken Q&A (internal) | [gtm/COMPETITIVE_QA.md](../../ENTERPRISE.md) Q13, [Q21](../../ENTERPRISE.md#q21-rerank-hyde) |
| Pocket card | [gtm/COMPETITIVE_QA_POCKET.md](../../ENTERPRISE.md) |
| Honest positioning FAQ | [GTM_HONEST_POSITIONING.md](../../ENTERPRISE.md) |
| Product freeze / next | [NEXT_STEPS.md](../ce/README.md) · [UNRESOLVED_E_BACKLOG.md](../../ENTERPRISE.md) |
| Shipped vs gaps | [IMPLEMENTATION_STATUS.md](../ce/README.md) |

---

## Document control

| Field | Value |
|-------|-------|
| Created | 2026-08-23 |
| Type | Product + GTM decision spine (internal OK to reuse in SE talk tracks; do not send the freeze/backlog section to prospects) |
| Next review | After first named POC that asks for rerank or HyDE in-proxy, or day-90 GTM gate |
