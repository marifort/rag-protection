# Community Edition (CE) documentation

**Product:** Marifort Gate · **Vendor:** Marifort Systems Inc.  
**Audience:** OSS contributors, evaluators, security architects.  
**Repo:** `rag-protection-proxy` — **public MIT** at launch.  
**Package:** `rag-protection-proxy` · **Console:** five workspaces (Overview, Query Lab, Documents & Ingest, Tool Gateway, Audit Log).

## Which doc?

Same `#N` appears in several places on purpose. Pick by **job**, not by filename similarity.

| I need to… | Open | This layer owns |
|------------|------|-----------------|
| Find a feature by number | [INDEX.md](../INDEX.md) | `#N` spine only |
| Get up to speed (lead / analyst / manager) | [learn/00-study-path.md](learn/00-study-path.md) | Ordered curriculum — features **and** E3 phase depth |
| Know behavior, policy knobs, block reasons | [features/](features/README.md) | **Source of truth** for CE feature behavior |
| Run a ~5 min demo | [demos/](demos/README.md) | Commands + expected output |
| Understand the guardrail pipeline | [security/](security/README.md) | Order, scan semantics, P1/P2, detection map |
| Learn a feature from scratch | [learn/](learn/README.md) | Teaching (analogy → first hands-on) — **not** the tech catalog |
| Look up APIs / matrices / non-claims | [FEATURE_CATALOG.md](FEATURE_CATALOG.md) | Technical reference — **not** the teaching catalog |
| Follow a multi-feature path | [tutorials/](tutorials/README.md) | Cross-feature walks (T01–T09; T08 → [EE body](../../ENTERPRISE.md)) |
| Install a local Python venv | [guide/LOCAL_SETUP.md](guide/LOCAL_SETUP.md) | Python version, libraries, activate, verify |
| Operate / integrate / develop | [guide/](guide/README.md) | Dev, admin, user, design, functional spec |
| Explain how clients use RAG + MCP (API · Python · UI) | [product/CLIENT_USAGE.md](../product/CLIENT_USAGE.md) | Plain-English narrative spine with doc links |
| Sell / deep lab package | [commercial/labs/](../../ENTERPRISE.md) | SPEC, talk track, BOUNDARY (link from card; don’t duplicate knobs) |

**Naming trap:** `learn/` (teaching) ≠ `FEATURE_CATALOG.md` (tech reference). Former path `feature-catalog/` redirects to `learn/`. Cards under `features/` are the short source of truth.

**Authoring:** new or rewritten CE feature pages follow the [feature card template](features/README.md#authoring-template). New files: [edition map](README.md) (`docs/ce/` only).

## Quick paths

| I need… | Open |
|---------|------|
| Feature lookup (#1–#31, CE rows) | [INDEX.md](../INDEX.md) |
| Architecture | [shared/architecture.md](../shared/architecture.md) |
| Guardrail pipeline | [security/README.md](security/README.md) |
| Hands-on tutorials | [tutorials/README.md](tutorials/README.md) |
| Technical catalog | [FEATURE_CATALOG.md](FEATURE_CATALOG.md) |
| Feature teaching guides | [learn/](learn/README.md) |
| 5-min demo scripts | [demos/](demos/) |
| Local Python venv | [guide/LOCAL_SETUP.md](guide/LOCAL_SETUP.md) |
| Docker Model Runner / no-Desktop LLM | Root [README.md](../../README.md) |
| Guides (dev / admin / user) | [guide/README.md](guide/README.md) |
| Ownership handoff | [shared/PRODUCT_OWNERSHIP_GUIDE.md](../shared/PRODUCT_OWNERSHIP_GUIDE.md) |
| Admin / operator (CE home) | [guide/ADMIN_GUIDE.md](guide/ADMIN_GUIDE.md) · [settings + tests](guide/ADMIN_SETTINGS_AND_TESTS.md) |
| Validate before commit | [product/DEV_WORKFLOW_QUICK.md](README.md) |

## Feature pages

**Full table:** [INDEX.md](../INDEX.md) · **Card rules:** [features/README.md](features/README.md) · **Demos:** [demos/README.md](demos/README.md)

Shipped CE feature cards: [`features/`](features/). Pipeline depth: [`security/`](security/README.md). Tech reference: [`FEATURE_CATALOG.md`](FEATURE_CATALOG.md). Teaching guides: [`learn/`](learn/README.md).

## EE boundary

CE runs standalone. EE-only routes return **404** (not greyed UI). EE extensions live in [ee/README.md](../../ENTERPRISE.md).
