# RAG Protection — Tutorial Index

Hands-on tutorials live under [`ce/tutorials/`](../ce/tutorials/README.md) and [`ee/tutorials/`](../../ENTERPRISE.md) (stubs remain in `product/tutorial/`).

Use this page as the landing index for the full tutorial set.

## Tutorial map

| Doc | Covers |
|-----|--------|
| [tutorial/01-getting-started-and-guardrails.md](../ce/tutorials/01-getting-started-and-guardrails.md) | What you are building, install/verify, demo users, first query, four guardrails |
| [tutorial/02-operator-console-ingest-and-audit.md](../ce/tutorials/02-operator-console-ingest-and-audit.md) | Operator console, pattern lab, policy knobs, ingest/quarantine, audit and debug forensics |
| [tutorial/03-extensions-troubleshooting-and-integrations.md](../ce/tutorials/03-extensions-troubleshooting-and-integrations.md) | Vector/OIDC extensions, multi-tenant operator console, OIDC admin roles, troubleshooting, LangChain/Pinecone integration, what you learned |
| [tutorial/04-agent-mcp-tool-gateway-lab1.md](../ce/tutorials/04-agent-mcp-tool-gateway-lab1.md) | **#7** Agent / MCP tool gateway |
| [tutorial/05-labs-2-through-5.md](../ce/tutorials/05-labs-2-through-5.md) | **#6, #5, #4, #10** — config scanner, SIEM pack, permission drift, red-team harness |
| [tutorial/06-labs-a2-a3-a6-a7.md](../ce/tutorials/06-labs-a2-a3-a6-a7.md) | **#27, #20, #19, #23** — MCP linter, posture scorecard, grounding check, injection benchmark |
| [tutorial/07-ci-workflows-and-gates.md](../ce/tutorials/07-ci-workflows-and-gates.md) | CI workflows/gates for shift-left enforcement |
| [tutorial/08-ee-packs-redteam-dlp-baselines-digest.md](../../ENTERPRISE.md) | **#10, #14, #17, #21, #22, #26** — red-team + DLP / evidence / egress / baselines / digest |
| [tutorial/09-implemented-features-walkthrough.md](../ce/tutorials/09-implemented-features-walkthrough.md) | Shipped features walkthrough (**#2–#5, #8–#15, #17–#18**, …) |

## Recommended reading order

1. [Getting started and guardrails](../ce/tutorials/01-getting-started-and-guardrails.md)
2. [Operator console, ingest, and audit](../ce/tutorials/02-operator-console-ingest-and-audit.md)
3. [Extensions, troubleshooting, and integrations](../ce/tutorials/03-extensions-troubleshooting-and-integrations.md)
4. [#7 Agent / MCP tool gateway](../ce/tutorials/04-agent-mcp-tool-gateway-lab1.md)
5. [#6 / #5 / #4 / #10 tools](../ce/tutorials/05-labs-2-through-5.md)
6. [#27 / #20 / #19 / #23 CLIs](../ce/tutorials/06-labs-a2-a3-a6-a7.md)
7. [CI workflows and gates](../ce/tutorials/07-ci-workflows-and-gates.md)
8. [#10 / #14 / #17 / #21 / #22 / #26 EE packs](../../ENTERPRISE.md)
9. [Shipped features walkthrough](../ce/tutorials/09-implemented-features-walkthrough.md) — catalog `#N` end-to-end

## Next steps

| Goal | Document |
|------|----------|
| Admin settings and pytest matrix | [ADMIN_GUIDE.md](../ce/README.md) |
| Multi-tenant + OIDC operator admin | [tutorial/03-extensions-troubleshooting-and-integrations.md#84-multi-tenant-operator-console-e53](../ce/tutorials/03-extensions-troubleshooting-and-integrations.md#84-multi-tenant-operator-console-e53) · [OIDC runbook](../../ENTERPRISE.md) |
| Architecture diagrams and API | [ARCHITECTURE.md](../ce/README.md) |
| Guardrail deep dives | [../guardrails/README.md](../ce/security/README.md) |
| Audit debug forensics | [../guardrails/P2_AUDIT_DEBUG_FORENSICS.md](../ce/security/P2_AUDIT_DEBUG_FORENSICS.md) |
| Manual test plans (TC-GR-*, TC-E1-*) | [../qa/test-plans/GUARDRAIL_TEST_PLAN.md](../../ENTERPRISE.md) |
| Shipped vs planned features | [IMPLEMENTATION_STATUS.md](../ce/README.md) |
| Extraction monitor — UI testing (#2) | [../commercial/labs/lab9-extraction-monitor/UI_TESTING.md](../../ENTERPRISE.md) · [tutorial/02 §7.4](../ce/tutorials/02-operator-console-ingest-and-audit.md#74-extraction-monitor-ui-lab-9) · [aliases](../shared/FEATURE_ID_ALIASES.md) |
| LangChain / Pinecone integration | [INTEGRATIONS.md](INTEGRATIONS.md) · [tutorial/03-extensions-troubleshooting-and-integrations.md#9-langchain-and-pinecone-integration-e7](../ce/tutorials/03-extensions-troubleshooting-and-integrations.md#9-langchain-and-pinecone-integration-e7) |
| Agent / MCP tool gateway (#7) | [../commercial/labs/lab1-mcp/IMPLEMENTATION_PLAN.md](../../ENTERPRISE.md) · [../commercial/labs/lab1-mcp/BACKLOG.md](../../ENTERPRISE.md) · [../commercial/labs/lab1-mcp/MCP_INTEGRATION_LAYERS.md](../../ENTERPRISE.md) · [tutorial/04-agent-mcp-tool-gateway-lab1.md](../ce/tutorials/04-agent-mcp-tool-gateway-lab1.md) · [../qa/test-plans/LAB1_TEST_PLAN.md](../../ENTERPRISE.md) |
| Polish sprint (Tiers 1-3) operator walkthrough | [POLISH_SPRINT.md](../ce/README.md) · [../qa/test-plans/E5_TEST_PLAN.md#polish-sprint--tier-1-e52-network--restore](../../ENTERPRISE.md#polish-sprint--tier-1-e52-network--restore) · [tutorial/02-operator-console-ingest-and-audit.md#52-policy-network-knobs-and-restore-from-backup-polish-tier-1](../ce/tutorials/02-operator-console-ingest-and-audit.md#52-policy-network-knobs-and-restore-from-backup-polish-tier-1) |
| Production deployment (Helm/K8s) | [../enterprise/e1/E1_5_HELM_K8S.md](../../ENTERPRISE.md) |
| Commercial / POC packaging | [../commercial/COMMERCIAL_SUMMARY.md](../../ENTERPRISE.md) |

## Quick reference

**Base URL:** `http://localhost:8090`

**Demo tokens:** `employee-demo-token` · `hr-demo-token` · `exec-demo-token` · `data-platform-demo-token` · `acme-employee-token` · `globex-employee-token` · `globex-hr-token`

**Admin keys (demo):** `rag-admin-demo-key` (full) · `rag-audit-reader-key` · `rag-audit-debug-key` · `rag-ingest-admin-key` · `rag-policy-admin-key` · `acme-ingest-admin` · `globex-audit-reader`

Persona scenes (UI + curl): [IDENTITY_DEMO_PLAYBOOK.md](../../ENTERPRISE.md)

**Key endpoints:**

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `POST /v1/query` | User bearer | Secured RAG query; optional `include_audit`, `audit_debug` |
| `GET /v1/documents` | User bearer | ACL-filtered document list |
| `POST /v1/ingest` | Admin bearer | Ingest with scan |
| `POST /v1/scan` | Admin bearer | Stateless input scan (E7.1 — shipped) |
| `GET /v1/tools` | User bearer | List registered tools + caller allow flags (#7) |
| `POST /v1/tools/invoke` | User bearer | Identity-bound tool gateway (#7) |
| `GET /audit/recent` | User bearer | Recent audit events |
| `GET /admin/policy-config` | Admin bearer | Read policy (secrets redacted) (EE Tier 2) |
| `GET /admin/policy-backups` | Admin bearer | List timestamped policy YAML backups (EE Tier 2) |
| `POST /admin/policy/restore-backup` | Admin bearer | Restore policy from backup (EE Tier 2) |
| `POST /admin/policy/preview-injection-patterns` | Admin bearer | Dry-run custom injection patterns (E5.9 Tier 2) (EE) |
| `POST /admin/reload-policy` | Admin bearer | Hot-reload YAML (CE Tier 1) |
| `GET /admin/auth/me` | Admin bearer | Roles, `tenant_scope`, `allowed_tenants` |
| `GET /admin/tenants` | Admin bearer | Tenant namespaces operator may access (EE Tier 2) |
| `GET /admin/challenges` | Admin bearer (`ingest_admin`) | CHALLENGE approval queue (EE Tier 2) |
| `GET /ui` | none | Operator console |
