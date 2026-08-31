# CE study path — new lead, analyst, or manager

**Purpose:** One curriculum so you do **not** read the whole docs tree. `learn/` is the spine; `features/`, `security/`, and `phases/` are depth you open only when the path says so.

**Edition floor:** Community Edition. After this path, continue with [EE study path](../../../ENTERPRISE.md) if you own Enterprise.

**How docs layers relate (pick by job):**

| Job | Open | Do not treat as… |
|-----|------|------------------|
| Teach / onboarding | **This path + `learn/` entries** | Full implementation backlog |
| Behavior / policy knobs | [`features/`](../features/) card | Tutorial script |
| ~5 min show | [`demos/`](../demos/) | Architecture essay |
| Guardrail / pipeline depth | [`security/`](../security/) | Product roadmap |
| E-phase engineering depth | [`ee/phases/`](../../../ENTERPRISE.md) | Required linear reading order |
| Ownership handoff (week-1 proofs) | [`shared/PRODUCT_OWNERSHIP_GUIDE.md`](../../shared/PRODUCT_OWNERSHIP_GUIDE.md) | Feature teaching |

Phase labels (E1–E7) are **taxonomy**, not a build queue. Priority lives in [NEXT_STEPS.md](../README.md).

---

## Pick your role (start here)

| Role | Time | Outcome |
|------|------|---------|
| **Lead engineer** | ~2–3 days | Trace identity → retrieval → guardrails → audit; know where E3.x lives; run smoke |
| **Security / SOC analyst** | ~1 day | Explain ACL, DLP, injection, citation, audit; run demos for #1/#8/#9/#11 |
| **Manager / product** | ~2–3 hours | Know shipped CE surface, CE vs EE boundary, and which docs answer which question |

Skip Planned/Deferred items ([EE roadmap](../../../ENTERPRISE.md)).

---

## Path A — Lead engineer

### Day 1 — Floor and pipeline

1. [ce/README — Which doc?](../README.md#which-doc) (5 min)
2. Shared stack: [learn README prerequisites](README.md#shared-prerequisites) → `bash tools/docker_start.sh --smoke`
3. Optional mental model (if RAG / embeddings / “what gets passed to the LLM?” is unclear): [HOW_RAG_WORKS.md](../../product/HOW_RAG_WORKS.md)
4. Teach: [#1 ACL + 4-guardrail pipeline](01-core-moats.md#1-document-level-acl--4-guardrail-pipeline)
5. Depth **only if** you own scanner code: [security/README](../security/README.md) (pipeline order) — stop after the overview table unless debugging a guardrail

### Day 2 — Guardrail depth (E3 map — do not skip)

E3 ships **in CE** but its engineering essays live under `ee/phases/e3/`. Learn the map here; open phase docs on demand.

1. Teach: [E3 guardrail depth](02-runtime-and-operations.md#e3-guardrail-depth) (includes sub-capability table)
2. Teach: [#8 Citation hard gate](01-core-moats.md#8-per-claim-citation-hard-gate) — pairs with **E3.4 / E3.5**
3. Optional deep-dives (open one that matches your ownership):

| If you own… | Read phase | Related feature / security |
|-------------|------------|----------------------------|
| NER / PII | [E3.1](../../../ENTERPRISE.md) | [GUARDRAIL_2](../security/GUARDRAIL_2_DLP.md) |
| PCI/PHI labels | [E3.2](../../../ENTERPRISE.md) | [GUARDRAIL_2](../security/GUARDRAIL_2_DLP.md) |
| Injection ML | [E3.3](../../../ENTERPRISE.md) | [GUARDRAIL_3](../security/GUARDRAIL_3_INJECTION.md) |
| Per-claim citations | [E3.4](../../../ENTERPRISE.md) | [#8](01-core-moats.md#8-per-claim-citation-hard-gate) · [GUARDRAIL_4](../security/GUARDRAIL_4_CITATION.md) |
| Entailment / paraphrase rescue | [E3.5](../../../ENTERPRISE.md) | [#8](01-core-moats.md#8-per-claim-citation-hard-gate) · [GUARDRAIL_4](../security/GUARDRAIL_4_CITATION.md) |
| Hybrid retrieval | [E3.6](../../../ENTERPRISE.md) | [Retrieval stores](02-runtime-and-operations.md#retrieval-stores) |

4. Platform skim: [Identity modes](02-runtime-and-operations.md#identity-modes) · [Retrieval stores](02-runtime-and-operations.md#retrieval-stores) · [Audit](02-runtime-and-operations.md#audit-and-observability)

### Day 3 — Moats you will demo or support

Minimum set (teach entry → card only if changing policy):

| # | Learn | Card / demo when needed |
|---|-------|-------------------------|
| #2 Extraction | [learn](01-core-moats.md#2-corpus-extraction-monitor) | [card](../features/02-extraction-monitor.md) |
| #3 Canary | [learn](01-core-moats.md#3-canary--honeypot-documents) | [card](../features/03-canary-docs.md) |
| #7 Tool gateway | [learn](01-core-moats.md#7-agent--mcp-tool-gateway-acl) | [card](../features/07-tool-gateway.md) |
| #9 Audit integrity | [learn](01-core-moats.md#9-tamper-evident-audit-log) | [card](../features/09-audit-integrity.md) |
| #11 Retrieval trace | [learn](01-core-moats.md#11-retrieval-decision-explainability-trace) | [card](../features/11-retrieval-trace.md) |
| #15 Quarantine | [learn](02-runtime-and-operations.md#15-ingest-time-quarantine-ce-lifecycle) | [card](../features/15-ingest-quarantine.md) |

Full CE index: [learn README — navigate by feature](README.md#navigate-by-feature-number). Multi-feature walk: [Tutorial 09](../tutorials/09-implemented-features-walkthrough.md).

### Stop condition

You can: start the stack, explain the four guardrails, point to the E3.x doc that owns a behavior (e.g. entailment → E3.5), and find the `#N` card for a policy knob — **without** reading all of `phases/` or `product/`.

Then: [EE study path](../../../ENTERPRISE.md) if licensed EE is in scope.

---

## Path B — Security / SOC analyst

1. [#1](01-core-moats.md#1-document-level-acl--4-guardrail-pipeline) → demo [01](../demos/01-acl-pipeline.md)
2. [E3 overview](02-runtime-and-operations.md#e3-guardrail-depth) — know NER / ML injection / citation / entailment exist; open E3.x only when investigating a finding type
3. [#8](01-core-moats.md#8-per-claim-citation-hard-gate) · [#9](01-core-moats.md#9-tamper-evident-audit-log) · [#11](01-core-moats.md#11-retrieval-decision-explainability-trace) · [#5 SIEM](01-core-moats.md#5-siem-pack--prebuilt-detections)
4. [Audit and observability](02-runtime-and-operations.md#audit-and-observability)
5. Optional: [DETECTION_OVERVIEW](../security/DETECTION_OVERVIEW.md)

Do **not** start with E4/E6 phase hubs unless a POC names scale or Presidio.

---

## Path C — Manager / product

1. [ce/README](../README.md) + [INDEX.md](../../INDEX.md) (spine of `#N`)
2. Skim [01-core-moats](01-core-moats.md) headings only (#1–#11) — read full teach sections for items you sell
3. [E3 one-pager in learn](02-runtime-and-operations.md#e3-guardrail-depth) — enough to say “entailment is E3.5, not a separate catalog feature”
4. CE vs EE: [ee/README](../../../ENTERPRISE.md) · skip Planned rows in [EE roadmap](../../../ENTERPRISE.md)
5. Priority / freeze: [NEXT_STEPS — What's next](../README.md#whats-next-post-e3) (first section only)

---

## CE shipped map (learn → depth)

Use this when a phase ID appears in code/tests without a catalog `#N`.

| Topic | Learn | Feature card | Phase / security depth |
|-------|-------|--------------|------------------------|
| ACL + pipeline | [#1](01-core-moats.md#1-document-level-acl--4-guardrail-pipeline) | [01](../features/01-acl-pipeline.md) | [security/](../security/README.md) |
| Extraction / canary / SIEM / CI / tools / citation / audit / red-team / trace | [01-core-moats](01-core-moats.md) | matching `features/0N-*.md` | labs via [lab map](README.md#lab-depth-packages) |
| Quarantine / egress routing / E3 / identity / stores / audit / patterns | [02-runtime](02-runtime-and-operations.md) | [#15](../features/15-ingest-quarantine.md) · [#18](../features/18-llm-egress-routing.md) | [e3/](../../../ENTERPRISE.md) · P1/P2 under [security/](../security/README.md) |
| Grounding / scorecard / InjBench / MCP lint / ACL backfill | [03-tools](03-tools-and-assessment.md) | matching cards | lab packages |

**E3.x ↔ catalog:** E3.4/E3.5 deepen **#8** and Guardrail 4; E3.1–E3.3 deepen Guardrails 2–3; E3.6 deepens retrieval stores. There is no separate `#N` for entailment alone — that is intentional.

---

## Related

- [CE learn index](README.md) · [EE study path](../../../ENTERPRISE.md)
- [Ownership handoff](../../shared/PRODUCT_OWNERSHIP_GUIDE.md) (proof checklist, not teaching)
- [Phases index](../../../ENTERPRISE.md) (engineering depth after this path)
