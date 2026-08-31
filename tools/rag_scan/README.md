# rag-scan — pre-production RAG config scanner (Lab 2)

Shift-left CI gate for RAG deployments. `rag-scan` imports the **same policy
loaders** the RAG Protection gateway uses at runtime
(`rag_protection_proxy.config`), so a failing scan provably means the running
gateway would have accepted a dangerous configuration.

> Lab reference: [AI_SECURITY_COMPETENCY_LABS.md § Lab 2](../../ENTERPRISE.md#lab-2--rag-config-scanner-shift-left-3-weeks)
> · Tier reference: [SOLOPRENEUR § #6](../../ENTERPRISE.md#6-pre-production-rag-config-scanner-shift-left)

## Why

Most real breaches in customer-built RAG are boring misconfigurations: a payroll
collection tagged `all-staff`, demo tokens left in prod, connectors that fail
open, a default admin key in git. Platform teams trust **CI failures** more than
runtime promises.

## Usage

Use the `tools/rag-scan` wrapper — it works from any directory (it puts `tools/`
on `PYTHONPATH` and prefers the repo `.venv`), so no install or `cd` is needed:

```bash
# Validate that policy + ACL YAML load at all (exit 2 on invalid)
tools/rag-scan validate \
  --policy rag-protection-proxy/config/policy.yaml \
  --acl rag-protection-proxy/config/acl_policy.prod.yaml

# Scan the PRODUCTION ACL (what prod deploys + what CI gates on)
tools/rag-scan check --env prod \
  --acl rag-protection-proxy/config/acl_policy.prod.yaml

# Explicit paths + JUnit output for CI panels
tools/rag-scan check \
  --env prod \
  --policy rag-protection-proxy/config/policy.yaml \
  --acl rag-protection-proxy/config/acl_policy.prod.yaml \
  --sample-docs rag-protection-proxy/config/sample_documents.json \
  --format junit --output rag-scan.xml

# Optional live vector probe (VEC001)
tools/rag-scan check --env prod --qdrant http://localhost:6333
```

> Without the wrapper, invoke the module from `tools/`
> (`cd tools && python -m rag_scan ...`) or add `tools/` to `PYTHONPATH`.

### Install as a command (`rag-scan`)

The scanner is also a standalone package with a `rag-scan` console script:

```bash
pip install -e tools/rag_scan          # editable, dev
pip install tools/rag_scan             # build + install
pip install -e 'tools/rag_scan[vector]'  # + qdrant-client for VEC001

rag-scan check --env prod --acl rag-protection-proxy/config/acl_policy.prod.yaml
```

`rag-scan` imports the gateway's config loaders (`rag_protection_proxy.config`).
That package is not on PyPI — when you run from a checkout the scanner adds the
sibling `rag-protection-proxy/` to `sys.path` automatically; for an out-of-tree
install, `pip install -e rag-protection-proxy` as well.

### Baseline (brownfield repos)

Adopt the CI gate on a repo with pre-existing findings without going red on day
one. Snapshot the current findings, commit the file, and suppress exactly those
on later runs — any **new or changed** finding still fails:

```bash
# 1. Record today's findings as the accepted baseline (exits 0).
tools/rag-scan check --env prod --acl config/acl_policy.prod.yaml \
  --write-baseline .rag-scan-baseline.json

# 2. In CI, gate against it. Suppressed findings show in the summary.
tools/rag-scan check --env prod --acl config/acl_policy.prod.yaml \
  --baseline .rag-scan-baseline.json
```

### Dev vs. prod ACL

There are two ACL files on purpose:

| File | Used by | Demo creds? |
|------|---------|-------------|
| `config/acl_policy.yaml` | local demo, `smoke_rag_proxy.sh`, the test suite | **yes** (demo tokens + demo admin keys) |
| `config/acl_policy.prod.yaml` | production deploys (Helm `RAG_ACL_FILE`) and this scanner's prod gate | **no** (OIDC + secret-managed admin key) |

So `tools/rag-scan check --env prod` against the **default** ACL
(`acl_policy.yaml`) will *correctly* report `ACL001` + `SEC001` — that demo file
is unsafe for prod by design. Always point `--acl` at `acl_policy.prod.yaml` for
the production posture check (this is what CI does).

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | Clean — no findings at or above `--severity` (default `critical`) |
| `1` | Findings at or above the fail severity |
| `2` | Configuration could not be loaded / validated |

### Output formats

`--format text` (default, human-readable), `junit` (GitHub/GitLab test panels),
`sarif` (GitHub code scanning tab).

## Rule catalog

| Rule | Severity | Condition |
|------|----------|-----------|
| **ACL001** | critical | Demo bearer tokens present in ACL file when `--env prod` |
| **ACL002** | critical | `--sample-docs` entry whose `metadata.classification` contains a confidential marker (`confidential`, `secret`, `restricted`, `pii`, `phi`, `pci`) also grants a broad group (`all-staff`, `public`, `*`, `everyone`, `all`). Does **not** inspect live Qdrant. Non-matching labels (e.g. `public`, `internal-engineering`) are not treated as confidential. |
| **ACL003** | warning | `default_groups` contains `*` (`all-staff` as baseline is allowed) |
| **POL001** | warning | `input.block_threshold` below floor (0.5) |
| **POL002** | critical | Connectors enabled while `unmapped_permissions` fails open (not `deny`) |
| **POL003** | warning | Injection detection weakened — `ml_injection_enabled: false` or built-in `injection_categories` toggled off |
| **CON001** | warning | Connector sync job missing `group_map` (ACL mapping) |
| **SEC001** | critical | Shipped default admin key present in ACL when `--env prod` |
| **SEC002** | warning | No OIDC and no `jwt_secret` configured for prod (no IdP auth) |
| **VEC001** | critical | (Live probe, needs `--qdrant`) sampled vector payloads **missing** `allowed_groups`. Does **not** score classification or over-broad group membership. |

## Testing

```bash
python -m pytest tools/rag_scan/tests -q
```

Golden fixtures live in `tools/rag_scan/tests/fixtures/` (`bad_*` must fire
rules; `good_*` must be clean).

## CI integration

An active PR gate lives at
[`.github/workflows/rag-scan.yml`](../../docs/ce/README.md). It runs
on changes to `rag-protection-proxy/config/**` or the scanner, validates both
ACL files load, and fails the PR on any **critical** finding in
`acl_policy.prod.yaml`.

## Notes / boundaries

- Static checks need no running stack; **VEC001** requires `--qdrant` and
  `qdrant-client`.
- **ACL002 vs VEC001:** confidential detection is substring markers on sample-doc
  `classification` only. The Qdrant probe never classifies documents; it only
  flags missing `allowed_groups` on sampled payloads.
- This is a **Lab 2 scaffold** (competency lab / OSS lead-gen asset), not yet a
  packaged EE SKU. Industry policy packs (HIPAA/PCI metadata patterns) are the
  EE upsell — out of scope here.
