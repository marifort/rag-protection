# mcp-lint — MCP manifest / tool-description linter (A2)

Statically lint MCP server **`tools/list`** manifests for **tool-description
injection** and **over-broad scopes** *before* an agent ever connects. `mcp-lint`
reuses the shipped **`PromptInjectionScanner`** (same as the Lab 1 tool gateway)
and **`McpStreamableHttpClient`** for live scans.

> Spec: [ADDITIONAL_OPPORTUNITIES_SPECS.md § A2](../../ENTERPRISE.md#a2--mcp-manifest--tool-description-linter-oss)
> · Tier: [SOLOPRENEUR § A2](../../ENTERPRISE.md#a2--mcp-manifest--tool-description-linter-oss)
> · Runtime enforcement: [Lab 1 MCP gateway](../../ENTERPRISE.md)
> · Lab deliverables: [SPEC](../../ENTERPRISE.md) · [DEMO_SCRIPT](../../ENTERPRISE.md)

This is an **OSS lead-gen / shift-left CI gate**, not runtime enforcement. Pair
it with the Lab 1 gateway: *lint the manifest (A2) → enforce at invoke (Lab 1)*.

---

## Goal

**The pain:** MCP servers publish `tools/list` metadata the LLM reads as implicit
instructions. Poisoned descriptions ("ignore previous instructions…") and
over-broad tool scopes are a real attack surface — and most teams have **no CI
gate** on MCP declarations.

**The opportunity (A2):** repackage the **already-shipped** `PromptInjectionScanner`
and `McpStreamableHttpClient` as a standalone OSS linter. A2 is the **MCP
declaration-side** counterpart to [rag-scan (Lab 2)](../rag_scan/README.md), which
grades RAG *config*.

| Property | What it means for A2 |
|----------|-------------------|
| **Thin wrapper** | ~10–15 h build; MCP001/MCP005 use the gateway's injection scanner |
| **Pre-incorporation** | Publishable OSS before a legal entity; feeds outbound on MCP adoption |
| **Beside the product** | Static CI lint — runtime `description_blocked` is Lab 1's job |
| **Natural upgrade path** | Failed CI → Lab 1 gateway POC or assessment SKU |

**What A2 is not:** runtime invoke enforcement, argument payload scanning, or a
guarantee that the MCP server implementation matches its declaration.

---

## Architecture

See [Lab 7 SPEC](../../ENTERPRISE.md) for the full module map and CLI contract.

---

## Design

### Rule engine (MCP001–MCP005)

| Rule | Severity | What it checks |
|------|----------|----------------|
| MCP001 | critical | `PromptInjectionScanner` on `tool.description` |
| MCP002 | warning | URLs/emails in description (skipped when MCP001 fired) |
| MCP003 | warning | Destructive/write scope without schema constraints |
| MCP004 | info | Missing or permissive `inputSchema` |
| MCP005 | warning | Hidden chars / instructional HTML comments |

### Inputs

| Mode | Flag | Accepts |
|------|------|---------|
| Static | `--manifest PATH` | `{tools:[]}`, bare array, or JSON-RPC wrapper |
| Live | `--url URL` | MCP Streamable HTTP (`initialize` → `tools/list`) |

---

## Contents

- [Goal](#goal)
- [How it works](#how-it-works)
- [Architecture](#architecture)
- [Design](#design)
- [Install](#install)
- [Usage](#usage)
- [Rule catalog](#rule-catalog)
- [Output formats](#output-formats)
- [Exit codes](#exit-codes)
- [CI integration](#ci-integration)
- [Project layout](#project-layout)
- [Lab artifacts](#lab-artifacts)
- [Testing](#testing)
- [Boundaries](#boundaries)

---

## How it works

```text
mcp-lint scan --manifest tools.json        # static (saved tools/list JSON)
mcp-lint scan --url http://mcp:8000/mcp    # live (MCP Streamable HTTP)
  │
  ▼
┌──────────────────────────────────────────────────────────────┐
│ mcp_lint                                                      │
│  fetch.load_manifest() / fetch_live()   → List[McpTool]      │
│  linter.lint_tools()                                            │
│    ├─ PromptInjectionScanner on each description  → MCP001/005│
│    ├─ external destination heuristics             → MCP002    │
│    ├─ destructive scope heuristics                → MCP003    │
│    └─ input schema checks                         → MCP004    │
│  reporters.render()  → text | junit | sarif                   │
└──────────────────────────────────────────────────────────────┘
  exit 0 clean | 1 finding | 2 unreachable/invalid manifest
```

---

## Install

Fastest path — **wrapper script** (no install, works from any directory):

```bash
tools/mcp-lint scan --manifest tools/mcp_lint/examples/good_tools.json
```

To install the **`mcp-lint` console script**:

```bash
pip install -e tools/mcp_lint
mcp-lint scan --manifest tools/mcp_lint/examples/good_tools.json
```

`mcp-lint` → `rag_protection_proxy.scanners` + `mcp_shim`. From a checkout the
proxy resolves automatically via `_bootstrap`; for an out-of-tree install also
`pip install -e rag-protection-proxy`.

**Requirements:** Python ≥ 3.11, `httpx` (for `--url` live mode).

---

## Usage

```bash
# Static manifest (saved tools/list output)
tools/mcp-lint scan --manifest tools/mcp_lint/examples/good_tools.json

# Live MCP server (must be reachable on the host — see below)
tools/mcp-lint scan --url http://localhost:8000/mcp

# CI gate — fail on warning or above (default)
tools/mcp-lint scan --manifest tools.json --format junit --output mcp-lint.xml

# SARIF for GitHub code scanning
tools/mcp-lint scan --manifest tools.json --format sarif --output mcp-lint.sarif

# Only fail on critical injection findings
tools/mcp-lint scan --manifest tools.json --severity critical
```

<a id="live-mode-url"></a>
### Live mode (`--url`)

`--url` talks Streamable HTTP (`initialize` → `tools/list`) to a **host-reachable**
MCP endpoint. If nothing is listening you get:

```text
[ERROR] MCP server unreachable or invalid: MCP transport failed: [Errno 61] Connection refused
```

**Do not expect `bash tools/docker_start.sh --mcp-tools` to fix this.** That overlay
runs `mcp-filesystem` on the internal `mcp-backends` network only (no host port
publish — TC-L1-N02). The gateway can reach `http://mcp-filesystem:8000/mcp`;
your laptop cannot reach `http://localhost:8000/mcp`.

For a local live scan, publish the Lab 1 filesystem MCP server on port 8000:

```bash
docker compose -f compose.yml -f compose.mcp-tools.yml build mcp-filesystem

docker run --rm -p 8000:8000 \
  -v "$PWD/examples/agentic/mcp_tool_gateway/demo_workspace:/workspace:ro" \
  rag-protection-mcp-filesystem:latest \
  --port 8000 --outputTransport streamableHttp --stdio "mcp-server-filesystem /workspace"
```

Then in another terminal:

```bash
tools/mcp-lint scan --url http://localhost:8000/mcp
```

Static `--manifest` is enough for the Lab 7 / #27 demo; live mode is optional.

### What is `tools.json`?

<a id="what-is-toolsjson"></a>

`tools.json` is a **saved MCP tool manifest** — a snapshot of what an MCP server returns from `tools/list` (tool names, descriptions, JSON schemas). Docs and CI examples often use that filename; it is a **convention**, not a single system-wide catalog shipped by the product.

| Source | What it is |
|--------|------------|
| Live MCP server | Canonical catalog via `tools/list` (e.g. `mcp-server-filesystem` may list ~14 tools) |
| Repo-root `tools.json` | Optional local dump (often untracked) for offline `mcp-lint scan --manifest tools.json` |
| [examples/good_tools.json](./examples/good_tools.json) / [examples/bad_tools.json](./examples/bad_tools.json) | Fixture manifests for demos and tests |
| `tool_policy.yaml` / `tool_policy.mcp.yaml` | **Not** MCP manifests — gateway allowlists (which tools the proxy exposes and enforces) |

The Lab 1 gateway does **not** load `tools.json`. It loads `RAG_TOOL_POLICY_FILE` and only offers tools registered there (Layer 2 maps gateway `read_file` → MCP `read_text_file` even when the filesystem server advertises many more tools). See [TOOL_GATEWAY_COMPONENT_REFERENCE.md](../../ENTERPRISE.md#mcp-manifests-toolsjson-vs-tool-policy).

### Saving a manifest from a running server

Prefer live lint (handles Streamable HTTP Accept headers + `initialize` session):

```bash
tools/mcp-lint scan --url http://localhost:8000/mcp
```

A bare `tools/list` POST fails without the Streamable HTTP Accept header:

```text
Not Acceptable: Client must accept both application/json and text/event-stream
```

To capture `tools/list` with curl, complete the handshake (Accept + session):

```bash
# 1) initialize — capture Mcp-Session-Id
SESSION=$(curl -si -X POST http://localhost:8000/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"curl","version":"0"}}}' \
  | awk -F': ' 'tolower($1)=="mcp-session-id"{gsub(/\r/,"",$2); print $2; exit}')

# 2) notifications/initialized
curl -s -X POST http://localhost:8000/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H "Mcp-Session-Id: $SESSION" \
  -H 'MCP-Protocol-Version: 2024-11-05' \
  -d '{"jsonrpc":"2.0","method":"notifications/initialized","params":{}}' >/dev/null

# 3) tools/list → tools.json (JSON body or SSE data: line)
curl -s -X POST http://localhost:8000/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H "Mcp-Session-Id: $SESSION" \
  -H 'MCP-Protocol-Version: 2024-11-05' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
  | tee /tmp/mcp-tools-raw.txt \
  | (grep -E '^data: ' | sed 's/^data: //' || cat) \
  | jq '.result // .' > tools.json
```

Then lint offline: `tools/mcp-lint scan --manifest tools.json`.

---

## Rule catalog

| Rule | Severity | Condition |
|------|----------|-----------|
| **MCP001** | critical | Tool description triggers `PromptInjectionScanner` (instruction override, exfiltration directive, …) |
| **MCP002** | warning | Description references external destinations (URLs, emails) not already flagged as injection |
| **MCP003** | warning | Tool name/schema implies destructive/write scope without input constraints |
| **MCP004** | info | Missing or unconstrained `inputSchema` |
| **MCP005** | warning | Hidden/zero-width characters or instructional HTML comments in description |

Finding categories reuse `BUILTIN_INJECTION_CATEGORIES` from the runtime so
reports speak the same language as the gateway.

---

## Output formats

| Format | Use case |
|--------|----------|
| `text` | Local dev (default) |
| `junit` | CI test panels (GitHub Checks, GitLab) |
| `sarif` | GitHub code scanning upload |

---

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Clean — no findings at or above `--severity` |
| `1` | One or more findings at or above `--severity` (default: `warning`) |
| `2` | Manifest could not be loaded or MCP server unreachable |

---

## CI integration

```yaml
# .github/workflows/mcp-lint.yml
- name: Lint MCP tool manifest
  run: |
    pip install -e tools/mcp_lint
    mcp-lint scan \
      --manifest path/to/tools.json \
      --format junit \
      --output mcp-lint.xml \
      --severity warning
- name: Publish results
  uses: EnricoMi/publish-unit-test-result-action@v2
  if: always()
  with:
    files: mcp-lint.xml
```

---

## Project layout

```text
tools/mcp_lint/
  cli.py           # mcp-lint scan --manifest | --url
  fetch.py         # static manifest + live MCP fetch
  linter.py        # MCP001–MCP005 rules
  models.py        # McpTool, Finding, LintReport
  reporters/       # text, junit, sarif
  examples/        # good_tools.json, bad_tools.json
  tests/           # pytest suite
tools/mcp-lint     # wrapper script (puts tools/ on PYTHONPATH)
```

---

## Lab artifacts

Buyer-facing deliverables live under
[`docs/commercial/labs/lab7-mcp-lint/`](../../ENTERPRISE.md):

| Doc | Purpose |
|-----|---------|
| [SPEC.md](../../ENTERPRISE.md) | Goal, architecture, module map, CLI contract, implementation status |
| [CONTROL_MAP.md](../../ENTERPRISE.md) | Threat → control → residual + OWASP mapping |
| [BOUNDARY.md](../../ENTERPRISE.md) | Out-of-scope statements + CE/EE line |
| [DEMO_SCRIPT.md](../../ENTERPRISE.md) | ~5 min runnable demo (shipped examples) |
| [TALK_TRACK.md](../../ENTERPRISE.md) | 5–8 min buyer/engineer talk track |

---

## Testing

```bash
pytest tools/mcp_lint/tests -q
```

---

## Boundaries

- **Static declaration lint only** — checks what the MCP server *advertises*, not
  runtime argument payloads or tool behavior.
- **Heuristic scope rules (MCP003/004)** — flag over-broad declarations for human
  review; they are not a substitute for server-side authorization.
- **Injection detection (MCP001)** — same regex/heuristic scanner as the gateway;
  novel semantic attacks may need ML/runtime enforcement (Lab 1).
- **Not legal advice** — indicative security hygiene, not a certification.

**Upgrade path:** [Lab 1 MCP tool gateway](../../ENTERPRISE.md) for
runtime description blocking and invoke-time policy enforcement.
