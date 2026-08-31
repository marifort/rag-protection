# Edition Feature Catalog Index (#1–#31 + E-phases)

> **Canonical navigation:** [docs/INDEX.md](../INDEX.md) → `ce/features/` · `ee/features/`.  
> This file is the **long-form / feature-tutorial jump table**. Prefer INDEX for day-to-day work.


| Field | Value |
|-------|-------|
| **Audience** | External evaluators and operators · Internal engineering, product, SE, GRC |
| **Status** | Feature tutorial index · July 2026 |
| **Purpose** | Jump table from ranked features and E-phases into CE/EE feature catalogs · **Canonical runtime pages:** [INDEX.md](../INDEX.md) (`ce/features/`, `ee/features/`) |
| **Authority** | Runtime → code + [CE_EE_MOAT](../../ENTERPRISE.md); readiness → [CAPABILITY_READINESS](../../ENTERPRISE.md) |
| **Canonical ID** | Edition catalog **`#1–#31`** — catalog / T0.x are legacy aliases only ([FEATURE_ID_ALIASES.md](FEATURE_ID_ALIASES.md)) |

**Technical catalogs:** [Community](../ce/FEATURE_CATALOG.md) · [Enterprise](../../ENTERPRISE.md)  
**Learn guides** (`learn/` — not the tech catalogs): [Community](../ce/learn/README.md) · [Enterprise](../../ENTERPRISE.md)  
**Lab/A → #N alias map:** [FEATURE_ID_ALIASES.md](FEATURE_ID_ALIASES.md)  
**Package hub:** [README.md](../../ENTERPRISE.md)

---

## Choose the right catalog layer

| Question | Open |
|----------|------|
| What is the feature, in plain English? | CE or EE **`learn/`** → **In plain English** |
| What everyday problem does it resemble? | `learn/` → **Everyday analogy** |
| How does it work step by step? | `learn/` → **What happens** |
| What changes with vs without it? | `learn/` → **Without this / With this** |
| Who cares and why? | `learn/` → **Who cares** / **Business value** |
| How do I try it hands-on? | `learn/` → **Tutorial** |
| Behavior / policy knobs? | CE or EE **feature card** (`features/#N`) |
| How do I configure, call, test, or validate deeply? | CE or EE **technical catalog** (`FEATURE_CATALOG.md`) |
| Is it Shipped, Partial, Planned, or Deferred? | This index, then the relevant catalog entry |

### Split `learn/` guides

| Edition | Part | Coverage |
|---------|------|----------|
| CE | [Core moats](../ce/learn/01-core-moats.md) | #1–#3, #5–#11 |
| CE | [Runtime and operations](../ce/learn/02-runtime-and-operations.md) | #15, #18, E3 + identity, stores, audit, integrations |
| CE | [Tools and assessment](../ce/learn/03-tools-and-assessment.md) | #19, #20, #23, #27, #29 |
| EE | [Operations and governance](../../ENTERPRISE.md) | #4, #12–#15, #17 |
| EE | [Packs and platform](../../ENTERPRISE.md) | #21, #22, #26 + E1/E2/E4/E5/E6/E7 |
| EE | [Roadmap and commercial](../../ENTERPRISE.md) | #16, #24, #25, #28, #30, #31 + commercial artifacts |

---

## Maturity legend

| Status | Meaning | Live demo? |
|--------|---------|------------|
| **Shipped** | Available in current release; tests/runbooks exist | Yes |
| **Partial** | Usable core; production gaps listed | Yes, with caveats |
| **Pack** | Deploy/docs artifact (may have no new runtime code) | Wire-up demo |
| **Commercial** | Contract/legal deliverable, not software | No |
| **Planned** | Roadmap — not available | Roadmap slide only |
| **Deferred** | Explicitly deferred (low priority / arms race) | No |

**Verification note:** EE runtime lives in the private `rag-protection-enterprise` package. When that package is absent from a checkout, EE **Shipped** rows are labeled **private-EE verified** (docs + CI seams), not locally source-proven.

---

## Uniform feature record fields

Every technical entry includes: Identity · What · Why · How it works · Tutorial
+ samples · Admin/User/Demo notes · Validation · Gaps / non-claims.

Every feature-tutorial entry includes: **In plain English** · **Everyday analogy** ·
**What happens (step by step)** · **Without this / With this** · **Business value** ·
**Who cares** · **Example scenario** · **When to use** · **Prerequisites** ·
**Tutorial** (shipped) · **Boundaries** · **Related**.

---

## Ranked features #1–#31

Legacy catalog names are **not** product IDs — see [FEATURE_ID_ALIASES.md](FEATURE_ID_ALIASES.md).

| # | Feature | Edition | Status | Technical | Tutorial |
|---|---------|---------|--------|-----------|---------------|
| 1 | Document-level ACL + 4-guardrail pipeline | CE | Shipped | [ce/features/01](../ce/features/01-acl-pipeline.md) · [security](../ce/security/README.md) · [Tech](../ce/FEATURE_CATALOG.md#1-document-level-acl--4-guardrail-pipeline) | [Try](../ce/learn/01-core-moats.md#1-document-level-acl--4-guardrail-pipeline) |
| 2 | Corpus-extraction monitor | CE | Shipped | [ce/features/02](../ce/features/02-extraction-monitor.md) · [demo](../ce/demos/02-extraction-monitor.md) | [Try](../ce/learn/01-core-moats.md#2-corpus-extraction-monitor) |
| 3 | Canary / honeypot documents | CE | Shipped | [ce/features/03](../ce/features/03-canary-docs.md) · [demo](../ce/demos/03-canary-docs.md) | [Try](../ce/learn/01-core-moats.md#3-canary--honeypot-documents) |
| 4 | Permission drift monitor | EE | Shipped (private-EE verified) | [ee/features/04](../../ENTERPRISE.md) · [demo](../../ENTERPRISE.md) | [Try](../../ENTERPRISE.md#feature-4-permission-drift) |
| 5 | SIEM pack + prebuilt detections | Pack | Pack + onboarding | [ce/features/05](../ce/features/05-siem-pack.md) · [demo](../ce/demos/05-siem-pack.md) | [Try](../ce/learn/01-core-moats.md#5-siem-pack--prebuilt-detections) |
| 6 | CI shift-left ACL scanner | CE | Shipped | [ce/features/06](../ce/features/06-config-scanner.md) · [Tech](../ce/FEATURE_CATALOG.md#6-ci-shift-left-acl-scanner-lab-2) | [Try](../ce/learn/01-core-moats.md#6-ci-shift-left-acl-scanner) |
| 7 | Agent / MCP tool gateway ACL | CE | Shipped (MVP) | [ce/features/07](../ce/features/07-tool-gateway.md) · [demo](../ce/demos/07-tool-gateway.md) | [Try](../ce/learn/01-core-moats.md#7-agent--mcp-tool-gateway-acl) |
| 8 | Per-claim citation hard gate | CE | Shipped | [ce/features/08](../ce/features/08-citation-hard-gate.md) · [demo](../ce/demos/08-citation-hard-gate.md) | [Try](../ce/learn/01-core-moats.md#8-per-claim-citation-hard-gate) |
| 9 | Tamper-evident audit log | CE | Shipped | [ce/features/09](../ce/features/09-audit-integrity.md) · [Tech](../ce/FEATURE_CATALOG.md#9-tamper-evident-audit-log) | [Try](../ce/learn/01-core-moats.md#9-tamper-evident-audit-log) |
| 10 | Packaged red-team harness | CE | Shipped | [ce/features/10](../ce/features/10-redteam.md) · [Tech](../ce/FEATURE_CATALOG.md#10-packaged-red-team-harness-lab-5) | [Try](../ce/learn/01-core-moats.md#10-packaged-red-team-harness) |
| 11 | Retrieval-decision explainability trace | CE | Shipped | [ce/features/11](../ce/features/11-retrieval-trace.md) · [demo](../ce/demos/11-retrieval-trace.md) | [Try](../ce/learn/01-core-moats.md#11-retrieval-decision-explainability-trace) |
| 12 | Real-time ACL sync v2 | EE | Shipped (private-EE verified) | [ee/features/12](../../ENTERPRISE.md) | [Try](../../ENTERPRISE.md#feature-12-acl-sync) |
| 13 | MCP tool gateway EE SKU (registry) | EE | Shipped (private-EE verified) | [ee/features/13](../../ENTERPRISE.md) · [demo](../../ENTERPRISE.md) | [Try](../../ENTERPRISE.md#feature-13-tool-registry) |
| 14 | Compliance evidence pack | EE | Shipped (private-EE verified) | [ee/features/14](../../ENTERPRISE.md) · [demo](../../ENTERPRISE.md) | [Try](../../ENTERPRISE.md#feature-14-evidence-pack) |
| 15 | Ingest-time quarantine (deepen) | CE API + EE UI | Partial / Shipped UI | [CE](../ce/features/15-ingest-quarantine.md) · [EE](../../ENTERPRISE.md) · [demo](../../ENTERPRISE.md) | [CE Try](../ce/learn/02-runtime-and-operations.md#15-ingest-time-quarantine-ce-lifecycle) · [EE Try](../../ENTERPRISE.md#feature-15-quarantine-review) |
| 16 | ReBAC / external authz | — | Planned | [ee/features/16](../../ENTERPRISE.md) · [Tech](../../ENTERPRISE.md#16-rebac--external-authz-planned) | [Try](../../ENTERPRISE.md#feature-16-rebac) |
| 17 | DLP compliance pattern packs | EE | Shipped (private-EE verified) | [ee/features/17](../../ENTERPRISE.md) · [demo](../../ENTERPRISE.md) | [Try](../../ENTERPRISE.md#feature-17-dlp-packs) |
| 18 | LLM egress routing by classification | CE | Shipped | [ce/features/18](../ce/features/18-llm-egress-routing.md) · [demo](../ce/demos/18-llm-egress-routing.md) | [Try](../ce/learn/02-runtime-and-operations.md#18-llm-egress-routing-by-classification) |
| 19 | Grounding / hallucination checker | CE | Shipped (CLI) | [ce/features/19](../ce/features/19-grounding.md) · [Tech](../ce/FEATURE_CATALOG.md#19-grounding--hallucination-checker) | [Try](../ce/learn/03-tools-and-assessment.md#19-grounding--hallucination-checker) |
| 20 | RAG posture scorecard | CE | Shipped (CLI) | [ce/features/20](../ce/features/20-posture-scorecard.md) · [Tech](../ce/FEATURE_CATALOG.md#20-rag-posture-scorecard) | [Try](../ce/learn/03-tools-and-assessment.md#20-rag-posture-scorecard) |
| 21 | Egress / SSRF guard packs | EE | Shipped (private-EE verified) | [ee/features/21](../../ENTERPRISE.md) · [Tech](../../ENTERPRISE.md#21-egress--ssrf-guard-packs-a8) | [Try](../../ENTERPRISE.md#feature-21-egress-packs) |
| 22 | Industry policy baselines | EE | Shipped (private-EE verified) | [ee/features/22](../../ENTERPRISE.md) · [Tech](../../ENTERPRISE.md#22-industry-policy-baselines-a9) | [Try](../../ENTERPRISE.md#feature-22-policy-baselines) |
| 23 | Prompt-injection benchmark | CE+EE | Shipped | [ce/features/23](../ce/features/23-injbench.md) · [Tech](../ce/FEATURE_CATALOG.md#23-prompt-injection-benchmark-a7) | [Try](../ce/learn/03-tools-and-assessment.md#23-prompt-injection-benchmark) |
| 24 | Purpose-based access + break-glass | — | Planned | [ee/features/24](../../ENTERPRISE.md) · [Tech](../../ENTERPRISE.md#24-purpose-based-access--break-glass-planned) | [Try](../../ENTERPRISE.md#feature-24-purpose-break-glass) |
| 25 | Reversible tokenization vault | — | Planned | [ee/features/25](../../ENTERPRISE.md) · [Tech](../../ENTERPRISE.md#25-reversible-tokenization-vault-planned) | [Try](../../ENTERPRISE.md#feature-25-tokenization-vault) |
| 26 | Weekly AI security digest | EE | Shipped (private-EE verified) | [ee/features/26](../../ENTERPRISE.md) · [Tech](../../ENTERPRISE.md#26-weekly-ai-security-digest-a10) | [Try](../../ENTERPRISE.md#feature-26-security-digest) |
| 27 | MCP manifest linter | CE | Shipped (CLI) | [ce/features/27](../ce/features/27-mcp-lint.md) · [Tech](../ce/FEATURE_CATALOG.md#27-mcp-manifest-linter) | [Try](../ce/learn/03-tools-and-assessment.md#27-mcp-manifest-linter) |
| 28 | 2nd + 3rd live connectors | EE | Planned | [ee/features/28](../../ENTERPRISE.md) · [Tech](../../ENTERPRISE.md#28-2nd--3rd-live-connectors-planned) | [Try](../../ENTERPRISE.md#feature-28-live-connectors) |
| 29 | Vector ACL backfill | CE tool | Shipped (EE mapping for full path) | [ce/features/29](../ce/features/29-acl-backfill.md) · [Tech](../ce/FEATURE_CATALOG.md#29-vector-acl-backfill-a4) | [Try](../ce/learn/03-tools-and-assessment.md#29-vector-acl-backfill) |
| 30 | Per-tenant BYOK encryption | — | Planned | [ee/features/30](../../ENTERPRISE.md) · [Tech](../../ENTERPRISE.md#30-per-tenant-byok-encryption-planned) | [Try](../../ENTERPRISE.md#feature-30-byok) |
| 31 | Embedding-space poisoning detection | — | Deferred | [ee/features/31](../../ENTERPRISE.md) · [Tech](../../ENTERPRISE.md#31-embedding-space-poisoning-detection-deferred) | [Try](../../ENTERPRISE.md#feature-31-embedding-poisoning) |

### No hands-on product tutorial yet (design-intent only)

#16 · #24 · #25 · #28 · #30 · #31 — stubs: [ee/features/](../../ENTERPRISE.md) · long-form: EE catalog Planned section.

---

## E-phase capability index

| Phase | Theme | Primary docs |
|-------|-------|--------------|
| MVP / P0–P2 | Core gateway, vector/OIDC, ingest quarantine, persistent audit | [CE catalog](../ce/FEATURE_CATALOG.md) · [CE FS](../ce/guide/FUNCTIONAL_SPECIFICATION.md) · [ce/security](../ce/security/README.md) |
| E1 | Product hardening (UI, Helm, webhooks) | [ee/phases/E1](../../ENTERPRISE.md) · [e1/](../../ENTERPRISE.md) |
| E2 | Identity & permissions (SCIM, Drive, RBAC, tenants) | [ee/phases/E2](../../ENTERPRISE.md) · [e2/](../../ENTERPRISE.md) |
| E3 | Guardrail depth (NER, ML injection, citations, hybrid) | [ee/phases/E3](../../ENTERPRISE.md) · [e3/](../../ENTERPRISE.md) · [CE §E3](../ce/FEATURE_CATALOG.md#e3-guardrail-depth-shipped-in-ce) |
| E4 | Scale & compliance (pgvector, retention, rate limits, HA planned) | [ee/phases/E4](../../ENTERPRISE.md) · [e4/](../../ENTERPRISE.md) |
| E5 | Operator UX & connectors | [ee/phases/E5](../../ENTERPRISE.md) · [e5/](../../ENTERPRISE.md) |
| E6 | Guardrail enterprise packs | [ee/phases/E6](../../ENTERPRISE.md) · [e6/](../../ENTERPRISE.md) |
| E7 | Framework integrations | [ee/phases/E7](../../ENTERPRISE.md) · [e7/](../../ENTERPRISE.md) |

---

## Commercial deliverables (not software FRs)

| Item | Status | Where |
|------|--------|-------|
| Support SLA | Commercial | [EE catalog § Commercial](../../ENTERPRISE.md#commercial-deliverables) |
| DPA / subprocessors | Commercial | same |
| Pentest report | Commercial / Planned | same |
| SOC 2 Type II certification | Planned / Commercial | same — **not certified** |

---

## Role-guide crosswalk

| Need | CE | EE |
|------|----|----|
| Architecture | [ARCHITECTURE](../../ENTERPRISE.md) | [ARCHITECTURE](../../ENTERPRISE.md) |
| Design | [DESIGN](../ce/guide/DESIGN.md) | [DESIGN](../../ENTERPRISE.md) |
| Functional spec | [FUNCTIONAL_SPECIFICATION](../ce/guide/FUNCTIONAL_SPECIFICATION.md) | [FUNCTIONAL_SPECIFICATION](../../ENTERPRISE.md) |
| Admin | [ADMIN_GUIDE](../ce/guide/ADMIN_GUIDE.md) | [ADMIN_GUIDE](../../ENTERPRISE.md) |
| User | [USER_GUIDE](../ce/guide/USER_GUIDE.md) | [USER_GUIDE](../../ENTERPRISE.md) |
| Demo | [DEMO_GUIDE](../ce/guide/DEMO_GUIDE.md) | [DEMO_GUIDE](../../ENTERPRISE.md) |

Hands-on tutorials: [product/TUTORIAL.md](../product/TUTORIAL.md) (T01–T09).

---

## Accuracy constraints (source-verified)

1. ACL is **inside the Qdrant query**; SQLite applies ACL in **application code** before scoring.
2. CE DLP fidelity = regex + custom patterns + heuristic NER — not vendor “semantic DLP.”
3. CE console = **four** workspaces only.
4. CE Tool Gateway UI lists policy / challenge review; **invoke** is primarily API / examples.
5. Policy **reload** is CE; policy **edit / backups / Pattern Lab** are EE.
6. Tutorials must declare policy fixture: clean `config/policy.yaml` seed vs persisted `data/policy.yaml`.
7. Evidence Pack supports evidence collection — **not** a certification.
