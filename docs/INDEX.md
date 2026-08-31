# Feature index (#1–#31)

**Canonical product IDs.** Use `#N` in all new writing. Legacy Lab/A folder names are aliases only.

**Edition:** `CE` = public MIT · `EE` = private `rag-protection-enterprise` · `Both` = CE base + EE extension · `Pack` = deploy artifact

| # | Feature | Ed. | Status | Feature page | Demo | Tutorial |
|---|---------|-----|--------|--------------|------|----------|
| 1 | Document ACL + 4-guardrail pipeline | CE | Shipped | [ce/features/01](ce/features/01-acl-pipeline.md) · [security/](ce/security/README.md) | [demo](ce/demos/01-acl-pipeline.md) | [T01](ce/tutorials/01-getting-started-and-guardrails.md) |
| 2 | Corpus-extraction monitor | CE | Shipped | [ce/features/02](ce/features/02-extraction-monitor.md) | [demo](ce/demos/02-extraction-monitor.md) | [T09 §A](ce/tutorials/09-implemented-features-walkthrough.md#part-a-corpus-extraction-monitor-lab-9-2) |
| 3 | Canary / honeypot documents | CE | Shipped | [ce/features/03](ce/features/03-canary-docs.md) | [demo](ce/demos/03-canary-docs.md) | [T09 §B](ce/tutorials/09-implemented-features-walkthrough.md#part-b-canary-honeypot-documents-lab-10-3) |
| 4 | Permission drift monitor | EE | Shipped | [ee/features/04](../ENTERPRISE.md) | [demo](../ENTERPRISE.md) | [T09 §D](ce/tutorials/09-implemented-features-walkthrough.md#part-d-permission-drift-monitor-lab-4-4-ee) |
| 5 | SIEM pack + detections | Pack | Shipped | [ce/features/05](ce/features/05-siem-pack.md) | [demo](ce/demos/05-siem-pack.md) | [T09 §C](ce/tutorials/09-implemented-features-walkthrough.md#part-c-siem-pack-onboarding-lab-3-5) |
| 6 | CI ACL scanner (`rag-scan`) | CE | Shipped | [ce/features/06](ce/features/06-config-scanner.md) | [demo](ce/demos/06-config-scanner.md) | [T05](ce/tutorials/05-labs-2-through-5.md) |
| 7 | MCP tool gateway ACL | CE | Shipped | [ce/features/07](ce/features/07-tool-gateway.md) | [demo](ce/demos/07-tool-gateway.md) | [T04](ce/tutorials/04-agent-mcp-tool-gateway-lab1.md) · [T09 §I](ce/tutorials/09-implemented-features-walkthrough.md#part-i-tool-gateway-console-7-l1-202) |
| 8 | Per-claim citation hard gate | CE | Shipped | [ce/features/08](ce/features/08-citation-hard-gate.md) · [GUARDRAIL_4](ce/security/GUARDRAIL_4_CITATION.md) | [demo](ce/demos/08-citation-hard-gate.md) | [T09 §E](ce/tutorials/09-implemented-features-walkthrough.md#part-e-per-claim-citation-hard-gate-8) |
| 9 | Tamper-evident audit log | CE | Shipped | [ce/features/09](ce/features/09-audit-integrity.md) | [demo](ce/demos/09-audit-integrity.md) | [T09 §F](ce/tutorials/09-implemented-features-walkthrough.md#part-f-tamper-evident-audit-log-9-t04) |
| 10 | Red-team harness | CE | Shipped | [ce/features/10](ce/features/10-redteam.md) | [demo](ce/demos/10-redteam.md) | [T05](ce/tutorials/05-labs-2-through-5.md) · [T08 §16](../ENTERPRISE.md#part-16--lab-5-packaged-red-team-harness-rank-1) |
| 11 | Retrieval explainability trace | CE | Shipped | [ce/features/11](ce/features/11-retrieval-trace.md) | [demo](ce/demos/11-retrieval-trace.md) | [T09 §G](ce/tutorials/09-implemented-features-walkthrough.md#part-g-retrieval-explainability-trace-11-t07) |
| 12 | Real-time ACL sync v2 | EE | Shipped | [ee/features/12](../ENTERPRISE.md) | [demo #4](../ENTERPRISE.md) | [T09 §H](ce/tutorials/09-implemented-features-walkthrough.md#part-h-real-time-acl-sync-v2-t05-12-ee) |
| 13 | MCP tool registry (EE SKU) | EE | Shipped | [ee/features/13](../ENTERPRISE.md) | [demo](../ENTERPRISE.md) | [T09 §J](ce/tutorials/09-implemented-features-walkthrough.md#part-j-lab-1-ee-tool-registry-l1-402-13) |
| 14 | Compliance evidence pack | EE | Shipped | [ee/features/14](../ENTERPRISE.md) | [demo](../ENTERPRISE.md) | [T08 §22](../ENTERPRISE.md#part-22--a5-compliance-evidence-pack-generator) · [T09 §K](ce/tutorials/09-implemented-features-walkthrough.md#part-k-compliance-evidence-pack-a5-14) |
| 15 | Ingest quarantine | Both | Shipped | [CE](ce/features/15-ingest-quarantine.md) · [EE](../ENTERPRISE.md) | [demo](../ENTERPRISE.md) | [T09 §M](ce/tutorials/09-implemented-features-walkthrough.md#part-m-ingest-quarantine-deepen-15) |
| 16 | ReBAC / external authz | EE | Planned | [ee/features/16](../ENTERPRISE.md) | — | — |
| 17 | DLP compliance packs | EE | Shipped | [ee/features/17](../ENTERPRISE.md) | [demo](../ENTERPRISE.md) | [T08](../ENTERPRISE.md) · [T09 §L](ce/tutorials/09-implemented-features-walkthrough.md#part-l-dlp-compliance-packs-a1-17) |
| 18 | LLM egress routing | CE | Shipped | [ce/features/18](ce/features/18-llm-egress-routing.md) | [demo](ce/demos/18-llm-egress-routing.md) | [T09 §P](ce/tutorials/09-implemented-features-walkthrough.md#part-p-llm-egress-routing-t06-18) |
| 19 | Grounding checker | CE | Shipped | [ce/features/19](ce/features/19-grounding.md) | [demo](ce/demos/19-grounding.md) | [T06](ce/tutorials/06-labs-a2-a3-a6-a7.md) |
| 20 | RAG posture scorecard | CE | Shipped | [ce/features/20](ce/features/20-posture-scorecard.md) | [demo](ce/demos/20-posture-scorecard.md) | [T06](ce/tutorials/06-labs-a2-a3-a6-a7.md) |
| 21 | Egress / SSRF packs | EE | Shipped | [ee/features/21](../ENTERPRISE.md) | [demo](../ENTERPRISE.md) | [T08](../ENTERPRISE.md) |
| 22 | Industry policy baselines | EE | Shipped | [ee/features/22](../ENTERPRISE.md) | [demo](../ENTERPRISE.md) | [T08](../ENTERPRISE.md) |
| 23 | Prompt-injection benchmark | Both | Shipped | [ce/features/23](ce/features/23-injbench.md) | [demo](ce/demos/23-injbench.md) | [T06](ce/tutorials/06-labs-a2-a3-a6-a7.md) |
| 24 | Purpose-based access + break-glass | EE | Planned | [ee/features/24](../ENTERPRISE.md) | — | — |
| 25 | Reversible tokenization vault | EE | Planned | [ee/features/25](../ENTERPRISE.md) | — | — |
| 26 | Weekly AI security digest | EE | Shipped | [ee/features/26](../ENTERPRISE.md) | [demo](../ENTERPRISE.md) | [T08](../ENTERPRISE.md) |
| 27 | MCP manifest linter | CE | Shipped | [ce/features/27](ce/features/27-mcp-lint.md) | [demo](ce/demos/27-mcp-lint.md) | [T06](ce/tutorials/06-labs-a2-a3-a6-a7.md) |
| 28 | 2nd + 3rd live connectors | EE | Planned | [ee/features/28](../ENTERPRISE.md) | — | — |
| 29 | Vector ACL backfill | CE | Shipped | [ce/features/29](ce/features/29-acl-backfill.md) | [demo](ce/demos/29-acl-backfill.md) | [T09 §N](ce/tutorials/09-implemented-features-walkthrough.md#part-n-vector-acl-backfill-a4-29) |
| 30 | Per-tenant BYOK encryption | EE | Planned | [ee/features/30](../ENTERPRISE.md) | — | — |
| 31 | Embedding poisoning detection | — | Deferred | [ee/features/31](../ENTERPRISE.md) | — | — |

Every `#N` has a page under `ce/features/` or `ee/features/` (planned stubs included). Depth for guardrails 1–4: [ce/security/](ce/security/README.md).

---

## EE phases (delivery track)

| Phase | Theme | Location |
|-------|-------|----------|
| E1 | Product hardening | [ee/phases/E1](../ENTERPRISE.md) · [e1/](../ENTERPRISE.md) |
| E2 | Identity & permissions | [ee/phases/E2](../ENTERPRISE.md) · [e2/](../ENTERPRISE.md) |
| E3 | Guardrail depth | [ee/phases/E3](../ENTERPRISE.md) · [e3/](../ENTERPRISE.md) |
| E4 | Scale & compliance | [ee/phases/E4](../ENTERPRISE.md) · [e4/](../ENTERPRISE.md) |
| E5 | Operator UX & connectors | [ee/phases/E5](../ENTERPRISE.md) · [e5/](../ENTERPRISE.md) |
| E6 | Enterprise guardrail packs | [ee/phases/E6](../ENTERPRISE.md) · [e6/](../ENTERPRISE.md) |
| E7 | Framework integrations | [ee/phases/E7](../ENTERPRISE.md) · [e7/](../ENTERPRISE.md) |

Index: [ee/phases/README.md](../ENTERPRISE.md). Old `docs/enterprise/` paths are redirect stubs.

---

## I need to…

| Task | Go to |
|------|-------|
| Understand the pipeline | [shared/architecture.md](shared/architecture.md) |
| Rerank / HyDE vs guardrails / citations | [product/RAG_QUALITY_VS_SECURITY.md](product/RAG_QUALITY_VS_SECURITY.md) |
| Paid D post-ACL rerank design | [product/POST_ACL_RERANK_DESIGN.md](ce/README.md) |
| Paid E HyDE / query expansion design | [product/HYDE_QUERY_EXPANSION_DESIGN.md](ce/README.md) |
| Why **Suspected data theft** without a canary query / missing retire row | [ce/features/03-canary-docs.md](ce/features/03-canary-docs.md#operator-notes-theft-card-hybrid-retrieval-and-missing-retire-rows) · [Qdrant Case D](product/QDRANT_CONFIGURATION_AND_TESTING.md#case-d--retire--delete-in-sqlite-qdrant-point-remains) |
| Client architecture / activity diagrams | [commercial/CLIENT_ARCHITECTURE_AND_FLOWS.md](../ENTERPRISE.md) |
| Production HTTPS / TLS / HA | [shared/PRODUCTION_ARCHITECTURE.md](shared/PRODUCTION_ARCHITECTURE.md) · [scenarios](shared/PRODUCTION_SCENARIOS.md) |
| Ownership handoff | [shared/PRODUCT_OWNERSHIP_GUIDE.md](shared/PRODUCT_OWNERSHIP_GUIDE.md) · [checklist](shared/OWNERSHIP_HANDOFF_CHECKLIST.md) |
| CE security deep dives | [ce/security/](ce/security/README.md) |
| CE guides (dev / **admin home** / user) | [ce/guide/](ce/guide/README.md) · [ADMIN_GUIDE](ce/guide/ADMIN_GUIDE.md) · [settings matrix](ce/guide/ADMIN_SETTINGS_AND_TESTS.md) |
| EE guides (dev / **admin home** / user) | [ee/guide/](../ENTERPRISE.md) · [ADMIN_GUIDE](../ENTERPRISE.md) |
| CE / EE tutorials | [ce/tutorials/](ce/tutorials/README.md) · [ee/tutorials/](../ENTERPRISE.md) |
| EE runbooks (identity demos, OIDC, kind/Helm) | [ee/runbooks/](../ENTERPRISE.md) · [IDENTITY_DEMO_PLAYBOOK](../ENTERPRISE.md) |
| Long-form + learn guides | [shared/FEATURE_CATALOG_INDEX.md](shared/FEATURE_CATALOG_INDEX.md) · [CE learn](ce/learn/README.md) · [EE learn](../ENTERPRISE.md) · [CE tech](ce/FEATURE_CATALOG.md) · [EE tech](../ENTERPRISE.md) |
| Commit / validate | [product/DEV_WORKFLOW_QUICK.md](ce/README.md) |
| Full demo walkthrough | [T09](ce/tutorials/09-implemented-features-walkthrough.md) |
| Founder / GTM | [internal/business/THIS_WEEK.md](../ENTERPRISE.md) · [FOUNDER_DASHBOARD](../ENTERPRISE.md) |
| Legacy stubs / old WHERE_IS | [legacy/](../ENTERPRISE.md) |
| Archive (hubs, preview shims) | [internal/archive/](../ENTERPRISE.md) |
