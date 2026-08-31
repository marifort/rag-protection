> **Canonical navigation:** [INDEX.md](../../INDEX.md) · technical detail [FEATURE_CATALOG.md](../FEATURE_CATALOG.md).

> **This folder is `learn/` (teaching guides) — not [`FEATURE_CATALOG.md`](../FEATURE_CATALOG.md)** (technical matrices). Behavior and policy knobs live on [`features/`](../features/) cards.

# Community Edition learn guides

| Field | Value |
|-------|-------|
| **Edition** | Community Edition (CE) |
| **Audience** | Engineers learning CE from scratch — evaluators, operators, AppSec, platform |
| **Purpose** | Per-feature learning guide: plain English, why, how, what-if-not, scenario, then hands-on tutorial |
| **Package** | `rag-protection-proxy` |

**New lead / analyst / manager:** start with the [**study path**](00-study-path.md) — role-based reading order that covers shipped features **and** E3 phase depth (e.g. entailment E3.5) without swallowing the whole docs tree. EE continuation: [ee/learn/00-study-path.md](../../../ENTERPRISE.md).

This catalog is for engineers who are **new to these features**. Each entry teaches the concept first (plain English, analogy, step-by-step behavior, without/with, who cares, example), then provides a copy-paste **Tutorial**.

**Not the tech catalog:** implementation matrices live in [FEATURE_CATALOG.md](../FEATURE_CATALOG.md). **Policy knobs / block reasons:** always defer to the one-page [feature card](../features/README.md) — do not re-specify them here. Short demos: [demos/](../demos/). Multi-feature walks: [tutorials/](../tutorials/). CE doc map: [ce/README § Which doc?](../README.md#which-doc).

## Coverage status (validated)

Cross-checked against [INDEX.md](../../INDEX.md) (#1–#31), [features/](../features/), and teaching-section completeness. **Last validated:** July 2026.

| Scope | In this catalog | Status |
|-------|-----------------|--------|
| Ranked CE shipped / pack | #1–#3, #5–#11, #15 (CE lifecycle), #18–#20, #23, #27, #29 | **Complete** — none missing |
| Unranked CE foundations | E3 guardrail depth · identity modes · retrieval stores · audit/observability · Patterns A/B/C | **Present** |
| EE-only ranked features | — | See [EE feature tutorials](../../../ENTERPRISE.md) |
| Planned / deferred (#16, #24–#25, #28, #30–#31) | Not CE | Documented in [EE roadmap](../../../ENTERPRISE.md) |

**Teaching sections (ranked CE entries):** each has In plain English · Everyday analogy · What happens · Without/With · Who cares · Tutorial.

**Soft gap:** identity, stores, and audit include try-it commands and prose but not the full analogy / who-cares template used for ranked `#N` features. **Patterns A/B/C** (especially Pattern C + Pinecone) now follow the full teaching template in [02-runtime-and-operations.md § Integration Patterns](02-runtime-and-operations.md#integration-patterns-abc).

**#15** appears in both CE (API lifecycle) and EE (review UI) catalogs — intentional.

## Lab depth packages

<a id="lab-depth-packages"></a>

Many ranked features have a **depth package** under [`docs/commercial/labs/`](../../../ENTERPRISE.md) — SPEC, DEMO_SCRIPT, BOUNDARY, control maps, and UI testing. Those folders keep historical Lab/A names; product IDs are always **`#N`** ([aliases](../../shared/FEATURE_ID_ALIASES.md)).

**How to use them:** start with this learn entry (learn + try), then open the **Lab depth** row / **Related → Lab depth package** for the full old lab deliverables (SPEC, DEMO_SCRIPT, BOUNDARY, CONTROL_MAP, UI_TESTING, TALK_TRACK) with paths updated to this catalog and `shared/FEATURE_ID_ALIASES.md`.

| Feature | Lab folder |
|---------|------------|
| #2 Extraction monitor | [lab9-extraction-monitor/](../../../ENTERPRISE.md) · [exfil-correlation/](../../../ENTERPRISE.md) |
| #3 Canary docs | [lab10-canary-docs/](../../../ENTERPRISE.md) · [exfil-correlation/](../../../ENTERPRISE.md) |
| #5 SIEM pack | [lab3-siem/](../../../ENTERPRISE.md) |
| #6 Config scanner | [lab2-config-scanner/](../../../ENTERPRISE.md) |
| #7 Tool gateway | [lab1-mcp/](../../../ENTERPRISE.md) |
| #10 Red-team | [lab5-redteam/](../../../ENTERPRISE.md) |
| #15 Quarantine | [quarantine-deepen/](../../../ENTERPRISE.md) |
| #18 LLM egress routing | [t06-llm-egress-routing/](../../../ENTERPRISE.md) |
| #19 Grounding | [lab6-grounding/](../../../ENTERPRISE.md) |
| #20 Posture scorecard | [lab8-posture-scorecard/](../../../ENTERPRISE.md) |
| #23 InjBench | [a7-injbench/](../../../ENTERPRISE.md) |
| #27 MCP lint | [lab7-mcp-lint/](../../../ENTERPRISE.md) |
| #29 ACL backfill | [a4-acl-backfill/](../../../ENTERPRISE.md) |

#1, #8, #9, #11, E3, and platform foundations have no dedicated lab folder — use [security/](../security/README.md), [FEATURE_CATALOG.md](../FEATURE_CATALOG.md), and the in-entry tutorials.

Full labs index: [commercial/labs/README.md](../../../ENTERPRISE.md).## Shared prerequisites

Run these once from the repository root before any tutorial in this catalog:

```bash
bash tools/docker_start.sh --smoke   # or full start without --smoke
export BASE=http://localhost:8090
# Policy: Docker uses data/policy.yaml; host uvicorn uses rag-protection-proxy/config/policy.yaml
```

**`$BASE` is required** for every curl that uses `$BASE/...`. New terminals, restored sessions, and shells that did not inherit the export leave `$BASE` empty — `curl` then fails with a malformed URL and no JSON body. Re-run `export BASE=http://localhost:8090` (or paste the **Shell setup** block at the top of each learn file) before continuing.

**Demo tokens** (sample ACL in `config/acl_policy.yaml`):

| Token | Role | Typical use |
|-------|------|-------------|
| `employee-demo-token` | engineering | Blocked from payroll |
| `hr-demo-token` | hr | Payroll + DLP demos |
| `exec-demo-token` | executives | Exec-classified docs |
| `acme-employee-token` / `globex-employee-token` / `globex-hr-token` | tenant people | Acme vs Globex isolation (Query Lab lists these even when Operator tenant is only `default`) |
| `rag-admin-demo-key` | admin | Operator APIs + console |
| `rag-ingest-admin-key` | ingest admin | Ingest / quarantine APIs |
| `rag-audit-reader-key` | audit reader | Read-only audit access |
| `rag-policy-admin-key` | policy admin | Reload policy; no ingest |

Persona scenes: [IDENTITY_DEMO_PLAYBOOK.md](../../../ENTERPRISE.md)

Individual entries reference this block as **Shared stack** instead of repeating it.

## Maturity legend

| Status | Meaning |
|--------|---------|
| **Shipped** | Available in current CE release |
| **Shipped MVP** | Working CE core with documented scope limits |
| **Shipped CLI** | Command-line tool; not a console workflow |
| **Partial CE lifecycle** | CE API lifecycle; richer review UX is Enterprise |
| **Pack** | Deployable artifacts over shipped CE telemetry |
| **Platform capability** | Foundation used by multiple ranked features |

Enterprise-only behavior is mentioned only as a boundary, not as CE.

## Navigate by feature number

### Part 1 — Core moats

- [#1 Document-level ACL + 4-guardrail pipeline](01-core-moats.md#1-document-level-acl--4-guardrail-pipeline)
- [#2 Corpus-extraction monitor](01-core-moats.md#2-corpus-extraction-monitor)
- [#3 Canary / honeypot documents](01-core-moats.md#3-canary--honeypot-documents)
- [#5 SIEM pack + prebuilt detections](01-core-moats.md#5-siem-pack--prebuilt-detections)
- [#6 CI shift-left ACL scanner](01-core-moats.md#6-ci-shift-left-acl-scanner)
- [#7 Agent / MCP tool gateway ACL](01-core-moats.md#7-agent--mcp-tool-gateway-acl)
- [#8 Per-claim citation hard gate](01-core-moats.md#8-per-claim-citation-hard-gate)
- [#9 Tamper-evident audit log](01-core-moats.md#9-tamper-evident-audit-log)
- [#10 Packaged red-team harness](01-core-moats.md#10-packaged-red-team-harness)
- [#11 Retrieval-decision explainability trace](01-core-moats.md#11-retrieval-decision-explainability-trace)

### Part 2 — Runtime and operations

- [#15 Ingest-time quarantine CE lifecycle](02-runtime-and-operations.md#15-ingest-time-quarantine-ce-lifecycle)
- [#18 LLM egress routing by classification](02-runtime-and-operations.md#18-llm-egress-routing-by-classification)
- [E3 guardrail depth](02-runtime-and-operations.md#e3-guardrail-depth)
- [Identity modes](02-runtime-and-operations.md#identity-modes)
- [Retrieval stores](02-runtime-and-operations.md#retrieval-stores)
- [Audit and observability](02-runtime-and-operations.md#audit-and-observability)
- [Integration Patterns A/B/C](02-runtime-and-operations.md#integration-patterns-abc)

### Part 3 — Tools and assessment

- [#19 Grounding / hallucination checker](03-tools-and-assessment.md#19-grounding--hallucination-checker)
- [#20 RAG posture scorecard](03-tools-and-assessment.md#20-rag-posture-scorecard)
- [#23 Prompt-injection benchmark](03-tools-and-assessment.md#23-prompt-injection-benchmark)
- [#27 MCP manifest linter](03-tools-and-assessment.md#27-mcp-manifest-linter)
- [#29 Vector ACL backfill](03-tools-and-assessment.md#29-vector-acl-backfill)

## Navigate by role

**Onboarding (preferred):** [00-study-path.md](00-study-path.md) — Lead engineer · Analyst · Manager paths with time budgets and E3.x bridges.

| Role | Start here | Why |
|------|------------|-----|
| **New lead / analyst / manager** | [Study path](00-study-path.md) | Ordered curriculum; features + phase depth without reading everything |
| **Security architect / CISO** | [#1](01-core-moats.md#1-document-level-acl--4-guardrail-pipeline), [#2](01-core-moats.md#2-corpus-extraction-monitor), [#3](01-core-moats.md#3-canary--honeypot-documents), [#20](03-tools-and-assessment.md#20-rag-posture-scorecard) | Understand the control model and measure configuration risk |
| **SOC / incident response** | [#5](01-core-moats.md#5-siem-pack--prebuilt-detections), [#9](01-core-moats.md#9-tamper-evident-audit-log), [#11](01-core-moats.md#11-retrieval-decision-explainability-trace), [Audit](02-runtime-and-operations.md#audit-and-observability) | Detect, investigate, and export decisions |
| **Platform / application engineering** | [#1](01-core-moats.md#1-document-level-acl--4-guardrail-pipeline), [#7](01-core-moats.md#7-agent--mcp-tool-gateway-acl), [#18](02-runtime-and-operations.md#18-llm-egress-routing-by-classification), [Integration patterns](02-runtime-and-operations.md#integration-patterns-abc) | Integrate query, tool, and model paths |
| **DevSecOps / AppSec** | [#6](01-core-moats.md#6-ci-shift-left-acl-scanner), [#10](01-core-moats.md#10-packaged-red-team-harness), [#23](03-tools-and-assessment.md#23-prompt-injection-benchmark), [#27](03-tools-and-assessment.md#27-mcp-manifest-linter) | Shift checks into CI and regression testing |
| **Governance / compliance** | [#8](01-core-moats.md#8-per-claim-citation-hard-gate), [#9](01-core-moats.md#9-tamper-evident-audit-log), [#19](03-tools-and-assessment.md#19-grounding--hallucination-checker), [#20](03-tools-and-assessment.md#20-rag-posture-scorecard) | Build traceability evidence without certification claims |
| **Data / knowledge operations** | [#15](02-runtime-and-operations.md#15-ingest-time-quarantine-ce-lifecycle), [Retrieval stores](02-runtime-and-operations.md#retrieval-stores), [#29](03-tools-and-assessment.md#29-vector-acl-backfill) | Control corpus intake and repair ACL metadata |

## Edition-wide accuracy guardrails

1. Qdrant enforces ACL in the retrieval query; SQLite filters in application code **before scoring**.
2. CE DLP is regex, custom patterns, and heuristic NER — not vendor semantic DLP or Presidio.
3. The CE console has exactly five workspaces: Overview, Query Lab, Documents & Ingest, Tool Gateway, and Audit Log.
4. Tool invocation is API-driven (`POST /v1/tools/invoke`); the CE Tool Gateway workspace lists policy and CHALLENGE queue only.
5. CE ingest quarantine supports metadata list, delete, and clean re-ingest. Approve-in-place and content preview are Enterprise.
6. Assessment tools (#6, #19, #20, #23) produce diagnostics and evidence — not certifications or penetration-test substitutes.
7. Do not claim zero-leakage, WORM storage, or Enterprise entitlements as CE.

## Parts

0. [Study path (new lead / analyst / manager)](00-study-path.md)
1. [Core moats](01-core-moats.md)
2. [Runtime and operations](02-runtime-and-operations.md)
3. [Tools and assessment](03-tools-and-assessment.md)
