# Community Edition — Design

| Field | Value |
|-------|-------|
| **Edition** | Community Edition (CE) |
| **Audience** | Product engineers, security reviewers |
| **Status** | Consolidated guide · July 2026 |
| **Package** | `rag-protection-proxy` |
| **Scope** | Design principles and component contracts for the CE trust surface |
| **Exclusions** | EE plugin internals, Tier 2/3 handlers, EE UI registry |

**Related:** [ARCHITECTURE.md](../../../ENTERPRISE.md) · [FUNCTIONAL_SPECIFICATION.md](FUNCTIONAL_SPECIFICATION.md) · [FEATURE_CATALOG.md](../FEATURE_CATALOG.md) · [FEATURE_CATALOG_INDEX.md](../../shared/FEATURE_CATALOG_INDEX.md) · [Package index](../../../ENTERPRISE.md)

**Deep dives:** [RAG_Protection.md](../README.md) · [guardrails/](../../ce/security/README.md) · [CE_EE_PLUGIN_SEAMS.md](../../../ENTERPRISE.md)

---

## 1. Design goals

1. **Enforce ACL before retrieval** — unauthorized documents never enter the candidate set.
2. **Keep the LLM out of the store path** — the gateway owns retrieval, sanitization, and auditing.
3. **Open the trust surface** — ACL, guardrails, and public API contracts remain inspectable in CE.
4. **Fail closed on identity and scan failures** — deny rather than silently over-permit.
5. **Stay runnable without Enterprise** — no hard dependency on EE for query, ingest, audit, or CE UI.

---

## 2. Design principles

| Principle | Implication |
|-----------|-------------|
| Pre-retrieval metadata filter | Vector/lexical search always includes group (and tenant) constraints |
| Context isolation | Retrieved text is treated as untrusted; system instructions stay outside that boundary |
| Ordered pipeline | Query scan → retrieve → chunk scan → LLM → citation → output scan |
| Thin UI over rich API | CE console: **five workspaces** (Overview, Query Lab, Documents & Ingest, Tool Gateway, Audit); Documents is ingest/list/delete only — preview/approve and Policy/Connectors are EE |
| Optional plugin | `register_enterprise()` may add routes; CE ignores `ImportError` |

---

## 3. Four-guardrail model

Requirements origin: [RAG_Protection.md](../README.md).

| Guardrail | Design intent | CE implementation notes |
|-----------|---------------|-------------------------|
| Document ACL | Map IdP/demo groups to document `allowed_groups` | SQLite + Qdrant metadata filters |
| Pattern-based DLP | Strip or redact sensitive patterns before LLM / in answers | Regex, custom patterns, secrets/URL scanners, optional heuristic NER — **not** semantic/ML DLP |
| Injection shielding | Detect imperative override patterns; isolate context | Heuristic + embedding ML assist; XML wrappers |
| Citation auditing | Require grounded answers; block prompt dumps | Overlap / per-claim checks |

**P1 input paths:** user query, retrieved chunks, and ingest content are all scanned. Mid-risk ingest can enter **CHALLENGE / quarantine** server-side in CE; CE Documents & Ingest supports ingest/list/delete and quarantine metadata. The **operator review workflow** (approve/reject/preview APIs and EE Documents overlay) is EE Tier 2 by design.

---

## 4. Identity and tenancy design

| Mode | When used |
|------|-----------|
| Demo bearer tokens | Local demos and POCs without IdP |
| HS256 JWT | Custom integrations / tests |
| OIDC / JWKS | Okta, Azure AD production pattern |

Additional CE design choices:

- Group hierarchy can expand effective access (e.g. executives inherit broader groups).
- Multi-tenant document namespaces isolate corpora at the API level.
- Operator RBAC maps static admin keys or OIDC `admin_role_map` to roles such as `policy_admin`, `ingest_admin`, `audit_reader`.
- Tenant toolbar selector uses `allowed_tenants` from `GET /admin/auth/me` (Tier 1).

---

## 5. Retrieval and store design

```text
create_document_store()
  ├── sqlite   → CE lexical store
  ├── vector   → CE Qdrant backend
  ├── hybrid   → CE RRF fusion
  └── pgvector → EE only (ImportError with install hint)
```

Design constraints:

- ACL filters are applied **before unauthorized content enters the candidate set for LLM context**: Qdrant applies the group filter **inside** the vector query; SQLite applies ACL in **application code before scoring** (not as a post-LLM prompt filter).
- Hybrid retrieval must enforce ACL on both lexical and vector legs.
- Embeddings are gateway-owned; the chat LLM does not write to or query the store.

---

## 6. Audit design

| Concern | CE design |
|---------|-----------|
| Capture | Allow / block / challenge decisions with findings |
| Buffer | In-memory ring for recent events |
| Persist | JSONL file + optional webhook retry |
| Export | NDJSON via `GET /admin/audit/export` |
| Analytics | `GET /admin/audit/stats` backs CE `AuditAnalyticsCard` |

**Note:** Older commercial matrices sometimes label “audit analytics” as EE. Runtime truth: the stats API and CE Audit Log card are **Tier 1 / CE**. EE adds retention/scrub governance and premium operator workflows elsewhere.

---

## 7. Tool gateway design

Identity-bound tool invocation prevents OWASP LLM08-style excessive agency:

1. Resolve caller groups
2. Lookup tool in registry; scan poisoned descriptions
3. Enforce `allowed_groups` and argument schemas
4. Size / pattern / domain checks
5. Input guardrail scan on arguments
6. Invoke mock or MCP shim backend
7. Record `kind: tool_invoke` audit

Base `GET /v1/tools` and `POST /v1/tools/invoke` remain CE. Tool **registry CRUD** and related premium UI overlay are EE (entitlement `tool_registry`).

---

## 8. Console design

| Decision | Rationale |
|----------|-----------|
| Single React shell | One app; edition differs by registered workspaces |
| Build-time CE/EE split | CE never compiles EE pane source |
| Five CE workspaces | Overview, Query Lab, Documents & Ingest (ingest/list/delete), Tool Gateway, Audit Log |
| Silent CE fallback | Missing EE package or `ee-ui.js` → stay CE-only |
| `?ee=off` debug toggle | Force CE-only view even when EE is installed |

---

## 9. Extension points (CE-safe)

| Extension | Mechanism |
|-----------|-----------|
| BYO RAG scan | `POST /v1/scan` |
| Policy tuning | Edit `policy.yaml` / `acl_policy.yaml` + `POST /admin/reload-policy` |
| Tool policy | `tool_policy.yaml` (+ MCP overlay file when Layer 2 enabled) |
| Frameworks | LangChain / Pinecone patterns A/B/C via HTTP — see [INTEGRATIONS.md](../../product/INTEGRATIONS.md) |
| Enterprise add-on | Optional `register_enterprise(app, deps=…)` |

---

## 10. Non-goals and EE upsell (labeled)

CE deliberately does **not** design for:

| Non-goal | EE direction |
|----------|--------------|
| Polished quarantine review UX (preview/approve) | EE Documents & Ingest CHALLENGE queue + inspect |
| Live source connectors | Drive OAuth, scheduler, SCIM admin |
| Postgres-native vector | `pgvector_store` |
| Policy form authoring / Pattern Lab | Tier 2 policy routes + Policy pane |
| Compliance evidence bundles | `evidence_pack` entitlement |
| Multi-replica HA | Planned EE operations work |

These are described in [Enterprise Design](../../../ENTERPRISE.md).

---

## 11. Testability

| Layer | What it proves |
|-------|----------------|
| `test_ce_ee_seams.py` | Tier 2/3 absent (404); health without enterprise |
| `tools/smoke_rag_proxy.sh` | ACL wedge + FAQ path on CE stack |
| Guardrail pytest / TC-GR-* | Four-guardrail regressions |
| Console Vitest (`console/packages/**`) | CE panes |

---

## Engineering reference

| Topic | Source |
|-------|--------|
| PRD | [RAG_Protection.md](../README.md) |
| Feature catalog | [MASTER_FEATURES_CATALOG.md](../README.md) |
| Detection overview | [DETECTION_OVERVIEW.md](../../ce/security/DETECTION_OVERVIEW.md) |
| Seam contracts | [CE_EE_PLUGIN_SEAMS.md](../../../ENTERPRISE.md) |
| Tech stack | [TECH_STACK.md](../../product/TECH_STACK.md) |

---

## 12. Four-guardrail design — CE fidelity limits

CE implements the full **four-guardrail pipeline** with **community-fidelity** detectors. This is intentional: the trust **architecture** (order, fail-closed gates, audit hooks) is production-grade; individual scanners trade vendor-ML depth for inspectability and offline operation.

Catalog: [FEATURE_CATALOG.md #1](../FEATURE_CATALOG.md#1-document-level-acl--4-guardrail-pipeline).

| Guardrail | CE design contract | Fidelity limit (honest non-claim) | Primary modules |
|-----------|-------------------|-----------------------------------|-----------------|
| Document ACL | Unauthorized docs never enter candidate set | Group metadata must be correct at ingest; no ReBAC/external authz | `acl.py`, `store.py`, `vector_store.py` |
| Pattern-based DLP | Scan query, chunks, ingest, output | **Regex + custom patterns + secrets/URL + optional heuristic NER** — not semantic/embedding DLP or curated compliance packs | `scanners/*`, `guardrails/*_pipeline.py` |
| Injection shielding | Block override patterns; isolate context | Heuristic rules + optional local ML assist; not adaptive red-team arms race | `prompt_injection.py`, `injection_ml.py`, `context_builder.py` |
| Citation auditing | Ground answers; block prompt dumps | Lexical overlap + per-claim map; optional hash embedder entailment — not full NLI service | `guardrails/citation.py` |

**Challenge mode interaction:** `policy.input.challenge_mode` and ingest risk scoring can emit `Decision.CHALLENGE` without blocking low-risk paths. CE persists quarantined ingest server-side; human approve/preview remains EE.

**Orthogonal controls (same pipeline, separate catalog entries):** extraction monitor (#2), canary (#3), retrieval trace (#11), LLM routing (#18) — hooked from `pipeline.py` after ACL-filtered retrieval.

**Four-layer LLM-firewall sketch (normalize → YAML signatures → local classifier → isolation):** how this CE pipeline maps, what stays in code on purpose, and what is not a next-release gap — [PIPELINE_LAYERS_AND_THREAT_MAINTENANCE.md](../security/PIPELINE_LAYERS_AND_THREAT_MAINTENANCE.md).

---

## 13. Store factory design

Single entry point: `create_document_store(data_dir, tenant_id)` in `store.py`. Selected by `RAG_STORE_BACKEND`.

```text
create_document_store(data_dir, tenant_id="default")
  ├── sqlite (default)
  │     DocumentStore(data_dir / "documents.db")
  │     ACL: user_can_access_document() before scoring each chunk
  ├── vector
  │     VectorDocumentStore → Qdrant
  │     ACL: build_acl_filter(user_groups) applied inside client.search()
  ├── hybrid
  │     HybridDocumentStore(lexical, vector)
  │     RRF fusion; each leg already ACL-filtered
  └── pgvector
        try: rag_protection_enterprise.store_backends.create_pgvector_store
        except ImportError → actionable message to install EE wheel
```

| Backend | ACL enforcement point | Quarantine exclusion |
|---------|----------------------|----------------------|
| SQLite | Application loop in `DocumentStore.search()` — skip if `!user_can_access_document` or `_is_quarantined` | Same loop |
| Qdrant | `Filter(must_not status=quarantined, should allowed_groups∈caller∪{public,all-staff})` in vector query | Payload index on `status` |
| Hybrid | Both legs independently filtered, then `_fuse_chunks()` | Inherited from legs |
| pgvector | EE backend (not CE) | EE |

Embeddings are gateway-owned (`embeddings.py`); the chat LLM never reads or writes the document store directly.

Multi-tenant: `tenant_store.py` calls `create_document_store` per tenant subdirectory with optional collection suffix for Qdrant.

---

## 14. Audit integrity chain design

When `policy.audit.integrity_chain: true`, persisted JSONL events include tamper-evident linkage (`audit_integrity.py`).

| Element | Behavior |
|---------|----------|
| Genesis | `GENESIS_HASH` constant seeds the chain |
| Per event | `prev_hash` + `event_hash = SHA256(prev_hash + canonical_json(body))` |
| Chain tip | In-memory `_last_hash`; sidecar `{audit_file}.chain` on persist |
| Verify | Replay file or `GET /admin/audit/integrity/verify` |
| Disable | `configure_integrity_chain(enabled=False)` — fields omitted |

Design choice: integrity is **append-only chain over audit exports**, not a full WORM store. CE provides verification tooling; EE adds retention/scrub governance elsewhere.

Catalog: [FEATURE_CATALOG.md #9](../FEATURE_CATALOG.md#9-tamper-evident-audit-log).

---

## 15. Extraction monitor — design hooks

Cross-query behavioral control (#2). ACL and per-query DLP cannot detect an authorized user slowly walking the entire corpus.

| Hook | Location | Trigger |
|------|----------|---------|
| Observe | `pipeline.run_query()` after retrieval | `policy.extraction.enabled` |
| State | In-process `(tenant_id, subject)` sliding window | `guardrails/extraction.py` |
| Score | Coverage, breadth, novelty ratios vs thresholds | `ExtractionPolicy` in `policy.yaml` |
| Act | `severity=severe` + action `challenge`/`throttle` → block response | `block_reason=extraction_suspected` |
| Audit | `kind=extraction_suspected` | Always on elevated/severe |

No new datastore in CE MVP — window mirrors audit ring semantics (single-process; resets on restart).

Catalog: [FEATURE_CATALOG.md #2](../FEATURE_CATALOG.md#2-corpus-extraction-monitor-lab-9).

---

## 16. Canary / honeypot — design hooks

#3 tripwire documents tagged with `metadata.canary=true`, default group `__canary__` (unreachable under correct ACL).

| Hook | Location | Behavior |
|------|----------|----------|
| Seed | `seed_canary(store, …)` | Admin/CLI; delete refused (409) |
| Retrieval trap | `inspect_candidates()` in `run_query()` | Non-auditor retrieval → `canary_triggered` audit, chunks stripped |
| Output backstop | `find_canary_token_in_text()` | Optional answer-path detection |
| Auditors | `policy.canary.auditor_subjects` / `auditor_groups` | May retrieve without alarm (testing) |

A canary hit is treated as **P1 enforcement failure signal**, not a user-facing document.

Catalog: [FEATURE_CATALOG.md #3](../FEATURE_CATALOG.md#3-canary--honeypot-documents-lab-10).

---

## 17. Extension points (expanded)

| Extension | Mechanism | CE-safe? | Catalog / doc |
|-----------|-----------|----------|---------------|
| BYO RAG scan | `POST /v1/scan` | Yes | #1 |
| Policy tuning | Edit active `policy.yaml` + `POST /admin/reload-policy` | Yes | #1 |
| ACL / demo users | `acl_policy.yaml` + reload | Yes | #1 |
| Tool policy | `tool_policy.yaml`, MCP overlay | Yes | #7 |
| Store backend | `RAG_STORE_BACKEND=sqlite\|vector\|hybrid` | Yes | ARCHITECTURE §13 |
| Extraction / canary knobs | `extraction:` / `canary:` in policy | Yes | #2, #3 |
| Retrieval explainability | `retrieval.explainability_enabled`, `include_retrieval_trace` | Yes | #11 |
| LLM routing table | `llm_routing:` in policy | Yes | #18 |
| Audit integrity | `audit.integrity_chain: true` | Yes | #9 |
| Framework integration | HTTP client patterns A/B/C | Yes | [INTEGRATIONS.md](../../product/INTEGRATIONS.md) |
| Enterprise add-on | `register_enterprise(app, deps=…)` | Optional | [CE_EE_PLUGIN_SEAMS.md](../../../ENTERPRISE.md) |
| CLI shift-left | `tools/acl_backfill`, `tools/inj_bench`, etc. | Yes | #6, #10, #19–#20, #23, #27, #29 |
| EE registry CRUD | Tier 2 routes + `ee-ui.js` | No (404 on CE) | EE #13 |

---

## 18. Testability matrix (expanded)

| Layer | Test / command | Proves | Catalog |
|-------|----------------|--------|---------|
| CE/EE seams | `pytest tests/test_ce_ee_seams.py` | Tier 2/3 → 404; pgvector ImportError hint | Moat |
| Store factory | `tests/test_store_factory.py` | sqlite/vector/hybrid selection | #1 |
| ACL wedge smoke | `tools/smoke_rag_proxy.sh` | Engineer vs HR retrieval | #1 |
| Guardrails P1 | `tests/test_p1.py`, TC-GR-* | Four-guardrail regressions | #1, #23 |
| Extraction | `tests/test_extraction.py` | Scrape detection + block | #2 |
| Canary | `tests/test_canary.py` | Tripwire + filter | #3 |
| Citation hard gate | `tests/test_rag_protection.py`, `tools/rag_ground/` | Ungrounded block | #8, #19 |
| Audit integrity | `tests/test_audit_integrity.py` | Chain + verify endpoint | #9 |
| LLM routing | `tests/test_llm_routing.py` | Classification → endpoint | #18 |
| Retrieval trace | `tests/test_retrieval_trace.py` · console Vitest | Trace outcomes | #11 |
| Tool gateway | tool invoke tests + MCP demo | Allowlist + audit | #7 |
| Ingest quarantine | ingest API tests | CHALLENGE metadata, CE list/delete | #15 |
| Console CE | `console/packages/ce/**/*.test.tsx` | Four workspaces render | #1 |
| Red team harness | `tools/redteam/` | Packaged scenarios | #10 |
| ACL backfill CLI | `tools/acl_backfill/` | Vector metadata repair | #29 |
| MCP linter CLI | `tools/mcp-lint` | Manifest hygiene | #27 |

---

## 19. CE console design note — Tool Gateway UI

Four workspaces at CE build (`console/packages/ce/src/main.tsx`): `overview`, `query`, `tools`, `audit`.

**Tool Gateway pane** is intentionally **policy- and queue-oriented**:

- Loads `GET /admin/tools/policy` (YAML-derived registry view)
- Shows group allowlists, description blocks, CHALLENGE queue rows when `challenge_mode: allow`
- Links operators to `tool_invoke` events in Audit Log
- Documents invoke path: `POST /v1/tools/invoke` or `examples/agentic/mcp_tool_gateway/demo_agent.py`

There is **no CE “invoke tool” form** — invocation is an integrator/agent API concern. EE adds registry CRUD overlay when `tool_registry` entitlement and `ee-ui.js` are present.

Catalog: [FEATURE_CATALOG.md #7](../FEATURE_CATALOG.md#7-agent--mcp-tool-gateway-acl-lab-1-ce).
