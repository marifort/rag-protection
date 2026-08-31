# Community Edition — Functional Specification

| Field | Value |
|-------|-------|
| **Edition** | Community Edition (CE) |
| **Audience** | Product managers, QA, security reviewers, implementers |
| **Status** | Consolidated guide · July 2026 |
| **Package** | `rag-protection-proxy` |
| **Scope** | Functional requirements for the CE trust surface and CE console |
| **Exclusions** | Tier 2/3 APIs, EE workspaces, entitlement-gated packs |

**Related:** [ARCHITECTURE.md](../../../ENTERPRISE.md) · [DESIGN.md](DESIGN.md) · [FEATURE_CATALOG.md](../FEATURE_CATALOG.md) · [FEATURE_CATALOG_INDEX.md](../../shared/FEATURE_CATALOG_INDEX.md) · [ADMIN_GUIDE.md](ADMIN_GUIDE.md) · [Package index](../../../ENTERPRISE.md)

**Deep dives:** [RAG_Protection.md](../README.md) · [CE_EE_MOAT_AND_ENDPOINT_TIERING.md](../../../ENTERPRISE.md) · [CAPABILITY_READINESS.md](../../../ENTERPRISE.md)

---

## 1. Status vocabulary

| Status | Meaning in this spec |
|--------|----------------------|
| **Shipped** | Available in current CE release; covered by tests/runbooks |
| **Partial** | Usable core with documented gaps |
| **Out of scope (EE)** | Requires Enterprise package — not a CE FR |

---

## 2. Actors

| Actor | Description |
|-------|-------------|
| End user | Calls `/v1/query` or `/v1/tools/*` with a user bearer |
| Operator / admin | Uses `/ui` and admin APIs with admin bearer / OIDC admin roles |
| Integration client | Calls `/v1/scan` or `/v1/ingest` from pipelines |
| Evaluator | Runs demos with demo tokens; no live IdP required |

---

## 3. Functional requirements

### FR-1 Document-level ACL (Shipped) · [Catalog #1](../FEATURE_CATALOG.md#1-document-level-acl--4-guardrail-pipeline)

| ID | Requirement | Acceptance |
|----|-------------|------------|
| FR-1.1 | System shall filter retrieval by caller groups before returning chunks | Engineer demo token cannot retrieve `hr-payroll` |
| FR-1.2 | Authorized groups shall retrieve matching documents | HR demo token retrieves payroll doc |
| FR-1.3 | `GET /v1/documents` shall respect the same ACL | Document list differs by token |
| FR-1.4 | Multi-tenant namespaces shall isolate corpora when configured | Cross-tenant retrieval denied |

### FR-2 Pattern-based DLP (Shipped — community scanners) · [Catalog #1](../FEATURE_CATALOG.md#1-document-level-acl--4-guardrail-pipeline)

| ID | Requirement | Acceptance |
|----|-------------|------------|
| FR-2.1 | System shall scan query, chunks, ingest, and output for PII/secrets/URLs | Findings appear in audit / redaction behavior |
| FR-2.2 | Authorized retrieval shall still apply DLP before LLM context | Payroll/PII patterns redacted or labeled per policy |
| FR-2.3 | CE DLP shall use regex, custom patterns, and optional heuristic NER — **not** marketed as semantic/ML DLP | Scanner modules under `scanners/`; no embedding-classifier DLP claim |

### FR-3 Injection shielding (Shipped) · [Catalog #1](../FEATURE_CATALOG.md#1-document-level-acl--4-guardrail-pipeline) · [Catalog #23](../FEATURE_CATALOG.md#23-prompt-injection-benchmark-a7)

| ID | Requirement | Acceptance |
|----|-------------|------------|
| FR-3.1 | User queries with jailbreak/injection patterns shall be blocked before retrieval | No LLM call; block audit event |
| FR-3.2 | Retrieved / ingested content shall be scanned for injection | Chunks blocked or quarantined per policy |
| FR-3.3 | Prompt construction shall isolate untrusted retrieved context | System instructions not executable from corpus |

### FR-4 Citation auditing (Shipped) · [Catalog #8](../FEATURE_CATALOG.md#8-per-claim-citation-hard-gate) · [Catalog #19](../FEATURE_CATALOG.md#19-grounding--hallucination-checker)

| ID | Requirement | Acceptance |
|----|-------------|------------|
| FR-4.1 | Ungrounded answers shall be blocked or replaced with safe fallback | `citation_verification_failed` or equivalent |
| FR-4.2 | System-prompt dump patterns shall be blocked | Output scan / citation path |

### FR-5 Ingest and quarantine semantics (Shipped — API) · [Catalog #15](../FEATURE_CATALOG.md#15-ingest-time-quarantine-ce-lifecycle)

| ID | Requirement | Acceptance |
|----|-------------|------------|
| FR-5.1 | `POST /v1/ingest` shall scan content and may quarantine mid-risk docs | Document not searchable while quarantined |
| FR-5.2 | CE shall **not** require EE for ingest itself | Ingest works on CE-only image |
| FR-5.3 | Approve/reject/preview/inspect APIs are **out of scope** for CE | Those routes return **404** without EE |
| FR-5.4 | Operators shall see quarantined docs, **metadata only** | `GET /v1/documents/quarantined` returns id/title/reason/risk — no content |
| FR-5.5 | Operators shall delete documents (incl. quarantined) | `DELETE /v1/documents/{id}` removes doc; `document_deleted` audit event; canaries refused (409) |
| FR-5.6 | Re-ingest of remediated content under the same id shall replace and rescan | Clean re-ingest → doc active immediately |

CE lifecycle for a held doc: **list → delete → re-ingest remediated**. Approve-in-place and content preview/inspect remain EE (FR-5.3).

### FR-6 Audit and export (Shipped) · [Catalog #9](../FEATURE_CATALOG.md#9-tamper-evident-audit-log)

| ID | Requirement | Acceptance |
|----|-------------|------------|
| FR-6.1 | Allow/block/challenge decisions shall be recorded | Events via `/admin/audit/events` or `/audit/recent` |
| FR-6.2 | Operators shall export NDJSON | `/admin/audit/export` |
| FR-6.3 | Operators shall view aggregate stats in CE Audit Log | `/admin/audit/stats` |

### FR-7 Tool gateway (Shipped) · [Catalog #7](../FEATURE_CATALOG.md#7-agent--mcp-tool-gateway-acl-lab-1-ce)

| ID | Requirement | Acceptance |
|----|-------------|------------|
| FR-7.1 | Callers shall only invoke tools allowed for their groups | Unauthorized → 403 |
| FR-7.2 | Tool args shall pass schema and guardrail checks | Malformed/injected args blocked |
| FR-7.3 | Tool decisions shall be audited | `kind: tool_invoke` |
| FR-7.4 | CE Tool Gateway UI shall expose policy registry and queue — **not** a first-class invoke form | Pane loads `/admin/tools/policy`; invoke documented as API-only |

### FR-8 Operator console — CE workspaces (Shipped) · [Catalog #1](../FEATURE_CATALOG.md#1-document-level-acl--4-guardrail-pipeline)

| ID | Requirement | Acceptance |
|----|-------------|------------|
| FR-8.1 | `/ui` shall serve the React CE shell | Build tag `ce-v1` |
| FR-8.2 | Sidebar shall include **exactly five** workspaces: Overview, Query Lab, Documents & Ingest, Tool Gateway, Audit Log | No Connectors or Policy panes on CE-only; Documents is ingest/list/delete only (no preview/approve) |
| FR-8.3 | CE-only install shall not show Documents, Connectors, or Policy panes | No EE bundle / probe fails closed to CE |

### FR-9 Identity modes (Shipped) · [Catalog #1](../FEATURE_CATALOG.md#1-document-level-acl--4-guardrail-pipeline)

| ID | Requirement | Acceptance |
|----|-------------|------------|
| FR-9.1 | Demo tokens shall authenticate without external IdP | Default ACL demo path |
| FR-9.2 | OIDC/JWKS shall map groups to ACL when configured | OIDC validation runbook |
| FR-9.3 | Admin roles shall gate admin APIs | Wrong key → 401/403; CE Tier 2 still 404 |

### FR-10 Configuration and reload (Shipped) · [Catalog #1](../FEATURE_CATALOG.md#1-document-level-acl--4-guardrail-pipeline)

| ID | Requirement | Acceptance |
|----|-------------|------------|
| FR-10.1 | `policy.yaml` and `acl_policy.yaml` shall hot-reload via `POST /admin/reload-policy` | New values take effect without full redeploy |
| FR-10.2 | Store backend and audit env vars shall require process restart | Documented in admin guide |

### FR-11 Corpus extraction monitor (Shipped) · [Catalog #2](../FEATURE_CATALOG.md#2-corpus-extraction-monitor-lab-9)

| ID | Requirement | Acceptance |
|----|-------------|------------|
| FR-11.1 | System shall track per-subject retrieval breadth in a sliding window when `extraction.enabled` | `observe_query()` updates in-process state |
| FR-11.2 | Severe scrape scores shall block or challenge per policy action | `block_reason=extraction_suspected`; no LLM on block |
| FR-11.3 | Extraction events shall be auditable | `kind=extraction_suspected` in audit export |

### FR-12 Canary / honeypot documents (Shipped) · [Catalog #3](../FEATURE_CATALOG.md#3-canary--honeypot-documents-lab-10)

| ID | Requirement | Acceptance |
|----|-------------|------------|
| FR-12.1 | Canary docs shall use reserved metadata/group defaults (`__canary__`) | Seeded canaries not in normal group retrieval |
| FR-12.2 | Non-auditor retrieval of a canary shall alarm and strip content | `kind=canary_triggered`; chunks filtered from response |
| FR-12.3 | Canary delete shall be refused | `DELETE /v1/documents/{canary_id}` → **409** |

### FR-13 Per-claim citation hard gate (Shipped) · [Catalog #8](../FEATURE_CATALOG.md#8-per-claim-citation-hard-gate)

| ID | Requirement | Acceptance |
|----|-------------|------------|
| FR-13.1 | Answers with unsupported claims beyond threshold shall fail verification | `citation.hard_gate_failed=true` in audit detail |
| FR-13.2 | Failed citation shall return safe fallback, not raw ungrounded text | `SAFE_FALLBACK` answer path in `pipeline.py` |
| FR-13.3 | System-prompt leak patterns shall fail citation path when enabled | `system_prompt_leak=true` in `CitationCheck` |

### FR-14 Tamper-evident audit integrity (Shipped) · [Catalog #9](../FEATURE_CATALOG.md#9-tamper-evident-audit-log)

| ID | Requirement | Acceptance |
|----|-------------|------------|
| FR-14.1 | When `audit.integrity_chain: true`, persisted events shall include hash chain fields | `prev_hash`, `event_hash` on JSONL lines |
| FR-14.2 | Operators shall verify chain integrity | `GET /admin/audit/integrity/verify` returns valid/invalid |
| FR-14.3 | Tampered or truncated files shall fail verification | `tests/test_audit_integrity.py` |

### FR-15 Retrieval explainability trace (Shipped) · [Catalog #11](../FEATURE_CATALOG.md#11-retrieval-decision-explainability-trace)

| ID | Requirement | Acceptance |
|----|-------------|------------|
| FR-15.1 | Retrieval shall explain per-chunk outcomes when enabled | `outcome` ∈ `selected`, `excluded_acl`, `excluded_quarantine`, `excluded_low_score`, `not_in_top_k` |
| FR-15.2 | Query may request trace via `include_retrieval_trace` | `QueryResponse.retrieval_trace` populated |
| FR-15.3 | Policy may persist traces to audit when `retrieval.explainability_enabled` | `kind=retrieval_trace` events |

### FR-16 LLM egress routing (Shipped) · [Catalog #18](../FEATURE_CATALOG.md#18-llm-egress-routing-by-classification)

| ID | Requirement | Acceptance |
|----|-------------|------------|
| FR-16.1 | System shall select LLM endpoint from chunk classification table when routing enabled | `resolve_llm_route()` picks `endpoint_id` |
| FR-16.2 | Unmapped sensitive classification shall fail closed when configured | `llm_routing_unmapped_classification` block |
| FR-16.3 | Routing decisions shall be auditable | `kind=llm_routed` with endpoint host/model detail |

### FR-17 CLI and shift-left tools (Shipped — `FR-tool-*`)

| ID | Requirement | Acceptance | Catalog |
|----|-------------|------------|---------|
| FR-tool-1 | ACL backfill CLI shall repair vector payload ACL metadata | `tools/acl_backfill/` exit 0 on sample | [#29](../FEATURE_CATALOG.md#29-vector-acl-backfill-a4) |
| FR-tool-2 | CI ACL scanner shall fail builds on ACL regressions | #6 wire-up in CI | [#6](../FEATURE_CATALOG.md#6-ci-shift-left-acl-scanner-lab-2) |
| FR-tool-3 | Red-team harness shall run packaged attack scenarios | `tools/redteam/` | [#10](../FEATURE_CATALOG.md#10-packaged-red-team-harness-lab-5) |
| FR-tool-4 | Grounding checker CLI shall score answer vs sources | `tools/rag_ground/` exit codes | [#19](../FEATURE_CATALOG.md#19-grounding--hallucination-checker) |
| FR-tool-5 | Posture scorecard CLI shall emit RAG security score | `tools/rag_score/` | [#20](../FEATURE_CATALOG.md#20-rag-posture-scorecard) |
| FR-tool-6 | Injection benchmark CLI shall run corpus benchmarks | `tools/inj_bench/` | [#23](../FEATURE_CATALOG.md#23-prompt-injection-benchmark-a7) |
| FR-tool-7 | MCP manifest linter shall validate tool manifests | MCP lint tool in repo | [#27](../FEATURE_CATALOG.md#27-mcp-manifest-linter) |

---

## 3a. Functional requirements matrix (summary)

| FR | Theme | Status | Catalog |
|----|-------|--------|---------|
| FR-1 | Document ACL | Shipped | [#1](../FEATURE_CATALOG.md#1-document-level-acl--4-guardrail-pipeline) |
| FR-2 | Pattern-based DLP | Shipped | [#1](../FEATURE_CATALOG.md#1-document-level-acl--4-guardrail-pipeline) |
| FR-3 | Injection shielding | Shipped | [#1](../FEATURE_CATALOG.md#1-document-level-acl--4-guardrail-pipeline), [#23](../FEATURE_CATALOG.md#23-prompt-injection-benchmark-a7) |
| FR-4 | Citation auditing | Shipped | [#8](../FEATURE_CATALOG.md#8-per-claim-citation-hard-gate), [#19](../FEATURE_CATALOG.md#19-grounding--hallucination-checker) |
| FR-5 | Ingest / quarantine CE lifecycle | Shipped (API) | [#15](../FEATURE_CATALOG.md#15-ingest-time-quarantine-ce-lifecycle) |
| FR-6 | Audit + export | Shipped | [#9](../FEATURE_CATALOG.md#9-tamper-evident-audit-log) |
| FR-7 | Tool gateway | Shipped | [#7](../FEATURE_CATALOG.md#7-agent--mcp-tool-gateway-acl-lab-1-ce) |
| FR-8 | CE console (five workspaces) | Shipped | [#1](../FEATURE_CATALOG.md#1-document-level-acl--4-guardrail-pipeline) |
| FR-9 | Identity modes | Shipped | [#1](../FEATURE_CATALOG.md#1-document-level-acl--4-guardrail-pipeline) |
| FR-10 | Config reload | Shipped | [#1](../FEATURE_CATALOG.md#1-document-level-acl--4-guardrail-pipeline) |
| FR-11 | Extraction monitor | Shipped | [#2](../FEATURE_CATALOG.md#2-corpus-extraction-monitor-lab-9) |
| FR-12 | Canary documents | Shipped | [#3](../FEATURE_CATALOG.md#3-canary--honeypot-documents-lab-10) |
| FR-13 | Citation hard gate | Shipped | [#8](../FEATURE_CATALOG.md#8-per-claim-citation-hard-gate) |
| FR-14 | Audit integrity | Shipped | [#9](../FEATURE_CATALOG.md#9-tamper-evident-audit-log) |
| FR-15 | Retrieval trace | Shipped | [#11](../FEATURE_CATALOG.md#11-retrieval-decision-explainability-trace) |
| FR-16 | LLM routing | Shipped | [#18](../FEATURE_CATALOG.md#18-llm-egress-routing-by-classification) |
| FR-tool-* | CLI shift-left tools | Shipped | [#6](../FEATURE_CATALOG.md#6-ci-shift-left-acl-scanner-lab-2), [#10](../FEATURE_CATALOG.md#10-packaged-red-team-harness-lab-5), [#19–#20](../FEATURE_CATALOG.md#19-grounding--hallucination-checker), [#23](../FEATURE_CATALOG.md#23-prompt-injection-benchmark-a7), [#27](../FEATURE_CATALOG.md#27-mcp-manifest-linter), [#29](../FEATURE_CATALOG.md#29-vector-acl-backfill-a4) |

## 4. API contracts (Tier 1 only)

Canonical list: [CE_EE_MOAT § Tier 1](../../../ENTERPRISE.md#tier-1--must-stay-open-trust-surface--ce-console-runtime-deps).

| Method | Path | Auth |
|--------|------|------|
| POST | `/v1/query` | User bearer |
| POST | `/v1/ingest` | Admin (`ingest_admin` or equivalent) |
| POST | `/v1/scan` | Admin |
| GET | `/v1/documents`, `/v1/documents/count` | User bearer |
| GET | `/v1/documents/quarantined` | Admin (`ingest_admin`) |
| DELETE | `/v1/documents/{document_id}` | Admin (`ingest_admin`) |
| GET | `/v1/auth/me` | User bearer |
| GET | `/admin/auth/me` | Admin bearer |
| GET | `/v1/tools` | User bearer |
| POST | `/v1/tools/invoke` | User bearer |
| GET | `/admin/overview/stats` | Admin |
| GET | `/admin/audit/events` | Admin |
| GET | `/admin/audit/export` | Admin |
| GET | `/admin/audit/stats` | Admin |
| GET | `/audit/recent` | User bearer |
| POST | `/admin/reload-policy` | Admin |
| GET | `/health`, `/metrics` | None / infra |
| GET | `/ui` | None |

---

## 5. Configuration surfaces

| Surface | Examples | Reload |
|---------|----------|--------|
| `config/policy.yaml` | input/output/DLP/network/LLM — **shipped default** | Hot via reload-policy |
| `data/policy.yaml` | Writable runtime copy when `config/` is read-only | Hot via reload-policy |
| `config/acl_policy.yaml` | demo users, OIDC maps | Hot via reload-policy |
| `config/tool_policy.yaml` | tool allowlists / backends | Hot via reload-policy |
| `.env` / `RAG_*` | admin key, store backend, audit paths, `RAG_POLICY_FILE`, `RAG_DATA_DIR` | Restart |

---

## 6. Console functional matrix

| Workspace | Operator can… |
|-----------|---------------|
| Overview | View health/stats summary |
| Query Lab | Run secured queries; inspect verdicts, chunks, optional audit debug |
| Tool Gateway | View tool policy registry, group allowlists, and CHALLENGE queue; jump to audit — **invoke via API** (`POST /v1/tools/invoke`) or demo scripts, not a CE invoke form |
| Audit Log | Browse events, export NDJSON, view analytics charts |

---

## 7. Failure behavior

| Condition | Expected |
|-----------|----------|
| Missing/invalid user token | 401 |
| Insufficient groups for tool/doc | 403 or empty retrieval set |
| Query injection block | No LLM; block audit |
| All chunks blocked | No LLM |
| LLM unavailable | Connectivity fallback; may fail citation |
| Tier 2/3 path on CE-only | **404** |
| `RAG_STORE_BACKEND=pgvector` without EE | `ImportError` with install hint |

---

## 8. Non-functional constraints

| Concern | CE expectation |
|---------|----------------|
| Latency | Local POC-grade; not multi-replica HA |
| Deploy | Docker Compose / single-replica Helm |
| Observability | `/health`, Prometheus `/metrics`, audit JSONL |
| Licensing | MIT terms apply at public CE launch; repo may be private today |
| Support | Community — no contractual SLA |

---

## 9. Out of scope (Enterprise)

| Capability | Notes |
|------------|-------|
| CHALLENGE queue APIs/UI | Tier 2 |
| Policy-config, knobs, backups, pattern preview | Tier 2 |
| `GET /admin/tenants` | Tier 2 |
| Connectors, SCIM sync admin | Tier 3 |
| Rate limits, pgvector | Tier 3 |
| Evidence pack / curated packs / digest | Entitlements |
| Documents, Connectors, Policy panes | EE UI |

Parallel spec: [Enterprise Functional Specification](../../../ENTERPRISE.md).

---

## 10. Acceptance evidence

Per-feature validation commands and tutorials: [FEATURE_CATALOG.md](../FEATURE_CATALOG.md) · index: [FEATURE_CATALOG_INDEX.md](../../shared/FEATURE_CATALOG_INDEX.md).

| Evidence | Source | FR / Catalog |
|----------|--------|--------------|
| CE-only seams | `pytest rag-protection-proxy/tests/test_ce_ee_seams.py` | FR-8, FR-9 · Moat |
| Smoke ACL wedge | `bash tools/docker_start.sh --smoke` · `tools/smoke_rag_proxy.sh` | FR-1 · [#1](../FEATURE_CATALOG.md#1-document-level-acl--4-guardrail-pipeline) |
| Guardrail manual cases | [GUARDRAIL_TEST_PLAN.md](../../../ENTERPRISE.md) | FR-1–4 · [#1](../FEATURE_CATALOG.md#1-document-level-acl--4-guardrail-pipeline) |
| Extraction monitor | `pytest rag-protection-proxy/tests/test_extraction.py` | FR-11 · [#2](../FEATURE_CATALOG.md#2-corpus-extraction-monitor-lab-9) |
| Canary tripwire | `pytest rag-protection-proxy/tests/test_canary.py` | FR-12 · [#3](../FEATURE_CATALOG.md#3-canary--honeypot-documents-lab-10) |
| Citation / hard gate | `pytest rag-protection-proxy/tests/test_rag_protection.py` · `tools/rag_ground/` | FR-4, FR-13 · [#8](../FEATURE_CATALOG.md#8-per-claim-citation-hard-gate), [#19](../FEATURE_CATALOG.md#19-grounding--hallucination-checker) |
| Audit integrity chain | `pytest rag-protection-proxy/tests/test_audit_integrity.py` · `GET /admin/audit/integrity/verify` | FR-14 · [#9](../FEATURE_CATALOG.md#9-tamper-evident-audit-log) |
| Retrieval trace | `pytest rag-protection-proxy/tests/test_e3.py` · Query Lab / Vitest | FR-15 · [#11](../FEATURE_CATALOG.md#11-retrieval-decision-explainability-trace) |
| LLM routing | `pytest rag-protection-proxy/tests/test_llm_routing.py` | FR-16 · [#18](../FEATURE_CATALOG.md#18-llm-egress-routing-by-classification) |
| Tool gateway invoke | API tests + `examples/agentic/mcp_tool_gateway/demo_agent.py` | FR-7 · [#7](../FEATURE_CATALOG.md#7-agent--mcp-tool-gateway-acl-lab-1-ce) |
| Quarantine CE lifecycle | ingest tests + `GET/DELETE /v1/documents/*` | FR-5 · [#15](../FEATURE_CATALOG.md#15-ingest-time-quarantine-ce-lifecycle) |
| Store factory / hybrid | `pytest rag-protection-proxy/tests/test_store_factory.py` | FR-1, FR-10 · ARCHITECTURE §13 |
| ACL backfill CLI | `tools/acl_backfill/` | FR-tool-1 · [#29](../FEATURE_CATALOG.md#29-vector-acl-backfill-a4) |
| Injection benchmark | `tools/inj_bench/` | FR-tool-6 · [#23](../FEATURE_CATALOG.md#23-prompt-injection-benchmark-a7) |
| Posture scorecard | `tools/rag_score/` | FR-tool-5 · [#20](../FEATURE_CATALOG.md#20-rag-posture-scorecard) |
| Red-team harness | `tools/redteam/` | FR-tool-3 · [#10](../FEATURE_CATALOG.md#10-packaged-red-team-harness-lab-5) |
| Console five workspaces | `console/packages/ce/**/*.test.tsx` | FR-8 · [#1](../FEATURE_CATALOG.md#1-document-level-acl--4-guardrail-pipeline) |
| Capability readiness (CE rows) | [CAPABILITY_READINESS.md](../../../ENTERPRISE.md) | All FRs |

---

## Engineering reference

| Topic | Source |
|-------|--------|
| Per-feature detail + validation | [FEATURE_CATALOG.md](../FEATURE_CATALOG.md) · [FEATURE_CATALOG_INDEX.md](../../shared/FEATURE_CATALOG_INDEX.md) |
| Feature design + tests (legacy matrix) | [MASTER_FEATURES_CATALOG.md](../README.md) |
| Implementation status | [IMPLEMENTATION_STATUS.md](../README.md) |
| Seam test plan | [CE_EE_SEAM_TEST_PLAN.md](../../../ENTERPRISE.md) |
