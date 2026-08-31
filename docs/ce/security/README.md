# CE security controls (guardrail pipeline)

Canonical home for Guardrails 1–4 and P1/P2 depth docs (moved from `docs/guardrails/`).

**Feature card:** [#1 ACL + pipeline](../features/01-acl-pipeline.md) · **Demo:** [demos/01](../demos/01-acl-pipeline.md) · **Tutorial:** [T01](../tutorials/01-getting-started-and-guardrails.md)

## Pipeline order

```text
identity → user-query scan (P1) → ACL retrieval → chunk scan → context isolation → LLM → citation → output scan
```

## Documents

| Layer | Document | Milestone |
|-------|----------|-----------|
| 1 — Document ACL | [GUARDRAIL_1_ACL.md](GUARDRAIL_1_ACL.md) | MVP |
| 2 — Semantic DLP | [GUARDRAIL_2_DLP.md](GUARDRAIL_2_DLP.md) | MVP + P1 |
| 3 — Injection shielding | [GUARDRAIL_3_INJECTION.md](GUARDRAIL_3_INJECTION.md) | MVP + P1 |
| 4 — Citation auditing | [GUARDRAIL_4_CITATION.md](GUARDRAIL_4_CITATION.md) | MVP |
| P1 — User query | [P1_USER_QUERY_GUARDRAILS.md](P1_USER_QUERY_GUARDRAILS.md) | v1 P1 |
| P1 — Ingest security | [P1_INGEST_SECURITY.md](P1_INGEST_SECURITY.md) | v1 P1 |
| P1 — CHALLENGE mode | [P1_CHALLENGE_MODE.md](P1_CHALLENGE_MODE.md) | v1 P1 |
| P2 — Persistent audit | [P2_PERSISTENT_AUDIT.md](P2_PERSISTENT_AUDIT.md) | v1 P2 |
| P2 — Audit / debug | [P2_AUDIT_DEBUG_FORENSICS.md](P2_AUDIT_DEBUG_FORENSICS.md) | v1 P2 |
| P2 — Integration quality | [P2_INTEGRATION_QUALITY.md](P2_INTEGRATION_QUALITY.md) | v1 P2 |
| Detection overview | [DETECTION_OVERVIEW.md](DETECTION_OVERVIEW.md) | All — severity, risk → BLOCK/CHALLENGE, what is policy-tunable |
| Pipeline layers vs signatures | [PIPELINE_LAYERS_AND_THREAT_MAINTENANCE.md](PIPELINE_LAYERS_AND_THREAT_MAINTENANCE.md) | Four-layer sketch mapping, threat-maintenance process, release call (2026-08-28) |

## Related CE moats

| # | Feature | Doc |
|---|---------|-----|
| 2 | Extraction monitor | [features/02](../features/02-extraction-monitor.md) |
| 3 | Canary docs | [features/03](../features/03-canary-docs.md) |
| 8 | Citation hard gate | [features/08](../features/08-citation-hard-gate.md) |
| 11 | Retrieval trace | [features/11](../features/11-retrieval-trace.md) |
| 15 | Ingest quarantine | [features/15](../features/15-ingest-quarantine.md) · [EE UI](../../../ENTERPRISE.md) |

**Validate:** `bash tools/docker_start.sh --smoke` · `pytest -q -m "not live"` in `rag-protection-proxy/`

**Quality vs this pipeline:** rerank / HyDE stay in the client RAG chain; this index is the **control** path (guardrails + citation gate) — [RAG_QUALITY_VS_SECURITY.md](../../product/RAG_QUALITY_VS_SECURITY.md).

Old links to `docs/guardrails/*` redirect via stubs.
