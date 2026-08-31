# Tutorial 07 — CI workflows & gates

> **Lab / A aliases:** CI wraps **#6** (`rag-scan`), **#19** (`rag-ground`), **#23** (`rag-injbench`), and related assessment CLIs. Prefer `#N` — [FEATURE_ID_ALIASES.md](../../shared/FEATURE_ID_ALIASES.md).

This page explains how CI is used to enforce RAG security properties *before* runtime:

- config safety gates (`rag-scan`)
- grounding / citation eval (`rag-ground`, #19)
- prompt-injection regression (`rag-injbench`, #23)
- the general CE/console/security CI workflows

For full CI/CD details (matrix, repo split, path-filtered behavior), see [CI_CD.md](../README.md).

---

## 1) Workflow map (CE repo)

In this repo, CI in GitHub Actions runs these key workflows:

- `ci.yml`: baseline unit/integration tests + console build + live integration tests
- `security.yml`: weekly dependency audit + static analysis + secrets scan + docker security scan (path-filtered on `main`)
- `rag-scan.yml`: path-filtered gate that scans the **production** ACL config (`acl_policy.prod.yaml`) for critical misconfigs
- `rag-ground.yml`: #19 eval harness workflow (unit tests + shipped batch JUnit artifact)
- `rag-injbench.yml`: #23 injection benchmark workflow (unit tests + baseline regression gate)

The CE workflow matrix table is in [CI_CD.md](../README.md#workflow-matrix).

---

## 2) `rag-scan.yml` (production config safety gate)

What it gates:

- Loads both dev/demo ACL (`acl_policy.yaml`) and production ACL (`acl_policy.prod.yaml`)
- Fails PRs on **critical** findings in the production ACL/config
- Generates a JUnit artifact for GitHub checks (`rag-scan-report`)

Local equivalent:

```bash
bash tools/rag-scan check \
  --env prod \
  --acl rag-protection-proxy/config/acl_policy.prod.yaml \
  --severity critical \
  --format junit --output /tmp/rag-scan.xml
echo "exit=$?"
```

---

## 3) `rag-ground.yml` (#19 grounding / hallucination checks)

What it gates:

- Runs the unit test suite: `python -m pytest tools/rag_ground/tests -q`
- Also generates a JUnit report from the shipped batch eval example (`tools/rag_ground/examples/eval.jsonl`)
- Uploads `rag-ground-report`

Local equivalent:

```bash
python -m pytest tools/rag_ground/tests -q

# Optional: generate the same JUnit artifact CI uploads
bash tools/rag-ground check \
  --jsonl tools/rag_ground/examples/eval.jsonl \
  --format junit --output /tmp/rag-ground.xml || true
```

Notes:

- The workflow gates on unit tests; the shipped batch eval is intentionally “demo narrative” failing by default.

---

## 4) `rag-injbench.yml` (#23 injection benchmark regression gate)

What it gates:

- Runs unit tests: `python -m pytest tools/inj_bench/tests -q` (with hash embedder determinism)
- Runs baseline regression for builtin scanners using committed baseline metrics:
  - `tools/rag-injbench run --target builtin --baseline tools/inj_bench/baseline/builtin.json`
- Uploads a JUnit artifact (`rag-injbench-report`)

Local equivalent (baseline gate):

```bash
tools/rag-injbench run \
  --target builtin \
  --baseline tools/inj_bench/baseline/builtin.json \
  --format junit --output /tmp/rag-injbench.xml
echo "exit=$?"
```

---

## 5) What about `rag-score` and `mcp-lint`?

`rag-score` (#20 posture scorecard):

- There is no dedicated `rag-score.yml` workflow in this repo snapshot.
- Instead, CI-style enforcement is achieved by *embedding `--fail-under` into your own pipeline*.

Example CI step:

```yaml
- name: RAG posture grade
  run: |
    tools/rag-score --env prod \
      --acl rag-protection-proxy/config/acl_policy.prod.yaml \
      --format markdown --output POSTURE.md \
      --fail-under B
```

`mcp-lint` (#27 manifest linter):

- The repo includes `tools/mcp_lint/` and an example in `tools/mcp_lint/README.md` for publishing a JUnit artifact.
- The CI workflow file is not present in `.github/workflows/` in this repo snapshot, but the intended step is straightforward:
  `mcp-lint scan --manifest ... --format junit --output ...`.

---

## 6) How to interpret CI results (what to look for)

1. If `rag-scan` fails: PR introduced critical production ACL/config misconfigs (demo ACL is intentionally separate).
2. If `rag-ground` fails: grounding/citation verification logic regressed (unit tests first).
3. If `rag-injbench` fails: injection detection metrics regressed vs committed baseline (detection rate down or false-positive up).

In all three cases, the uploaded JUnit artifact shows granular per-test failures in GitHub checks.

---

## 7) CI artifacts: exact filenames + artifact names

These workflows upload a single JUnit XML file as a GitHub Actions artifact:

- `rag-scan` (`.github/workflows/rag-scan.yml`)
  - Generated: `rag-scan.xml`
  - Artifact name: `rag-scan-report`
- `rag-ground` (`.github/workflows/rag-ground.yml`)
  - Generated: `rag-ground.xml`
  - Artifact name: `rag-ground-report`
- `rag-injbench` (`.github/workflows/rag-injbench.yml`)
  - Generated: `rag-injbench.xml`
  - Artifact name: `rag-injbench-report`

Where to find them in GitHub:

1. Open the PR → look at the failing **Checks** entry for the workflow/job.
2. Use the workflow run page’s **Artifacts** section to download the uploaded XML.

