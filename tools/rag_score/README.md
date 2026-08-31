# rag-score — RAG security posture scorecard (A3)

A free, self-serve **"grade my RAG config"** report. `rag-score` is a thin
wrapper over [`rag-scan`](../rag_scan/README.md): it runs the same checks, weights
the findings into a **0–100 score / A–F grade**, maps them onto the **OWASP LLM
Top 10**, and lists the **top fixes** — as a shareable Markdown / HTML / JSON card.

Because it reuses `rag-scan` (which imports the gateway's own config loaders), a
grade reflects the *same* configuration the RAG Protection gateway would load.

> Spec: [ADDITIONAL_OPPORTUNITIES_SPECS.md § A3](../../ENTERPRISE.md#a3--rag-security-posture-scorecard)
> · Tier: [SOLOPRENEUR § A3](../../ENTERPRISE.md#a3--rag-security-posture-scorecard)
> · OWASP map: [AI_SECURITY_COMPETENCY_LABS.md](../../ENTERPRISE.md#owasp-llm-top-10--coverage-map)
> · Scanner: [Lab 2 rag-scan](../rag_scan/README.md)
> · Lab deliverables: [SPEC](../../ENTERPRISE.md) · [DEMO_SCRIPT](../../ENTERPRISE.md) · [POSTURE_WALKTHROUGH](../../ENTERPRISE.md) (full prose: inputs, scoring, output)

This is a **top-of-funnel lead magnet**, not an audit: the grade is *indicative,
not a certification*, and it runs **entirely locally** — no configuration is
uploaded. A prospect runs it on their own config, sees the gaps, and books the
[GenAI/RAG security assessment](../../ENTERPRISE.md#1-genai--rag-security-assessment).

---

## Contents

- [Goal](#goal)
- [How it works](#how-it-works)
- [Architecture](#architecture)
- [Design](#design)
- [Install](#install)
- [Usage](#usage)
- [Scoring model](#scoring-model)
- [Report sections](#report-sections)
- [Rule → OWASP mapping](#rule--owasp-mapping)
- [Output formats](#output-formats)
- [Exit codes](#exit-codes)
- [CI integration](#ci-integration)
- [Publishing as a lead magnet](#publishing-as-a-lead-magnet)
- [Sample output](#sample-output)
- [Project layout](#project-layout)
- [Lab artifacts](#lab-artifacts)
- [Full prose walkthrough](../../ENTERPRISE.md)
- [Testing](#testing)
- [FAQ](#faq)
- [Boundaries](#boundaries)

---

## Goal

**The pain:** prospects and platform teams don't know how exposed their RAG
*configuration* is — demo tokens in prod, payroll indexed for `all-staff`, connectors
that fail open. Security leads need a **letter grade**, not a SARIF file, to forward
internally.

**The opportunity (A3):** repackage the **already-shipped** Lab 2 scanner (`rag-scan`)
as a buyer-friendly **A–F grade card** with OWASP framing and top fixes. A3 is the
*config-side* counterpart to [rag-ground (A6)](../rag_ground/README.md), which grades
*answers*.

| Property | What it means for A3 |
|----------|---------------------|
| **Thin wrapper** | ~8–12 h build; every finding comes from `rag-scan` |
| **Pre-incorporation** | Publishable OSS before a legal entity; self-qualifying leads |
| **Beside the product** | Grades declared YAML — not a merge into the proxy |
| **Natural upgrade path** | Poor grade → assessment SKU or A9 baseline packs |

**What A3 is not:** a certification, pen test, hallucination check, or MCP/agent audit.

---

## Architecture

See [Lab 8 SPEC](../../ENTERPRISE.md) for the full module map and CLI contract.

```text
rag-score CLI
  → posture.build_posture()
       → rag_scan.context.build_context()   # gateway loaders
       → rag_scan.checks.run_all(ctx)       # Lab 2 rules
       → scoring.score_findings()            # 0–100 → A–F
       → owasp.build_coverage() + top_fixes()
  → report.render(posture, fmt)              # markdown | html | json
```

**Core contract:** no scanner logic in `rag_score` — only scoring, OWASP attribution,
and rendering on top of Lab 2 findings.

---

## Design

### Scoring (summary)

| Severity | Penalty |
|----------|---------|
| Base | 100 |
| `critical` | −25 |
| `warning` | −8 |
| `info` | −2 |

Clamped to 0–100; grade bands at 90/80/70/60 → A/B/C/D/F. Full detail in [Scoring model](#scoring-model).

### OWASP coverage (summary)

| Risk | From findings | Notes |
|------|---------------|-------|
| LLM01 | POL001, POL003 | Prompt injection policy tuning |
| LLM06 | ACL*, SEC*, CON001, POL002, VEC001 | Data exposure / ACL |
| LLM07 | — | Not assessed — Lab 1 gateway |
| LLM08 | — | Not assessed — Lab 1 gateway |

New `rag-scan` rules must get a `RULE_TO_RISK` entry or `test_owasp.py` fails.

---

## How it works

```text
prospect runs:  rag-score --env prod --acl acl_policy.prod.yaml [--policy ... --sample-docs ...]
  │
  ▼
┌──────────────────────────────────────────────────────────────┐
│ rag_score                                                     │
│                                                              │
│  posture.build_posture()                                     │
│    ├─ rag_scan.context.build_context()   ← gateway loaders   │
│    ├─ rag_scan.checks.run_all(ctx)       → List[Finding]     │
│    ├─ scoring.score_findings()           → 0–100 → A/B/C/D/F │
│    └─ owasp.build_coverage() / top_fixes()                   │
│                                                              │
│  report.render(posture, fmt)  → markdown | html | json      │
└──────────────────────────────────────────────────────────────┘
  │
  ▼
POSTURE.md / posture.html / posture.json   (shareable, branded, local-only)
```

The scorecard owns **no security logic** of its own — every finding comes from
`rag-scan`, which in turn imports `rag_protection_proxy.config`. New scanner rules
are graded automatically; a CI consistency test
([`test_owasp.py`](tests/test_owasp.py)) fails if a new rule is added without an
OWASP attribution.

---

## Install

The fastest path is the **wrapper script** — no install, works from any
directory (it puts `tools/` on `PYTHONPATH` and prefers the repo `.venv`):

```bash
tools/rag-score --env prod --acl rag-protection-proxy/config/acl_policy.prod.yaml
```

To install the `rag-score` **console script** (depends on `rag-scan`):

```bash
pip install -e tools/rag_scan          # dependency: the scanner
pip install -e tools/rag_score         # editable, dev
# or, with the live vector probe:
pip install -e 'tools/rag_score[vector]'

rag-score --env prod --acl rag-protection-proxy/config/acl_policy.prod.yaml
```

`rag-score` → `rag-scan` → `rag_protection_proxy.config`. When run from a checkout
all three resolve automatically; for an out-of-tree install also
`pip install -e rag-protection-proxy`.

**Requirements:** Python ≥ 3.11. No third-party runtime deps beyond `rag-scan`
(which needs `pyyaml`); `qdrant-client` only for the optional `--qdrant` probe.

---

## Usage

```bash
# Grade the production ACL (Markdown to stdout)
tools/rag-score --env prod \
  --acl rag-protection-proxy/config/acl_policy.prod.yaml

# Branded HTML card, written to a file
tools/rag-score --env prod \
  --acl rag-protection-proxy/config/acl_policy.prod.yaml \
  --format html --output posture.html

# Machine-readable JSON (badges / automation)
tools/rag-score --env prod --format json --output posture.json

# Include sample documents (enables the ACL002 confidential-exposure check)
tools/rag-score --env prod \
  --acl rag-protection-proxy/config/acl_policy.prod.yaml \
  --sample-docs rag-protection-proxy/config/sample_documents.json

# Live vector-store probe (VEC001) — needs qdrant-client
tools/rag-score --env prod --qdrant http://localhost:6333

# Opt-in CI gate: fail the build if the grade drops below B
tools/rag-score --env prod \
  --acl rag-protection-proxy/config/acl_policy.prod.yaml \
  --fail-under B
```

### Options

| Flag | Default | Meaning |
|------|---------|---------|
| `--policy PATH` | shipped `policy.yaml` | Guardrail policy to grade |
| `--acl PATH` | shipped `acl_policy.yaml` | ACL policy to grade |
| `--sample-docs PATH` | shipped `sample_documents.json` | Documents for the ACL002 check |
| `--qdrant URL` | _(off)_ | Live vector probe (VEC001) |
| `--env {dev,prod,production}` | **`prod`** | Environment the grade is for |
| `--format {markdown,html,json}` | `markdown` | Report format |
| `--output PATH` | _(stdout)_ | Write report to a file |
| `--fail-under {A,B,C,D,F}` | _(off)_ | Exit 1 if the grade is worse than this |
| `--version` | — | Print version and exit |

> **Why `--env prod` by default?** A posture grade is about *production* exposure.
> Several rules (demo tokens, default admin keys, missing IdP auth) only apply in
> prod, so grading at `--env prod` is the meaningful default. Pass `--env dev` to
> grade a local/demo posture. (Note: `rag-scan` itself defaults to `dev`.)

> The default `--acl` is the **demo** file (`acl_policy.yaml`), which is unsafe in
> prod by design — running `tools/rag-score --env prod` with no `--acl` will
> correctly grade it **F**. Point `--acl` at `acl_policy.prod.yaml` for the real
> production posture.

---

## Scoring model

Deliberately simple and stable, so a grade is explainable to a non-security buyer
and reproducible across runs.

| Input | Effect |
|-------|--------|
| Base | `100` |
| Each `critical` finding | `−25` |
| Each `warning` finding | `−8` |
| Each `info` finding | `−2` |
| Clamp | result bounded to `[0, 100]` |

```text
score = clamp(0, 100, 100 − 25·crit − 8·warn − 2·info)
```

| Score | Grade | Characterisation |
|-------|-------|------------------|
| 90–100 | **A** | Strong — no critical exposure in the declared config |
| 80–89 | **B** | Good — a few issues to tighten before production |
| 70–79 | **C** | Fair — notable gaps that an attacker could chain |
| 60–69 | **D** | Weak — at least one path to data exposure is open |
| 0–59 | **F** | Failing — critical misconfigurations present right now |

Source: [`scoring.py`](scoring.py) (`WEIGHTS`, `GRADE_BANDS`).

---

## Report sections

1. **Grade** — letter + score + one-line characterisation + severity counts.
2. **OWASP LLM Top 10 coverage** — status for the RAG-relevant risks:
   - `LLM01` Prompt injection and `LLM06` Sensitive information disclosure —
     status derived from findings (clean / minor / needs attention / at risk).
   - `LLM07` Insecure plugin/tool design and `LLM08` Excessive agency — flagged
     *not assessed by a config scan*, with a pointer to the runtime tool gateway
     (Lab 1), because they are runtime/agent concerns a static config check
     cannot judge.
3. **Top fixes** — the three highest-severity remediations (de-duplicated by
   rule + remediation, so a rule firing on many documents counts once).
4. **Next step** — CTA to the GenAI/RAG security assessment.

---

## Rule → OWASP mapping

| Rules | OWASP risk |
|-------|------------|
| `ACL001` `ACL002` `ACL003` `POL002` `CON001` `SEC001` `SEC002` `VEC001` | **LLM06** — sensitive information disclosure |
| `POL001` `POL003` | **LLM01** — prompt injection |

Rule definitions and conditions live in the
[`rag-scan` rule catalog](../rag_scan/README.md#rule-catalog). Mapping source:
[`owasp.py`](owasp.py) (`RULE_TO_RISK`).

---

## Output formats

| `--format` | File | Use |
|------------|------|-----|
| `markdown` | `POSTURE.md` | Gist / README / email — the default shareable artifact |
| `html` | `posture.html` | Self-contained branded card (inline CSS, no assets, no JS) |
| `json` | `posture.json` | Badges / automation / dashboards |

The JSON shape is stable:

```json
{
  "product": "Marifort Gate",
  "env": "prod",
  "grade": "F",
  "score": 50,
  "blurb": "Failing posture — ...",
  "counts": { "critical": 2, "warning": 0, "info": 0 },
  "owasp_coverage": [
    { "risk_id": "LLM06", "name": "Sensitive information disclosure",
      "status": "critical", "status_label": "At risk (critical)",
      "rule_ids": ["ACL001", "SEC001"], "note": "" }
  ],
  "top_fixes": [
    { "rule_id": "ACL001", "severity": "critical", "title": "...",
      "message": "...", "remediation": "...", "location": "..." }
  ],
  "disclaimer": "Indicative posture grade, not a certification. ..."
}
```

---

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Report produced (and grade ≥ `--fail-under`, if set) |
| `1` | Grade is below `--fail-under` (opt-in CI gate) |
| `2` | Configuration could not be loaded / validated |

---

## CI integration

The scorecard is primarily a **lead magnet**, but `--fail-under` lets teams pin a
minimum grade in CI. Example GitHub Actions step:

```yaml
- name: RAG posture grade
  run: |
    tools/rag-score --env prod \
      --acl rag-protection-proxy/config/acl_policy.prod.yaml \
      --format markdown --output POSTURE.md \
      --fail-under B
- uses: actions/upload-artifact@v4
  with:
    name: rag-posture
    path: POSTURE.md
```

For a hard **shift-left gate** on critical findings (rather than a grade
threshold), use `rag-scan` directly — see
[`.github/workflows/rag-scan.yml`](../../docs/ce/README.md).

---

## Publishing as a lead magnet

The intended top-of-funnel flow (no legal entity required to publish):

1. Generate the HTML card for the shipped/demo config:
   `tools/rag-score --env prod --format html --output posture.html`.
2. Host it (gist, GitHub Pages, microsite) with the "grade your own config"
   instructions and the privacy note (**runs locally, nothing is uploaded**).
3. Every prospect run is a qualified-lead signal; the CTA routes to the
   assessment SKU. A poor grade is the natural opening for
   [A9 policy baseline packs](../../ENTERPRISE.md#a9--industry-policy-baseline-packs-policy-as-code)
   ("graded D? start from a pre-validated baseline").

---

## Sample output

A full failing-config report (Markdown) is committed at
[`examples/POSTURE.sample.md`](examples/POSTURE.sample.md). Regenerate it with:

```bash
tools/rag-score --env prod \
  --policy tools/rag_scan/tests/fixtures/bad_policy.yaml \
  --acl    tools/rag_scan/tests/fixtures/bad_acl.yaml \
  --sample-docs tools/rag_scan/tests/fixtures/bad_sample_documents.json
```

---

## Project layout

```text
tools/rag_score/
├── __init__.py        # version + package docstring
├── __main__.py        # python -m rag_score
├── scoring.py         # weights, clamp, A–F bands, blurbs
├── owasp.py           # rule→OWASP map, coverage rows, top-fix selection
├── posture.py         # build_context + run_all + assemble Posture
├── report.py          # markdown / html / json renderers + branding
├── cli.py             # argparse CLI, exit codes, --fail-under gate
├── pyproject.toml     # standalone package + rag-score console script
├── README.md
├── examples/
│   └── POSTURE.sample.md
└── tests/
    ├── _util.py           # fixtures path + Finding factory
    ├── test_scoring.py    # weighting + grade banding
    ├── test_owasp.py      # mapping completeness, coverage, top fixes
    ├── test_posture.py    # orchestration over fixtures, env behaviour
    ├── test_report.py     # md/html(escaping)/json rendering
    └── test_cli.py        # formats, --fail-under, exit codes, --version
tools/rag-score            # convenience wrapper (any directory)
```

---

## Lab artifacts

Buyer-facing deliverables live under
[`docs/commercial/labs/lab8-posture-scorecard/`](../../ENTERPRISE.md):

| Doc | Purpose |
|-----|---------|
| [SPEC.md](../../ENTERPRISE.md) | Goal, architecture, module map, CLI contract, implementation status |
| [POSTURE_WALKTHROUGH.md](../../ENTERPRISE.md) | Full prose: inputs, scoring, how to read output, worked examples |
| [CONTROL_MAP.md](../../ENTERPRISE.md) | Threat → control → residual + OWASP mapping |
| [BOUNDARY.md](../../ENTERPRISE.md) | Out-of-scope statements + CE/EE line |
| [DEMO_SCRIPT.md](../../ENTERPRISE.md) | ~5 min runnable demo (prod vs demo ACL) |
| [TALK_TRACK.md](../../ENTERPRISE.md) | 5–8 min buyer/engineer talk track |

---

## Testing

```bash
python -m pytest tools/rag_score/tests -q          # 69 tests
python -m pytest tools/rag_scan/tests tools/rag_score/tests -q   # scanner + scorecard
```

Tests reuse `rag-scan`'s golden fixtures so the scorecard is exercised on the
same bad/good configs the scanner is tested against. Coverage includes: scoring
math + clamping + grade boundaries, OWASP mapping completeness (every scanner
rule must be attributed), coverage status per risk, top-fix de-duplication and
ordering, posture over good/bad/dev/prod configs, Markdown/HTML/JSON rendering
(including HTML escaping of finding content), and CLI formats / `--fail-under`
gate / exit codes / `--version`.

---

## FAQ

**Does my config leave my machine?** No. Everything runs locally; the report is
written to stdout or a file you choose. The disclaimer in every report says so.

**Is this an audit or certification?** No — it's an *indicative* grade based on
the declared config. A hands-on assessment is the paid follow-on.

**Why are LLM07/LLM08 "not assessed"?** They are runtime/agent-design concerns
(tool/plugin abuse, excessive agency) that a static config scan can't judge.
They're surfaced for completeness and pointed at the runtime tool gateway (Lab 1).

**My prod config grades A but I expected issues.** The grade reflects the
*declared* config only (same limits as `rag-scan`). Common surprises:

- **`all-staff` everywhere is not automatically a finding.** ACL003 only flags
  `default_groups: [*]`. Hierarchy that inherits `all-staff`, and `all-staff` on
  non-confidential sample docs, are expected. Confidential exposure needs
  ACL002 (confidential `classification` *plus* a broad group on `--sample-docs`).
- **`--qdrant` / VEC001 does not classify documents.** It only fails when sampled
  payloads are *missing* `allowed_groups`. Points tagged `all-staff` still pass.
  It does not identify `hr-payroll` / `exec-strategy` as confidential in Qdrant.
- **ACL002 confidential markers** (on `metadata.classification`): substring
  match for `confidential`, `secret`, `restricted`, `pii`, `phi`, `pci`. Labels
  like `public` or `internal-engineering` are not confidential for this rule.

**How do I add a new rule to the grade?** Add it to `rag-scan`; it's graded
automatically. Map its `rule_id` to an OWASP risk in `owasp.RULE_TO_RISK` (the
consistency test enforces this).

---

## Boundaries

- Reports on the **declared config**, same limits as `rag-scan`: **ACL002** keys
  off sample-doc `classification` substrings (not a public/confidential enum);
  **VEC001** (needs `--qdrant`) only checks live payloads for missing
  `allowed_groups` — not classification and not over-broad groups.
- Lead magnet, **not an audit** — explicitly *indicative, not a certification*.
- Runs **locally**; no configuration leaves the machine.
- A standalone OSS/lead-gen asset that lives **beside** the product — it is not
  merged into the RAG Protection gateway (per the
  [do-now operating rule](../../ENTERPRISE.md#what-do-now-means-and-doesnt)).
