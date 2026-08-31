# Tutorial 06 — #19 Grounding · #20 Posture · #23 InjBench · #27 MCP lint · #29 ACL backfill

**Catalog IDs:** [#19](../../shared/FEATURE_ID_ALIASES.md), [#20](../../shared/FEATURE_ID_ALIASES.md), [#23](../../shared/FEATURE_ID_ALIASES.md), [#27](../../shared/FEATURE_ID_ALIASES.md), [#29](../../shared/FEATURE_ID_ALIASES.md)

> **Lab / A aliases:** Lab 6 / A6 → **#19** · Lab 8 / A3 → **#20** · A7 → **#23** · Lab 7 / A2 → **#27** · A4 → **#29**. See [FEATURE_ID_ALIASES.md](../../shared/FEATURE_ID_ALIASES.md).

## Part 16 — #19 Grounding / hallucination checker (`rag-ground`)

This lab exposes the shipped output guardrail (`verify_citations`) as a batch/CI tool so you can measure grounding and prompt-leak risk on an eval set before deploy.

**Demo script:** [../../commercial/labs/lab6-grounding/DEMO_SCRIPT.md](../../../ENTERPRISE.md) · **Verdict walkthrough (full prose):** [../../commercial/labs/lab6-grounding/VERDICT_WALKTHROUGH.md](../../../ENTERPRISE.md) · **CI workflow:** `.github/workflows/rag-ground.yml`

### 16.0 One-time setup (off camera)

```bash
tools/rag-ground --version          # rag-ground 0.1.0
```

Shipped example files:

| File | Role |
|------|------|
| `tools/rag_ground/examples/answer.txt` | Single-mode demo: 3/6 sentences grounded |
| `tools/rag_ground/examples/sources.json` | Three KB chunks (uptime, encryption, free tier) |
| `tools/rag_ground/examples/eval.jsonl` | Batch: grounded + hallucination + leak rows |

---

### 16.1 Single answer: spot the hallucination (60 sec)

```bash
tools/rag-ground check \
  --answer tools/rag_ground/examples/answer.txt \
  --sources tools/rag_ground/examples/sources.json
echo "exit=$?"
```

**Expected:** `Verdict: UNGROUNDED` and `exit 1` (three fabricated sentences).

**Why:** [Verdict walkthrough § 1](../../../ENTERPRISE.md#1-single-answer--verdict-ungrounded) — 3/6 sentences overlap the KB chunks; coverage 0.50 fails threshold 0.75. Brand-token false support: [edge case](../../../ENTERPRISE.md#edge-case--short-fabrication-that-shares-a-brand-token).

---

### 16.2 Batch eval set: pass rate as the CI metric (60 sec)

```bash
tools/rag-ground check --jsonl tools/rag_ground/examples/eval.jsonl
echo "exit=$?"
```

**Expected:** pass rate `1/3 (0.33)` -> gate fail -> `exit 1`.

**Why:** [Verdict walkthrough § 2](../../../ENTERPRISE.md#2-batch-mode--pass-rate-and---min-pass-rate) — only `ex-grounded` passes; default `--min-pass-rate 1.0` fails the set.

---

### 16.3 Relax vs tighten the gate (45 sec)

```bash
# Loosen threshold - single answer passes at 0.5
tools/rag-ground check \
  --answer tools/rag_ground/examples/answer.txt \
  --sources tools/rag_ground/examples/sources.json \
  --threshold 0.5
echo "exit=$?"    # 0

# Loosen batch gate - 1/3 pass rate meets a 0.3 floor
tools/rag-ground check \
  --jsonl tools/rag_ground/examples/eval.jsonl \
  --min-pass-rate 0.3
echo "exit=$?"    # 0
```

**Why the relaxed batch gate passes:** [Verdict walkthrough § 2](../../../ENTERPRISE.md#2-batch-mode--pass-rate-and---min-pass-rate) — pass rate 0.33 meets `--min-pass-rate 0.3` even though two rows still fail individually.

---

### 16.4 Machine-readable output for CI (30 sec)

```bash
tools/rag-ground check \
  --jsonl tools/rag_ground/examples/eval.jsonl \
  --format junit --output /tmp/grounding.xml
head -20 /tmp/grounding.xml
```

**Why this XML:** [Verdict walkthrough § 3](../../../ENTERPRISE.md#3-junit-xml--machine-readable-ci-report) — three testcases, two failures (`ex-hallucination`, `ex-leak`).

---

### 16.5 Pair with config grading (15 sec)

```bash
# #20 grades the config; #19 grades the answers
tools/rag-score --env prod \
  --acl rag-protection-proxy/config/acl_policy.prod.yaml \
  --format markdown | head -5
```

---

### 16.6 Where CI plugs in (15 sec)

Show the live workflow: `.github/workflows/rag-ground.yml` (runs the 50-test suite and uploads a JUnit artifact).

---

## Part 17 — #27 MCP manifest linter (`mcp-lint`)

This lab catches **tool description injection** and other MCP declaration-level hazards *before* an agent connects.

**Demo script:** [../../commercial/labs/lab7-mcp-lint/DEMO_SCRIPT.md](../../../ENTERPRISE.md)

### 17.0 Prereqs

- Repo checkout
- Python >= 3.11 (repo `.venv` preferred)
- Duration: ~5 min
- Artifacts: `tools/mcp_lint/examples/*.json`

---

### 17.1 Clean manifest (30 sec)

```bash
tools/mcp-lint scan --manifest tools/mcp_lint/examples/good_tools.json
```

**Say:** Two tools, no findings - exit 0.

---

### 17.2 Poisoned manifest (2 min)

```bash
tools/mcp-lint scan --manifest tools/mcp_lint/examples/bad_tools.json
```

**Say:** Watch MCP001 fire on an instruction override in `send_email`.

**Expect:**
- `[CRIT] MCP001` on `send_email` (instruction override)
- `[WARN] MCP003` on `delete_file` (destructive scope, no constraints)
- `[WARN] MCP002` on `fetch_url` (external URL/email)
- `[WARN] MCP005` on `run_shell` (HTML comment payload)
- `[INFO] MCP004` on `legacy_tool` (no schema)

Exit `1`.

---

### 17.3 CI severity gate (1 min)

```bash
# Injection-only gate - still fails on MCP001
tools/mcp-lint scan --manifest tools/mcp_lint/examples/bad_tools.json --severity critical

# Info-only findings would pass a critical gate
tools/mcp-lint scan --manifest tools/mcp_lint/examples/bad_tools.json --severity warning
```

---

### 17.4 JUnit for CI panel (optional, 1 min)

```bash
tools/mcp-lint scan \
  --manifest tools/mcp_lint/examples/bad_tools.json \
  --format junit \
  --output /tmp/mcp-lint.xml
head -20 /tmp/mcp-lint.xml
```

---

### 17.5 Live mode (optional - needs running MCP server)

```bash
# Requires a Streamable HTTP MCP endpoint, e.g. compose stack from #7
tools/mcp-lint scan --url http://localhost:8000/mcp
```

---

### 17.6 CI workflow note

This lab is designed for a CI step that runs `mcp-lint scan --manifest ...` and publishes a JUnit artifact. The `tools/mcp_lint/README.md` shows an example using `mcp-lint.xml`; the corresponding workflow file is not present in `.github/workflows/` in this repo snapshot.

---

## Part 18 — #20 RAG posture scorecard (`rag-score`)

This lab turns the config findings from the #6 scanner into a **shareable A-F grade card** (and an OWASP LLM map) so prospects can self-qualify before a sales call.

**Demo script:** [../../commercial/labs/lab8-posture-scorecard/DEMO_SCRIPT.md](../../../ENTERPRISE.md) · **Full prose walkthrough:** [../../commercial/labs/lab8-posture-scorecard/POSTURE_WALKTHROUGH.md](../../../ENTERPRISE.md)

### 18.0 Prereqs

- Repo checkout
- Python >= 3.11 (repo `.venv` preferred)
- Duration: ~5 min

---

### 18.1 Clean production posture (1 min)

```bash
tools/rag-score --env prod \
  --acl rag-protection-proxy/config/acl_policy.prod.yaml
```

**Expected:** `Grade: A (100/100)` and `exit 0`.

---

### 18.2 Demo ACL fails prod posture (2 min)

```bash
tools/rag-score --env prod \
  --acl rag-protection-proxy/config/acl_policy.yaml \
  --sample-docs rag-protection-proxy/config/sample_documents.json
```

**Expected:** grade `F` (and a score drop), because the file is unsafe for prod by design.

---

### 18.3 Opt-in CI gate (1 min)

```bash
tools/rag-score --env prod \
  --acl rag-protection-proxy/config/acl_policy.yaml \
  --fail-under B
echo "exit code: $?"
```

**Expected:** `exit 1` if grade is worse than `B`.

---

### 18.4 Shareable HTML card (1 min)

```bash
tools/rag-score --env prod \
  --acl rag-protection-proxy/config/acl_policy.yaml \
  --format html --output /tmp/posture.html

open /tmp/posture.html   # macOS; xdg-open on Linux
```

---

### 18.5 CI workflow note

There is no dedicated `rag-score.yml` workflow in this repo snapshot. Instead:
- use `--fail-under` in your own CI step (opt-in, grade threshold)
- for a hard shift-left gate on critical findings, use `rag-scan.yml` directly (scanner + critical misconfig enforcement)

---

## Part 19 — #23 Prompt-injection benchmark (`rag-injbench`)

**#23** packages a versioned prompt-injection corpus plus a regression harness so you can answer: "Is injection defense getting better or worse?" - and make that answer enforceable in CI.

This part mirrors the shipped workflow `.github/workflows/rag-injbench.yml`.

**Reference:** [../A7_INJBENCH_AND_CI.md](../README.md) · **Tool:** [../../../tools/inj_bench/README.md](../../../tools/inj_bench/README.md) · **Lab demo:** [../../commercial/labs/a7-injbench/DEMO_SCRIPT.md](../../../ENTERPRISE.md)

### 19.1 CI workflow (what `rag-injbench.yml` gates)

It runs when relevant paths change (tool/corpus/scanners/workflow):
- runs unit tests for `tools/inj_bench`
- runs the baseline regression gate using `tools/rag-injbench run --target builtin --baseline ...`
- uploads a JUnit artifact (`rag-injbench.xml`) so GitHub checks can show results

### 19.2 Step-by-step demo commands (run locally)

#### A) Score shipped scanners (full CE corpus)

```bash
tools/rag-injbench run --target builtin
```

#### B) OSS public sampler only (~15 payloads)

```bash
tools/rag-injbench run --published-only
```

#### C) Reports (JSON / JUnit)

```bash
tools/rag-injbench run --format json
tools/rag-injbench run --format junit --output injbench.xml
```

#### D) Regression gate (baseline diff)

```bash
tools/rag-injbench run \
  --target builtin \
  --baseline tools/inj_bench/baseline/builtin.json
```

**Interpretation:**
- exit `0` at/above baseline
- exit `1` on regression / baseline failure
- exit `2` on invalid corpus/baseline/target

#### E) Refresh baseline after intentional scanner improvements

```bash
tools/rag-injbench run \
  --target builtin \
  --write-baseline tools/inj_bench/baseline/builtin.json
```

#### F) Score an external HTTP filter

```bash
tools/rag-injbench run \
  --target http://localhost:8080/v1/scan \
  --header "X-Admin-Key: your-key"
```

#### G) Strict per-case failure (no baseline needed)

```bash
tools/rag-injbench run --target builtin --fail-on-cases
```

#### H) EE full corpus (`inj_corpus:full`)

```bash
export RAG_EE_ENTITLEMENTS=inj_corpus:full
export PYTHONPATH=rag-protection-enterprise:rag-protection-proxy

tools/rag-injbench run --corpus full-v1 --target builtin \
  --baseline tools/inj_bench/baseline/ee-full-v1.json
```

Use `ee-full-v1.json` for the EE corpus — **not** `builtin.json` (CE sampler yardstick).

### 19.3 CI parity helpers (optional)

Aggregated validation:

```bash
bash tools/validate_labs.sh
bash tools/validate_labs.sh -k baseline
```

Manual CI trigger (if you want to reproduce the gate quickly):

```bash
gh workflow run rag-injbench.yml --repo "$(gh repo view --json nameWithOwner -q .nameWithOwner)"
gh run list --workflow=rag-injbench.yml --limit 3
```

---

## Part 20 — #29 Vector ACL backfill (`acl-backfill`)

One-shot **Service** CLI that patches `allowed_groups` onto an **already-indexed** corpus without re-embedding — the ACL workshop unblocker when the prospect says *"we can’t re-index."*

Uses the **same** `connectors/acl_mapping` semantics as Drive ingest and #4 drift, so backfilled corpora stay sync-ready (#12).

**Demo script:** [../../commercial/labs/a4-acl-backfill/DEMO_SCRIPT.md](../../../ENTERPRISE.md) · **Competitive walkthrough:** [Tutorial 09 §N](09-implemented-features-walkthrough.md#part-n-vector-acl-backfill-a4-29) · **Tool README:** [../../../tools/acl_backfill/README.md](../../../tools/acl_backfill/README.md)

### 20.0 One-time setup (off camera)

```bash
tools/acl-backfill --version          # acl-backfill 0.1.0
```

| File | Role |
|------|------|
| `tools/acl_backfill/examples/store_snapshot.json` | Memory-backend corpus (4 docs) |
| `tools/acl_backfill/examples/permissions.json` | Drive-style permission matrix |
| `tools/acl_backfill/examples/group_map.yaml` | email / `@domain` → groups |
| `tools/acl_backfill/examples/permissions_flat.csv` | Flat groups CSV alternative |

---

### 20.1 Dry-run diff (60 sec)

```bash
tools/acl-backfill \
  --backend memory \
  --snapshot tools/acl_backfill/examples/store_snapshot.json \
  --permissions tools/acl_backfill/examples/permissions.json \
  --group-map tools/acl_backfill/examples/group_map.yaml
echo "exit=$?"
```

**Expected:** `DRY-RUN`, exit **0** — 3 changes, 1 store orphan, 1 permissions orphan (fail-closed `[]`).

**Say:** "Clipboard walk before anyone changes a label — no re-embed."

---

### 20.2 Apply + coverage artifact (60 sec)

```bash
tools/acl-backfill \
  --backend memory \
  --snapshot tools/acl_backfill/examples/store_snapshot.json \
  --permissions tools/acl_backfill/examples/permissions.json \
  --group-map tools/acl_backfill/examples/group_map.yaml \
  --apply --write-snapshot /tmp/a4-after.json \
  --coverage-out /tmp/a4-coverage.json
cat /tmp/a4-coverage.json
```

**Expected:** `APPLY`; coverage JSON lists orphans + `coverage_pct_after`. Payload metadata includes `acl_mapping_status` + `source_revision` (#4 / #12 ready).

---

### 20.3 Idempotent re-run (30 sec)

```bash
tools/acl-backfill \
  --backend memory \
  --snapshot /tmp/a4-after.json \
  --permissions tools/acl_backfill/examples/permissions.json \
  --group-map tools/acl_backfill/examples/group_map.yaml \
  --apply --format json | python3 -c "import sys,json; r=json.load(sys.stdin); print(r['written'], r['summary']['changed'])"
```

**Expected:** near-zero writes — safe when the customer refreshes the export.

---

### 20.4 Flat CSV permissions (30 sec)

```bash
tools/acl-backfill \
  --backend memory \
  --snapshot tools/acl_backfill/examples/store_snapshot.json \
  --permissions tools/acl_backfill/examples/permissions_flat.csv \
  --group-map tools/acl_backfill/examples/group_map.yaml
```

**Expected:** `--perm-format` auto-detects **flat**; groups applied from CSV.

---

### 20.5 Live backends (optional)

```bash
# Qdrant — sample corpus in rag_chunks
tools/acl-backfill \
  --backend qdrant --qdrant http://localhost:6333 --collection rag_chunks \
  --permissions tools/acl_backfill/examples/qdrant_permissions.json \
  --group-map tools/acl_backfill/examples/qdrant_group_map.yaml          # dry-run
tools/acl-backfill ... --apply                            # set_payload

# pgvector
tools/acl-backfill \
  --backend pgvector --pg-url "postgresql://…" \
  --permissions tools/acl_backfill/examples/qdrant_permissions.json \
  --group-map tools/acl_backfill/examples/qdrant_group_map.yaml --apply
```

Workshop cutover / rollback: [README § runbook](../../../tools/acl_backfill/README.md#workshop-runbook-staging--cutover--rollback).

---

### 20.6 Tests / labs gate (15 sec)

```bash
.venv/bin/python -m pytest -q tools/acl_backfill/tests
bash tools/validate_labs.sh -k acl-backfill
```

**Boundary:** metadata only — not a sync, not a connector, not an EE checkbox. Converts to the [ACL mapping workshop](../../../ENTERPRISE.md#2-idp--vector-acl-mapping-workshop).
