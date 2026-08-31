# Community Edition — Demo Guide

| Field | Value |
|-------|-------|
| **Edition** | Community Edition (CE) |
| **Audience** | Founders, SEs, evaluators running live or recorded demos |
| **Status** | Consolidated guide · July 2026 |
| **Package** | `rag-protection-proxy` |
| **Scope** | Repeatable ~5-minute CE wedge demo |
| **Exclusions** | EE panes, packs, Evidence Pack, live connectors |

**Related:** [USER_GUIDE.md](USER_GUIDE.md) · [ADMIN_GUIDE.md](ADMIN_GUIDE.md) · [FEATURE_CATALOG.md](../FEATURE_CATALOG.md) · [Plain-English feature catalog](../learn/README.md) · [Identity demo playbook](../../../ENTERPRISE.md) · [Package index](../../../ENTERPRISE.md)

**Source scripts:** [gtm/DEMO_VIDEO_RUNBOOK.md](../../../ENTERPRISE.md) · [ARCHITECTURE § Guardrail Demo Walkthrough](../README.md#guardrail-demo-walkthrough)

---

## 1. Demo goal

Prove in under five minutes that:

1. Retrieval-time ACL blocks unauthorized payroll access.
2. The same corpus allows HR with identity change only.
3. Decisions are auditable.

Optional if time allows: DLP redaction, injection block, citation fallback, Tool Gateway invoke.

---

## 2. Claims you may make (CE)

| OK to say | Do not say |
|-----------|------------|
| Pre-retrieval ACL — unauthorized docs never enter the candidate set | “Zero leakage guaranteed” |
| Open/inspectable trust pipeline | “SOC 2 Type II certified” |
| Demo tokens stand in for Okta/Azure groups | “Live IdP required before any demo” |
| Community scanners are production-usable for many POCs | “Presidio NER / NLI packs included in CE” |
| Enterprise adds connectors, review UX, compliance tooling | Promise EE features as if they were on the CE screen |

Honest positioning: [GTM_HONEST_POSITIONING.md](../../../ENTERPRISE.md)

---

## 3. Preflight (30 minutes before)

```bash
bash tools/build_ce.sh
bash tools/docker_start.sh --smoke
bash tools/smoke_rag_proxy.sh

curl -s http://localhost:8090/health | jq '{status, enterprise_installed, store_backend}'
# Prefer enterprise_installed: false for a pure CE demo
```

Open **http://localhost:8090/ui** (add `?ee=off` if EE is installed).

| Token | Persona |
|-------|---------|
| `employee-demo-token` | Engineer — blocked on payroll |
| `hr-demo-token` | HR — allowed |
| `rag-admin-demo-key` | Operator — Audit Log |

Full people + operator cast (RBAC, tenants, person-is-not-admin, OIDC): [IDENTITY_DEMO_PLAYBOOK.md](../../../ENTERPRISE.md).

---

## 4. Script — 5 minutes

### 0:00 — Problem (30 sec)

**Say:** Internal RAG often fails security review because IdP groups do not map into the vector database. An engineer can semantically retrieve payroll even when file shares would deny access. This gateway enforces document ACL **at retrieval time**.

### 0:30 — Engineer blocked (90 sec)

**UI:** Query Lab → `employee-demo-token` → *What is the Q1 payroll total?*

Or:

```bash
curl -s http://localhost:8090/v1/query \
  -H "Authorization: Bearer employee-demo-token" \
  -H "Content-Type: application/json" \
  -d '{"query":"What is the Q1 payroll total?","top_k":4}' | python3 -m json.tool
```

**Expect:** No `hr-payroll` content / no `$4.2M` from payroll doc.  
**Say:** Unauthorized document never enters the candidate set — not prompt filtering after the fact.

### 2:00 — HR allowed (60 sec)

**UI:** Same query with `hr-demo-token`.

**Expect:** Chunks include payroll document.  
**Say:** Same corpus, different identity groups mapped to `allowed_groups`.

### 3:00 — DLP (optional, 45 sec)

With HR token, highlight redaction / DLP findings on sensitive patterns.  
**Say:** Authorized retrieval still runs DLP before the LLM.

### 3:45 — Audit (75 sec)

**UI:** Audit Log → show allow/block events and analytics card → mention NDJSON export.  
**Say:** Security signs off on POC day-10 by reviewing these decisions.

### 4:45 — Close (15 sec)

**Say:** CE exposes the inspectable trust surface. Enterprise adds live connectors, operator review workflows, and compliance tooling. If this matches your permissions gap, next step is a 2-week POC in your IdP test tenant.

---

## 5. Optional extensions (only if asked)

| Demo | How | Ref |
|------|-----|-----|
| Injection | Jailbreak query → block | [GUARDRAIL_3](../../ce/security/GUARDRAIL_3_INJECTION.md) |
| Citation | Ungrounded path → safe fallback | [GUARDRAIL_4](../../ce/security/GUARDRAIL_4_CITATION.md) |
| Document list ACL | `GET /v1/documents` per token | Architecture API surface |
| Tool Gateway | Invoke allowed `read_file` (Layer 1) | [USER_GUIDE §5](USER_GUIDE.md#5-tool-gateway) |

Keep under 2 extra minutes.

---

## 6. Do **not** demo on CE

| Feature | Why |
|---------|-----|
| CHALLENGE queue / approve reject | EE Tier 2 |
| Policy forms / Pattern Lab / Evidence Pack | EE |
| Google Drive / SCIM live | EE Tier 3 |
| Curated DLP packs / weekly digest | EE entitlements |
| Tutorial 08/09 EE pack walkthroughs | Use [Enterprise Demo Guide](../../../ENTERPRISE.md) |

---

## 7. Pass criteria checklist

- [ ] `/health` OK
- [ ] Engineer payroll query does not surface payroll doc
- [ ] HR payroll query does
- [ ] Audit Log shows corresponding events
- [ ] (Optional) Smoke script green
- [ ] (Optional) Injection query blocked

Manual cases: [GUARDRAIL_TEST_PLAN.md](../../../ENTERPRISE.md) TC-GR-A–D subset.

---

## 8. Troubleshooting mid-demo

| Issue | Fix |
|-------|-----|
| Stack down | `bash tools/docker_start.sh` |
| Empty / citation failures | Model Runner / `RAG_LLM_BASE_URL` |
| EE panes visible | Open `/ui?ee=off` or restart CE-only |
| Prospect insists on live OIDC | Do not block — schedule POC; demo tokens prove ACL path |
| Live failure | Fall back to pre-recorded video from GTM runbook |

---

## 9. After a good demo

1. Send [COMMERCIAL_SUMMARY.md](../../../ENTERPRISE.md) + [CAPABILITY_READINESS.md](../../../ENTERPRISE.md)
2. Offer [POC_SOW_TEMPLATE.md](../../../ENTERPRISE.md)
3. If they need operator review / connectors, switch to [Enterprise Demo Guide](../../../ENTERPRISE.md)

---

## 10. Preflight (expanded)

Run **30 minutes before** any live or recorded session.

```bash
bash tools/build_ce.sh
bash tools/docker_start.sh --smoke
bash tools/smoke_rag_proxy.sh

curl -s http://localhost:8090/health | jq '{status, enterprise_installed, store_backend}'
# Prefer enterprise_installed: false
```

### CE-only UI check

Open **http://localhost:8090/ui?ee=off** — sidebar must show **exactly five** workspaces: Overview, Query Lab, Documents & Ingest, Tool Gateway, Audit Log. No Connectors or Policy panes. Documents & Ingest must **not** show CHALLENGE Queue / Preview / Inspect / Approve.

If EE panes appear without `?ee=off`, rebuild CE-only stack ([ADMIN_GUIDE §3](ADMIN_GUIDE.md#3-verify-ce-only-mode)).

### Policy fixture reset note

Advanced demos (extraction, canary, quarantine, integrity) depend on the **active** policy file:

| Runtime | Active file |
|---------|-------------|
| Docker | `data/policy.yaml` (seeded once from `config/policy.yaml`) |
| Host uvicorn | `rag-protection-proxy/config/policy.yaml` |

If a prior lab left wrong thresholds or `input.challenge_mode: block`, reset demo volumes or copy the repo fixture:

```bash
docker compose down
rm -f data/policy.yaml data/rag.db data/audit.jsonl   # demo volumes only
bash tools/docker_start.sh
# optional: cp data/policy.yaml from repo rich fixture, then reload-policy
```

Full procedure: [ADMIN_GUIDE §17](ADMIN_GUIDE.md#17-policy-fixture-and-clean-demo-volumes).

### Demo tokens (as documented)

| Token | Persona |
|-------|---------|
| `employee-demo-token` | Engineer — blocked on payroll |
| `hr-demo-token` | HR — allowed |
| `exec-demo-token` | Executives — classified docs |
| `rag-admin-demo-key` | Operator — Audit Log, reload, admin APIs |
| `rag-ingest-admin-key` | Ingest / quarantine API demos |

---

## 11. Modular demo scripts

Core **5-minute wedge** (§4) plus optional modules. Each module maps to [FEATURE_CATALOG.md](../FEATURE_CATALOG.md) for deeper samples.

| Module | Duration | Catalog # | When to use | Primary surface |
|--------|----------|-----------|-------------|-----------------|
| **Core ACL wedge** | 5 min | [#1](../FEATURE_CATALOG.md#1-document-level-acl--4-guardrail-pipeline) | Every first meeting | Query Lab + Audit Log |
| DLP on allow | +1 min | [#1](../FEATURE_CATALOG.md#1-document-level-acl--4-guardrail-pipeline) | Security asks “what about PII?” | HR token + payroll query |
| Injection block | +1 min | [#1](../FEATURE_CATALOG.md#1-document-level-acl--4-guardrail-pipeline), [#23](../FEATURE_CATALOG.md#23-prompt-injection-benchmark-a7) | AppSec audience | Jailbreak query |
| Citation / grounding | +1 min | [#8](../FEATURE_CATALOG.md#8-per-claim-citation-hard-gate) | “Hallucination?” objection | Antarctica revenue query |
| Retrieval trace | +1 min | [#11](../FEATURE_CATALOG.md#11-retrieval-decision-explainability-trace) | “Why empty?” tuning | `include_retrieval_trace` |
| Tool gateway | +2 min | [#7](../FEATURE_CATALOG.md#7-agent--mcp-tool-gateway-acl-lab-1-ce) | Agent/MCP buyer | **API invoke** + Tool Gateway queue |
| Quarantine lifecycle | +2 min | [#15](../FEATURE_CATALOG.md#15-ingest-time-quarantine-ce-lifecycle) | Ingest security | curl ingest/list/re-ingest — **no approve UI** |
| Extraction monitor | +3 min | [#2](../FEATURE_CATALOG.md#2-corpus-extraction-monitor-lab-9) | Insider risk / SOC | Scripted queries + audit |
| Canary tripwire | +2 min | [#3](../FEATURE_CATALOG.md#3-canary--honeypot-documents-lab-10) | ACL mapping failures | seed + query + audit |
| Audit integrity | +1 min | [#9](../FEATURE_CATALOG.md#9-tamper-evident-audit-log) | GRC / audit trail | Verify chain badge |
| SIEM pack | +2 min | [#5](../FEATURE_CATALOG.md#5-siem-pack--prebuilt-detections-lab-3) | SOC integration | export + onboard dry-run |
| Red-team evidence | +3 min | [#10](../FEATURE_CATALOG.md#10-packaged-red-team-harness-lab-5) | POC close | `tools/rag-redteam run --all` |
| Shift-left posture | +2 min | [#6](../FEATURE_CATALOG.md#6-ci-shift-left-acl-scanner-lab-2), [#20](../FEATURE_CATALOG.md#20-rag-posture-scorecard) | Platform engineering | `rag-scan` / `rag-score` |
| LLM routing | +2 min | [#18](../FEATURE_CATALOG.md#18-llm-egress-routing-by-classification) | Data residency | Enable `llm_routing` + audit |

**Rule:** never stack more than **two** optional modules after core unless the prospect asked for that depth.

---

## 12. Claim-safe talk track (expanded)

### Opening (problem)

**Say:** “Internal RAG often fails security review because IdP groups never made it into the vector index. File shares would deny payroll to engineering — but semantic search still retrieves it. We enforce document ACL **before** chunks enter the candidate set.”

**Do not say:** “Zero leakage,” “SOC 2 certified,” “Presidio NER included in CE.”

### ACL wedge (core)

**Say:** “Same corpus, same question — only the bearer token changes. Engineering never sees payroll chunks. HR does. That difference is auditable NDJSON, not prompt engineering.”

**Show:** Query Lab or curl side-by-side; Audit Log allow/block pair.

### DLP (optional)

**Say:** “Authorization is not exfiltration approval. CE runs regex, custom patterns, and heuristic NER — not vendor semantic DLP packs. Authorized HR still gets redaction on sensitive patterns.”

### Injection (optional)

**Say:** “Query-level guardrails can block before retrieval and before any LLM call. CE includes ML-assisted injection detection — benchmark with `rag-injbench`, not marketing superlatives.”

### Citation (optional)

**Say:** “We gate ungrounded answers — per-claim mapping and a hard citation gate in shipped policy. That is grounding in retrieved context, not a guarantee of factual world truth.”

### Tool gateway (optional)

**Say:** “Agents need the same ACL and audit stack outside RAG. CE ships an MVP gateway — list and invoke through the API; the UI is policy summary and CHALLENGE review, not a generic MCP console.”

### Quarantine (optional — API only)

**Say:** “Mid-risk ingest can quarantine on CE. Operators list metadata, delete, or re-ingest remediated content over the API. Approve-in-place and content preview are Enterprise review workflows — we do not pretend they are on this CE screen.”

### Close

**Say:** “Community Edition proves the inspectable trust surface: ACL, guardrails, audit. Enterprise adds operator review UX, live connectors, and compliance packs. If this matches your permissions gap, next step is a two-week POC in your IdP test tenant.”

Honest positioning: [GTM_HONEST_POSITIONING.md](../../../ENTERPRISE.md)

---

## 13. Pass criteria checklist (expanded)

### Core wedge (required)

- [ ] `/health` OK; `enterprise_installed: false` for pure CE story
- [ ] UI at `/ui?ee=off` shows **four** workspaces only
- [ ] `employee-demo-token` + payroll question → no payroll doc / no `$4.2M`
- [ ] `hr-demo-token` + same question → payroll chunk(s) visible
- [ ] Audit Log shows matching allow/block (or empty-retrieval) events
- [ ] Admin bearer `rag-admin-demo-key` works for Audit export

### Optional modules (when demoed)

- [ ] Injection query blocked with audit `decision: block`
- [ ] HR query shows DLP findings or redaction (not required for core pass)
- [ ] Ungrounded question → citation failure or safe fallback ([#8](../FEATURE_CATALOG.md#8-per-claim-citation-hard-gate))
- [ ] `include_retrieval_trace: true` shows ACL drop reason ([#11](../FEATURE_CATALOG.md#11-retrieval-decision-explainability-trace))
- [ ] Tool invoke via API: allow + audit `tool_invoke` ([#7](../FEATURE_CATALOG.md#7-agent--mcp-tool-gateway-acl-lab-1-ce))
- [ ] Quarantine ingest → `GET /v1/documents/quarantined` metadata → re-ingest `ok` ([#15](../FEATURE_CATALOG.md#15-ingest-time-quarantine-ce-lifecycle))
- [ ] `bash tools/smoke_rag_proxy.sh` green (pre-demo)
- [ ] `tools/rag-redteam run --scenario acl_bypass_attempt` PASS (POC close)

Manual cases: [GUARDRAIL_TEST_PLAN.md](../../../ENTERPRISE.md) TC-GR-A–D subset.

---

## 14. Do **not** demo — Planned / Deferred / EE-only

### Already excluded (§6 recap)

CHALLENGE **ingest** queue UI, Policy forms, Evidence Pack, live Drive/SCIM, curated DLP packs, EE tutorial packs.

### Planned features — roadmap slide only (#16, #24, #25, #28, #30)

| # | Feature | Why not live demo |
|---|---------|-------------------|
| 16 | ReBAC / external authz | Planned — not in product |
| 24 | Purpose-based access + break-glass | Planned |
| 25 | Reversible tokenization vault | Planned |
| 28 | 2nd + 3rd live connectors | Planned |
| 30 | Per-tenant BYOK encryption | Planned |

**Say instead:** “On the roadmap — happy to align POC scope if that is your blocker.”

### Deferred (#31)

| # | Feature | Why not live demo |
|---|---------|-------------------|
| 31 | Embedding-space poisoning detection | Explicitly deferred — do not imply shipped detection |

### EE Shipped but not on CE screen

Permission drift (#4), connector sync (#12), MCP registry EE SKU (#13), Evidence Pack (#14), DLP packs (#17), SSRF packs (#21), baselines (#22), digest (#26) — pivot to [Enterprise Demo Guide](../../../ENTERPRISE.md) if requested.

Index: [FEATURE_CATALOG_INDEX.md](../../shared/FEATURE_CATALOG_INDEX.md)

---

## 15. Deeper feature demos (catalog index)

For SE prep beyond this guide, use per-feature tutorial blocks in [FEATURE_CATALOG.md](../FEATURE_CATALOG.md):

| Topic | Catalog anchor |
|-------|----------------|
| ACL + pipeline | [#1](../FEATURE_CATALOG.md#1-document-level-acl--4-guardrail-pipeline) |
| Extraction monitor | [#2](../FEATURE_CATALOG.md#2-corpus-extraction-monitor-lab-9) |
| Canary honeypots | [#3](../FEATURE_CATALOG.md#3-canary--honeypot-documents-lab-10) |
| SIEM onboarding | [#5](../FEATURE_CATALOG.md#5-siem-pack--prebuilt-detections-lab-3) |
| CI rag-scan | [#6](../FEATURE_CATALOG.md#6-ci-shift-left-acl-scanner-lab-2) |
| Tool gateway | [#7](../FEATURE_CATALOG.md#7-agent--mcp-tool-gateway-acl-lab-1-ce) |
| Citations | [#8](../FEATURE_CATALOG.md#8-per-claim-citation-hard-gate) |
| Audit integrity | [#9](../FEATURE_CATALOG.md#9-tamper-evident-audit-log) |
| Red-team harness | [#10](../FEATURE_CATALOG.md#10-packaged-red-team-harness-lab-5) |
| Retrieval trace | [#11](../FEATURE_CATALOG.md#11-retrieval-decision-explainability-trace) |
| Quarantine API | [#15](../FEATURE_CATALOG.md#15-ingest-time-quarantine-ce-lifecycle) |
| LLM routing | [#18](../FEATURE_CATALOG.md#18-llm-egress-routing-by-classification) |

Hands-on tutorial index: [product/TUTORIAL.md](../../product/TUTORIAL.md) · Tutorial 09 walkthrough for #2–#3 and advanced CE features.

---

## Engineering reference

| Topic | Source |
|-------|--------|
| Full GTM runbook | [DEMO_VIDEO_RUNBOOK.md](../../../ENTERPRISE.md) |
| Curl walkthrough | [ARCHITECTURE.md § Demo](../README.md#guardrail-demo-walkthrough) |
| Smoke script | `tools/smoke_rag_proxy.sh` |
| Packaging notes | [CE_LEGACY_AND_PACKAGING_NOTES.md](../README.md) |
