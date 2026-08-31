# Marifort Gate Operator Console

Vite + React monorepo for the operator UI. Serves the React console at `/ui`.

**Architecture (CE vs EE):** [docs/product/CONSOLE_CE_EE_UI_ARCHITECTURE.md](../docs/ce/README.md)  
**Plan:** [docs/product/CONSOLE_UI_REFACTOR.md](../docs/ce/README.md)  
**Build / start / debug (local + Docker):** [docs/product/CE_EE_BUILD_RUN_DEBUG.md](../docs/product/CE_EE_BUILD_RUN_DEBUG.md)

## Packages

| Package | Edition | Purpose |
|---------|---------|---------|
| `@rag-protection/console-core` | MIT (CE) | Theme, API client, auth context, layout shell, workspace registry |
| `@rag-protection/console-ce` | MIT | CE workspaces: Overview, Query Lab, Audit Log — [Lab 9 extraction UI testing](../ENTERPRISE.md) |
| `ee_ui` (private repo) | Commercial | EE workspaces — see `rag-protection-enterprise` |

## URLs (local dev)

| URL | What you get |
|-----|----------------|
| **http://localhost:8090/ui** | **React console** — served by the proxy |
| **http://localhost:5174** | Vite dev server (`npm run dev`) — hot reload; API proxied to `:8090` |

### How routing works

The proxy (`rag-protection-proxy`) serves:

- `GET /ui` → `ui/static/ce/index.html` (React CE shell) when built
- `GET /ui/static/ce/*` → CE JS/CSS bundle
- `GET /ui/static/ee/ee-ui.js` → EE workspace bundle (when enterprise package installed)

Verify the build:

```bash
curl -sI http://localhost:8090/ui | grep -i x-rag-protection-ui-build
# React: ce-v1
```

## Quick start (production-like on :8090)

### 1. Install CE + EE

```bash
cd /path/to/RAG_protection
source .venv/bin/activate
bash tools/dev_install_ee.sh
```

### 2. Build UI bundles

```bash
bash tools/build_ce.sh   # console-core + CE → ui/static/ce/
bash tools/build_ee.sh   # EE bundle → ee_ui/dist/ee-ui.js
```

Or manually:

```bash
cd console && npm install && npm run build
cd ../rag-protection-enterprise/ee_ui && npm install && npm run build
```

### 3. Start / restart the proxy

```bash
cd rag-protection-proxy
uvicorn rag_protection_proxy.app:app --host 0.0.0.0 --port 8090 --reload
```

### 4. Open the console

1. Browse to **http://localhost:8090/ui**
2. Hard-refresh (Cmd+Shift+R)
3. Set toolbar tokens:
   - **Proxy base URL:** `http://localhost:8090`
   - **Admin bearer token:** `rag-admin-demo-key`
   - **User bearer token:** `employee-demo-token` (or `hr-demo-token` for HR docs)
   - **Operator tenant:** `default`

### 5. EE workspaces

When `GET /health` reports `"enterprise_installed": true`, the shell lazy-loads `/ui/static/ee/ee-ui.js` and shows EE sidebar items:

| Workspace | API | Notes |
|-----------|-----|-------|
| Documents & Ingest | `GET /v1/documents`, `POST /v1/ingest`, `GET /admin/documents/{id}/inspect` | Corpus uses **user** token; ingest/inspect use **admin** + operator tenant |
| CHALLENGE queue | `GET /admin/challenges`, preview/inspect/approve/reject | Tier 2 — **404 without EE wheel** on proxy; response field is **`documents`** |
| Connectors | `GET /admin/connectors/status`, Drive/Notion ingest, SCIM sync, schedule sync, OAuth | Tier 3 — EE only |
| Policy Viewer/Admin | `GET /admin/policy-config`, `PATCH /admin/policy-knobs`, pattern preview | Tier 2 — **404 without EE wheel** on proxy |

**Layout:** CHALLENGE queue is a card at the top of **Documents & Ingest** (EE workspace).

## Quick start (Vite dev on :5174)

```bash
# Terminal 1 — proxy must be running on :8090
cd rag-protection-proxy && uvicorn rag_protection_proxy.app:app --port 8090 --reload

# Terminal 2 — CE dev server
cd console && npm run dev
```

Open **http://localhost:5174**. EE bundle is still loaded from the proxy at `/ui/static/ee/ee-ui.js` — rebuild `ee_ui` after EE pane changes.

### CE-only dev (hide EE panels)

`npm run dev` runs the CE shell, but it auto-detects Enterprise (`GET /health` → `enterprise_installed: true`) and lazy-loads the EE bundle, so EE workspaces appear. To debug **CE only**:

```bash
npm run dev:ce-only        # sets VITE_EE=off — CE workspaces only
```

Or toggle at runtime without restarting the dev server:

```text
http://localhost:5174/?ee=off       # CE-only
http://localhost:5174/              # CE + EE (default)
```

Both force `bootstrapEnterprise` off; the sidebar then shows only Overview, Query Lab, and Audit Log.

## Scripts

```bash
cd console
npm run dev          # CE shell on http://localhost:5174 (proxies to :8090)
npm run dev:ce-only  # CE shell with EE disabled (VITE_EE=off) — CE workspaces only
npm run dev:core     # core demo shell on http://localhost:5173
npm run build        # core library + CE app → rag-protection-proxy/.../ui/static/ce/
npm run typecheck
npm run test
```

```bash
cd rag-protection-enterprise/ee_ui
npm run build        # → rag_protection_enterprise/ee_ui/dist/ee-ui.js
npm run typecheck
npm run test         # Vitest + Testing Library — EE pane + registry component tests
npm run test:watch
```

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Sidebar missing Documents / CHALLENGE | Install EE (`tools/dev_install_ee.sh`); check `enterprise_installed` in `/health` |
| CHALLENGE queue always empty | Confirm `input.challenge_mode: allow` in policy; align **operator tenant** with quarantined docs; rebuild `ee_ui` after fixes |
| Ingest form missing | Open **Documents & Ingest** workspace (EE); scroll below corpus table |
| `ee-ui.js` 404 | Run `npm run build` in `rag-protection-enterprise/ee_ui` |
| EE panels show on the CE dev server | Expected — CE auto-loads EE. Use `npm run dev:ce-only` or `?ee=off` for CE-only |
| Extraction monitor — Extraction Watch | Policy Viewer/Admin → **Edit → Advanced Features → Extraction** (EE); CE fallback: Query Lab + Audit Log | [UI_TESTING.md](../ENTERPRISE.md) |
| Canary tripwire — Recent Triggers | Policy Viewer/Admin → **Edit → Advanced Features → Canary** (EE); CE fallback: Audit Log `canary_triggered` | [UI_TESTING.md](../ENTERPRISE.md) |
| Audit Log empty after extraction scrape | Enable `extraction:` via **Extraction** knobs or `data/policy.yaml` + **Reload Policy**; use vocabulary-aligned queries in Query Lab | [UI_TESTING.md §Troubleshooting](../ENTERPRISE.md#troubleshooting-ui) |

## Recommended next console surfaces (moats)

Runtime for core moats #1–#11 is shipped; console coverage is uneven. Preferred order when a POC needs `/ui` evidence:

1. ~~Retrieval explainability (#11) in Query Lab~~ **shipped** — toggle + table; Audit drawer; Policy Retrieval knobs  
2. ~~Audit integrity verify (#9)~~ **shipped** — Verify chain badge; Policy Audit knobs  
3. ~~Citation hard-gate UX (#8)~~ **shipped** — Ungrounded demo + unsupported highlight; Policy Thresholds knobs  
4. ~~Permission drift panel (#4)~~ **shipped** — Connectors drift panel + Policy Drift knobs  
5. ~~Tool gateway read-only panel (#7)~~ **shipped** — CE **Tool Gateway** + Audit `tool_invoke` chips  
6. ~~Exfil correlation strip (#2+#3)~~ **shipped** — Overview + Audit pair signal (`RAG-Exfil-HighConfidence`) — [UI_TESTING](../ENTERPRISE.md) · `bash tools/validate_ui_build_order.sh --item 6`
7. EE tool CHALLENGE queue + registry hot-edit — **deferred** (pilot / EE SKU triggers)

Full table + freeze rules: [NEXT_STEPS § Core moats — operator UI](../docs/ce/README.md#core-moats--operator-ui-shipped--recommended). Test plan: [UI_BUILD_ORDER_TEST_PLAN](../ENTERPRISE.md).

## Recommended next console surfaces (procurement #12–#18)

Runtime for #12–#14 / #17 is shipped. Remaining `/ui` gaps for GRC / regulated POC (most of #12–#18 console now done):

1. ~~**Evidence pack builder (#14)**~~ **shipped** — Policy → **Evidence Pack** — [UI_TESTING](../ENTERPRISE.md) · `bash tools/validate_procurement_ui.sh --item 1`
2. ~~**DLP pack enable (#17)**~~ **shipped** — Pattern Lab / Injection & DLP **Enable HIPAA / PCI / GDPR** — [UI_TESTING](../ENTERPRISE.md) · `bash tools/validate_procurement_ui.sh --item 2`
3. ~~**Quarantine deepen (#15)**~~ **shipped** — [UI_TESTING](../ENTERPRISE.md) · `bash tools/validate_procurement_ui.sh --item 3`
4. ~~**Tool registry CRUD (#13)**~~ **shipped** (L1-403) — [lab1 UI_TESTING](../ENTERPRISE.md); L1-201 CHALLENGE deferred
5. ~~**ACL sync polish (#12)**~~ **shipped** — Audit `acl_sync` chip + Connectors last ACL-only delta — [lab4 UI_TESTING](../ENTERPRISE.md) · `bash tools/validate_procurement_ui.sh --item 5`

Skip until runtime: #16 ReBAC. **#18 LLM egress routing shipped** (Audit `llm_routed` chip only — no traffic dashboard). **#13 L1-201 CHALLENGE shipped**.

Full tables: [NEXT_STEPS § Enterprise procurement UI](../docs/ce/README.md#enterprise-procurement--operator-ui-recommended) · [02-enterprise-procurement.md](../ENTERPRISE.md#operator-console-note-1218).

## Workspace plugin API

```ts
import { registerWorkspace } from '@rag-protection/console-core';

registerWorkspace({
  id: 'query',
  label: 'Query Lab',
  edition: 'ce',
  component: QueryLabPane,
});
```

EE bundle registers workspaces with `edition: 'ee'` at load time via `registerEeWorkspaces()`.
