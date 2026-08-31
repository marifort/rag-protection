# Feature ID aliases (Lab / A → Catalog #)

| Field | Value |
|-------|-------|
| **Audience** | Internal — engineering, product, SE, docs |
| **Status** | Canonical · July 2026 |
| **Purpose** | Freeze one product identity: edition catalog **`#1–#31`**. Lab / A / T0.x labels are **legacy aliases** only. |
| **Authority** | [FEATURE_CATALOG_INDEX.md](FEATURE_CATALOG_INDEX.md) · CE/EE technical catalogs |

---

## Rule

1. **Canonical ID** in titles, talk tracks, tutorials, FR links, and demos: **`#N`** (edition catalog rank).
2. **Legacy aliases** (Lab 1–10, A1–A10, T0.x) may appear once as an alias note or in a folder path — never as the primary identity beside a conflicting number.
3. **Depth packages** stay under `docs/commercial/labs/<folder>/` until merged into `docs/ce/features/` or `docs/ee/features/`; canonical pages are listed in [INDEX.md](../INDEX.md).
4. **Folder rename** (`lab9-…` → `f02-…`) is deferred — paths keep historical names; prose does not.

---

## Alias map (legacy → catalog)

| Legacy | Catalog # | Feature | Depth folder |
|--------|-----------|---------|--------------|
| — | **#1** | Document-level ACL + 4-guardrail pipeline | *(core product — no lab folder)* |
| Lab 9 | **#2** | Corpus-extraction monitor | `lab9-extraction-monitor/` |
| Lab 10 | **#3** | Canary / honeypot documents | `lab10-canary-docs/` |
| Lab 4 | **#4** | Permission drift monitor | `lab4-drift/` |
| Lab 3 | **#5** | SIEM pack + prebuilt detections | `lab3-siem/` |
| Lab 2 | **#6** | CI shift-left ACL scanner (`rag-scan`) | `lab2-config-scanner/` |
| Lab 1 (CE) | **#7** | Agent / MCP tool gateway ACL | `lab1-mcp/` |
| — | **#8** | Per-claim citation hard gate | *(core — guardrails docs)* |
| — | **#9** | Tamper-evident audit log | *(core — audit docs)* |
| Lab 5 | **#10** | Packaged red-team harness | `lab5-redteam/` |
| — | **#11** | Retrieval-decision explainability trace | *(core — E3 / console)* |
| Lab 4 / T0.5 | **#12** | Real-time ACL sync v2 | `lab4-drift/` (`ACL_SYNC_V2.md`) |
| Lab 1 (EE) | **#13** | MCP tool gateway EE SKU (registry) | `lab1-mcp/` (`EE_SKU.md`) |
| A5 | **#14** | Compliance evidence pack | `a5-evidence-pack/` |
| quarantine deepen | **#15** | Ingest-time quarantine (CE API + EE UI) | `quarantine-deepen/` |
| — | **#16** | ReBAC / external authz *(Planned)* | — |
| A1 | **#17** | DLP compliance pattern packs | `a1-dlp-packs/` |
| T0.6 | **#18** | LLM egress routing by classification | `t06-llm-egress-routing/` |
| Lab 6 / A6 | **#19** | Grounding / hallucination checker | `lab6-grounding/` |
| Lab 8 / A3 | **#20** | RAG posture scorecard | `lab8-posture-scorecard/` |
| A8 | **#21** | Egress / SSRF guard packs | `a8-egress-packs/` |
| A9 | **#22** | Industry policy baselines | `a9-baselines/` |
| A7 | **#23** | Prompt-injection benchmark | `a7-injbench/` |
| — | **#24** | Purpose-based access + break-glass *(Planned)* | — |
| — | **#25** | Reversible tokenization vault *(Planned)* | — |
| A10 | **#26** | Weekly AI security digest | `a10-digest/` |
| Lab 7 / A2 | **#27** | MCP manifest linter | `lab7-mcp-lint/` |
| — | **#28** | 2nd + 3rd live connectors *(Planned)* | — |
| A4 | **#29** | Vector ACL backfill | `a4-acl-backfill/` |
| — | **#30** | Per-tenant BYOK encryption *(Planned)* | — |
| — | **#31** | Embedding-space poisoning detection *(Deferred)* | — |

### Composite / UI-only packages

| Alias | Catalog refs | Folder |
|-------|--------------|--------|
| Exfil correlation (UI #6) | **#2** + **#3** | `exfil-correlation/` |

---

## Title convention (depth packages)

```markdown
# #N — Short feature name — Architecture, Design & Implementation

**Catalog ID:** [#N](../ce/README.md) · **Legacy alias:** Lab X / AY
```

Same pattern for BOUNDARY, DEMO_SCRIPT, TALK_TRACK, CONTROL_MAP, UI_TESTING, README H1s.

---

## Where to look up a feature

| Need | Open |
|------|------|
| Jump table #1–#31 | [FEATURE_CATALOG_INDEX.md](FEATURE_CATALOG_INDEX.md) |
| Technical what/why/how | CE/EE `FEATURE_CATALOG.md` |
| Plain-English | CE/EE `learn/` |
| Demo / control depth | [../commercial/labs/README.md](../../ENTERPRISE.md) |
| Historical Lab/A build index | [../commercial/LABS_AND_OPPORTUNITIES_MASTER_INDEX.md](../../ENTERPRISE.md) |
