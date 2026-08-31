# #7 — Agent / MCP tool gateway ACL

> **Which doc?** **Card** (this page) = behavior / policy · **Demo** = show it · **Learn** = teach it · **Lab** = GTM depth
>
> [Demo](../demos/07-tool-gateway.md) · [Learn](../learn/01-core-moats.md#7-agent--mcp-tool-gateway-acl) · [Lab](../../../ENTERPRISE.md) · [Tutorial](../tutorials/04-agent-mcp-tool-gateway-lab1.md)

| Field | Value |
|-------|-------|
| **Edition** | CE (MVP) |
| **Status** | Shipped |
| **Legacy alias** | Lab 1 |
| **Code** | `rag_protection_proxy/tools_gateway/` |
| **Tests** | `tests/test_tools_gateway.py` |
| **EE extension** | [#13 Tool registry](../../../ENTERPRISE.md) |

**Demo:** [../demos/07-tool-gateway.md](../demos/07-tool-gateway.md) · **Tutorial:** [T04 §11](../tutorials/04-agent-mcp-tool-gateway-lab1.md#part-11--agent--mcp-tool-gateway-lab-1) · **Console:** [T09 §I](../tutorials/09-implemented-features-walkthrough.md#part-i-tool-gateway-console-7-l1-202)

---

## What & why

RAG ACL stops wrong **documents** in context. Agent deployments fail on wrong **actions**: over-scoped service accounts, SQL exports, email exfil, tool-description injection at registry load.

The tool gateway applies **identity → policy → allow/deny → audit** on `POST /v1/tools/invoke` — the same pattern as retrieval ACL, before any backend side effect runs.

---

## How it works

```text
POST /v1/tools/invoke  { tool, arguments }
  → resolve_auth()                    # shared acl.py
  → registry lookup + description scan
  → group allowlist (tool_policy.yaml)
  → argument schema + size/pattern/domain guards
  → scan_input() on configured fields
  → risk score + CHALLENGE mode
  → backend handler (mock in MVP)
  → audit kind=tool_invoke
```

### Policy (`tool_policy.yaml`)

Loaded from `RAG_TOOL_POLICY_FILE` (default `./config/tool_policy.yaml`). Reload with `POST /admin/reload-policy`.

```yaml
defaults:
  challenge_threshold: 0.4
  block_threshold: 0.8
  challenge_mode: block

tools:
  run_sql:
    allowed_groups: [data-platform]
    blocked_patterns: ['DROP TABLE', 'DELETE FROM']
  send_email:
    allowed_groups: [hr, engineering, all-staff]
    blocked_domains: [personal-email.com]
```

### Invoke pipeline (first failure wins)

| Step | Check | Typical block |
|------|-------|---------------|
| 1 | Tool in registry | Unknown tool |
| 2 | Description injection (at load) | Tool blocked — description scan |
| 3 | Caller groups ∩ `allowed_groups` | Not authorized for tool |
| 4 | Pydantic argument schema | Invalid arguments |
| 5–7 | Size / patterns / domains | Argument policy |
| 8–9 | `scan_input()` + CHALLENGE | Guardrail block |
| 10 | Backend | Validation error |
| 11 | Success | `decision: allow` |

Every step writes one `tool_invoke` audit event (including blocks).

### How risk, severity, and thresholds work

After hard policy checks (unknown tool, ACL, argument size, blocked patterns/domains), the gateway runs the same input guardrail pipeline used for RAG queries on each configured string argument (`scan_arguments`, or all string fields if none are listed). That scan produces **findings**. Each finding carries a **severity** in `[0, 1]`. Severities are almost never computed dynamically: they are **fixed weights** chosen when the detection rule was authored.

Prompt-injection matches use per-pattern constants (for example instruction override near `0.85–0.9`, fake system prompt at `0.7`, base64 instructional payloads at `0.8`). URL threats score by host class (cloud metadata `1.0`, denied domain `0.9`, private IP `0.85`, not on allowlist `0.5`). Regex PII uses type weights (email/phone `0.3`, credit card `0.5`, SSN `0.7`). Secrets are high by design (private key `1.0`, common API keys `0.95`). Custom DLP patterns take `severity` from YAML (default `0.5` for `dlp`, `0.95` for `secret`). The only runtime formula is ML injection, when enabled: `min(0.95, 0.7 + similarity × 0.25)`.

Those findings collapse into one float via `aggregate_risk` in `guardrails/risk_scoring.py`: take the **maximum** severity across findings; if more than one finding has severity `≥ 0.7`, add `0.1 × (n_high − 1)` capped at `+0.15`; then clamp to `1.0`. An empty finding list yields risk `0.0`.

That aggregated **risk score** is what `defaults.challenge_threshold` and `defaults.block_threshold` compare against (not a raw ML score and not a single finding in isolation):

| Risk relative to tool-policy defaults | Verdict before `challenge_mode` |
|---------------------------------------|----------------------------------|
| `< challenge_threshold` (default `0.4`) | `ALLOW` |
| `≥ challenge_threshold` and `< block_threshold` (default `0.8`) | `CHALLENGE` |
| `≥ block_threshold` | `BLOCK` |

`challenge_mode` then remaps a raw `CHALLENGE`: `block` (fail-closed default) treats it as a hard block; `allow` holds the invoke in the operator queue without running the backend. Hard policy denials short-circuit earlier with fixed risk scores and never enter this threshold band.

### API

| Endpoint | Purpose |
|----------|---------|
| `GET /v1/tools` | List tools with per-caller `allowed` flag |
| `POST /v1/tools/invoke` | Enforced invocation |
| `GET /admin/tools/policy` | Operator policy view |
| `GET /admin/audit/events?kind=tool_invoke` | Audit feed |

### Demo tokens

| Token | Groups | `run_sql` | `send_email` |
|-------|--------|-----------|--------------|
| `employee-demo-token` | engineering, all-staff | Deny | Allow |
| `data-platform-demo-token` | data-platform, all-staff | Allow | Allow |
| `hr-demo-token` | hr, all-staff | Deny | Allow |

---

## Validate (smoke)

```bash
bash tools/docker_start.sh
export BASE=http://localhost:8090

curl -s -X POST "$BASE/v1/tools/invoke" \
  -H "Authorization: Bearer employee-demo-token" \
  -H "Content-Type: application/json" \
  -d '{"tool":"run_sql","arguments":{"query":"SELECT 1"}}' | jq '{blocked, decision, reason}'

cd rag-protection-proxy && pytest tests/test_tools_gateway.py -q
```

Full demo: [../demos/07-tool-gateway.md](../demos/07-tool-gateway.md).

---

## Gaps & non-claims

| In scope | Out of scope |
|----------|--------------|
| Per-invocation HTTP enforce + audit | Full MCP wire protocol server (stdio/SSE) |
| Mock backends + policy guards | Arbitrary third-party SaaS without adapters |
| Shared identity with RAG path | Multi-step agent orchestration policy |
| CE console: policy list, challenge review | EE registry CRUD → [#13](../../../ENTERPRISE.md) |

- **Does not replace IdP** — enforces allowlists on bearer token groups.
- **MCP layers:** HTTP invoke (Layer 1) is CE; native MCP transport is deferred — [MCP_INTEGRATION_LAYERS](../../../ENTERPRISE.md).
- **With vs without proxy:** plain-English comparison + diagrams — [MCP_WITH_WITHOUT_PROXY](../../../ENTERPRISE.md).

---

## Engineering reference

| Artifact | Path |
|----------|------|
| Router | `tools_gateway/router.py` |
| Policy | `tools_gateway/policy.py` · `config/tool_policy.yaml` |
| Registry | `tools_gateway/registry.py` |
| Backends | `tools_gateway/backends/` |
| Full architecture | [lab1 ARCHITECTURE](../../../ENTERPRISE.md) |
| With vs without proxy | [MCP_WITH_WITHOUT_PROXY](../../../ENTERPRISE.md) |
| Component reference | [TOOL_GATEWAY_COMPONENT_REFERENCE](../../../ENTERPRISE.md) |
| UI testing | [lab1 UI_TESTING](../../../ENTERPRISE.md) |
| Test plan | [LAB1_TEST_PLAN](../../../ENTERPRISE.md) |
| Example agent | [examples/agentic/mcp_tool_gateway/](../../../examples/agentic/mcp_tool_gateway/) |
