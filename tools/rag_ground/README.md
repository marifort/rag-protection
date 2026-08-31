# rag-ground — grounding / hallucination check (A6)

A free, self-serve **"did the model make this up?"** check. `rag-ground` scores an
LLM answer against the **source chunks it was supposed to be grounded in** and
returns a **grounded / ungrounded / leak** verdict plus a coverage ratio — the
metric an eval or CI pipeline gates on.

It is a thin wrapper over the **shipped output guardrail**
[`verify_citations`](../../rag-protection-proxy/rag_protection_proxy/guardrails/citation.py):
the *same* per-sentence grounding + system-prompt-leak check the RAG Protection
gateway runs on every answer at runtime. `rag-ground` just exposes it **outside**
the request pipeline as a batch/CI tool — so a grade reflects the exact behaviour
the gateway would enforce.

> Spec: [ADDITIONAL_OPPORTUNITIES_SPECS.md § A6](../../ENTERPRISE.md#a6--grounding--hallucination-check-library-oss)
> · Guardrail: [GUARDRAIL_4_CITATION.md](../../docs/ce/README.md)
> · Sibling lead magnet: [rag-score (A3)](../rag_score/README.md)

This is a **top-of-funnel lead magnet**, not a hallucination guarantee: it
measures *grounding in the supplied context*, not the factual correctness of that
context, and runs **entirely locally** — no answer or source text is uploaded. A
team wires it into their eval set, sees their ungrounded rate, and books the
[GenAI/RAG security assessment](../../ENTERPRISE.md#1-genai--rag-security-assessment)
or adopts the runtime output guardrail.

---

## Quick start

From the repo root (uses the shipped example files — no setup required):

```bash
# Single answer — expect UNGROUNDED (exit 1): two sentences are fabricated
tools/rag-ground check \
  --answer tools/rag_ground/examples/answer.txt \
  --sources tools/rag_ground/examples/sources.json

# Batch eval set — 1/3 grounded, 1 leak; default gate fails
tools/rag-ground check --jsonl tools/rag_ground/examples/eval.jsonl
```

---

## Contents

- [Why A6 exists](#why-a6-exists)
- [How it works](#how-it-works)
- [Architecture](#architecture)
- [Design](#design)
- [Install](#install)
- [Usage](#usage)
- [Shipped examples](#shipped-examples)
- [Lab artifacts](#lab-artifacts)
- [Inputs](#inputs)
- [Verdicts & scoring](#verdicts--scoring)
- [Output formats](#output-formats)
- [Exit codes](#exit-codes)
- [CI integration](#ci-integration)
- [Publishing as a lead magnet](#publishing-as-a-lead-magnet)
- [Sample output](#sample-output)
- [Project layout](#project-layout)
- [Testing](#testing)
- [FAQ](#faq)
- [Boundaries](#boundaries)

---

## Why A6 exists

**The pain:** every RAG team ships LLM answers with **no grounding gate**. Stakeholders
ask *"did the model make this up?"* and there is no self-serve, local tool to answer
that question against the retrieved context — only ad-hoc manual review or opaque
vendor claims.

**The opportunity (A6):** repackage the **already-shipped** runtime output guardrail
(`verify_citations`) as a standalone OSS CLI + library. A6 is the **answer-side**
counterpart to [rag-score (A3)](../rag_score/README.md), which grades the *config*;
together they cover "is my RAG setup safe?" and "are my answers actually grounded?"

**Why it is a do-now lead magnet:**

| Property | What it means for A6 |
|----------|-------------------|
| **Thin wrapper** | ~8–12 h build; no new scoring logic — every verdict comes from the gateway guardrail |
| **Pre-incorporation** | Publishable OSS before a legal entity; feeds outbound and qualified leads |
| **Beside the product** | Not a merge into the proxy — the guardrail is *already* in the product at runtime |
| **Natural upgrade path** | Poor grounding rate → assessment SKU or adoption of the runtime output guardrail |

**What A6 is not:** a hallucination guarantee, a fact-checker, or proof that the
*source chunks* are correct. It only checks whether each sentence in the answer
is **supported by the context you supply**.

---

## How it works

```text
team runs:  rag-ground check --answer answer.txt --sources sources.json [--threshold 0.75]
            rag-ground check --jsonl eval.jsonl     # batch eval set
  │
  ▼
┌──────────────────────────────────────────────────────────────┐
│ rag_ground                                                   │
│                                                              │
│  grounding.check_answer()                                    │
│    ├─ build_policy(threshold, entailment)  → OutputPolicy    │
│    └─ verify_citations(answer, chunks, …)  ← gateway guardrail│
│        → CitationCheck{passed, coverage_ratio,              │
│            system_prompt_leak, claims[]}                     │
│  grounding.check_jsonl()  → BatchResult (aggregate pass rate)│
│                                                              │
│  report.render(result, fmt)  → text | json | junit          │
└──────────────────────────────────────────────────────────────┘
  │
  ▼
verdict + coverage + ungrounded sentences   (local-only)
```

`rag-ground` owns **no grounding logic** of its own — every verdict comes from
`verify_citations`, which it imports from `rag_protection_proxy`. Entailment
(`--entailment`) uses an offline lexical embedder (`HashEmbedder`) so the tool
never downloads a model or makes a network call.

---

## Architecture

### End-to-end data flow

```mermaid
flowchart TD
  subgraph inputs [Inputs]
    A["--answer PATH<br/>(plain text file)"]
    S["--sources PATH<br/>(JSON chunks)"]
    J["--jsonl PATH<br/>(batch eval set)"]
  end

  subgraph cli [cli.py]
    M{mode?}
    M -->|single| LA[load_answer + load_sources]
    M -->|batch| LJ[load_jsonl]
  end

  subgraph core [grounding.py]
    NS[normalize_sources]
    BP[build_policy → OutputPolicy]
    CA[check_answer]
    CJ[check_jsonl → BatchResult]
    LA --> NS --> CA
    LJ --> CJ
    BP --> CA
    BP --> CJ
  end

  subgraph guardrail [rag_protection_proxy — shipped]
    VC[verify_citations]
    VC --> CC[CitationCheck]
  end

  subgraph output [report.py]
    R[render text | json | junit]
  end

  A --> LA
  S --> LA
  J --> LJ
  CA --> VC
  CJ --> VC
  CC --> R
  CJ --> R
  R --> OUT[stdout or --output file]
```

### Module responsibilities

| Module | Role |
|--------|------|
| [`cli.py`](cli.py) | Argparse CLI: mode resolution (single vs batch), exit codes (0/1/2), `--min-pass-rate` gate |
| [`grounding.py`](grounding.py) | Input loaders, source normalization, `OutputPolicy` mapping, `GroundingResult` / `BatchResult` wrappers |
| [`report.py`](report.py) | Text / JSON / JUnit renderers + product branding and disclaimer |
| [`_bootstrap.py`](_bootstrap.py) | Locates `rag_protection_proxy` from a checkout (sibling `rag-protection-proxy/`) |
| [`tools/rag-ground`](../rag-ground) | Bash wrapper: sets `PYTHONPATH`, prefers repo `.venv` |

### Guardrail reuse (the core design constraint)

A6 deliberately imports **`verify_citations`** from
[`guardrails/citation.py`](../../rag-protection-proxy/rag_protection_proxy/guardrails/citation.py)
and adds **zero alternate scoring paths**. That means:

1. **Runtime parity** — a CI gate using `rag-ground` enforces the same rules the gateway would at request time.
2. **Maintenance** — guardrail improvements (entailment, leak patterns, short-sentence handling) flow through automatically.
3. **Honest marketing** — "same check as the product" is literally true, not a reimplementation.

The guardrail pipeline per answer:

```text
answer text
  │
  ├─► system-prompt leak regex scan ──► LEAK (fail immediately, coverage 0)
  │
  ├─► sentence split on [.!?]
  │
  └─► for each sentence:
        ├─ lexical token overlap ≥ 25% against any chunk → supported
        ├─ substring match against joined sources → supported
        └─ optional entailment (--entailment):
              HashEmbedder lexical similarity ≥ --entailment-threshold → supported

coverage_ratio = supported_sentences / total_sentences
passed = coverage_ratio ≥ --threshold  (maps to OutputPolicy.min_citation_coverage)
```

See [GUARDRAIL_4_CITATION.md](../../docs/ce/README.md) for the full guardrail spec.

---

## Design

### Thin wrapper, not a second platform

Following the [do-now operating rule](../../ENTERPRISE.md#what-do-now-means-and-doesnt),
A6 is a **standalone funnel asset beside the product**, not a feature merge. The
product already runs `verify_citations` on every answer; A6's job is **packaging**
that capability for eval/CI workflows.

### Input normalization (flexible sources JSON)

Teams export retrieved chunks in different shapes. `normalize_sources()` accepts:

- `[{"id", "text"}]` — canonical form (also `chunk_id` / `content` aliases)
- `["chunk a", "chunk b"]` — bare strings, ids become `"0"`, `"1"`, …
- `{"chunks": [...]}` or `{"sources": [...]}` — common wrapper keys

Batch mode (`--jsonl`) expects one JSON object per line with `answer`, `sources`, and optional `id`.

### Policy mapping

CLI flags map directly to `OutputPolicy` fields the guardrail already understands:

| CLI flag | `OutputPolicy` field | Notes |
|----------|---------------------|-------|
| `--threshold` | `min_citation_coverage` | Default 0.75 |
| `--entailment` | `entailment_check` | Uses offline `HashEmbedder` only |
| `--entailment-threshold` | `entailment_threshold` | Default 0.55 |
| _(always on)_ | `per_claim_citations=True` | So reports can list ungrounded sentences |
| _(always on)_ | `block_system_prompt_leak=True` | Leak always fails |

### Single vs batch modes

| Mode | Inputs | Result type | CI gate |
|------|--------|-------------|---------|
| Single | `--answer` + `--sources` | `GroundingResult` | Exit 0 iff grounded (no leak) |
| Batch | `--jsonl` | `BatchResult` | Exit 0 iff `pass_rate ≥ --min-pass-rate` |

Modes are mutually exclusive — providing both exits 2.

### Reporter pattern

Reporters follow the same pattern as [`rag_scan`](../rag_scan/) (text / JSON / JUnit).
JUnit output gives CI test panels one `<testcase>` per answer, with failure messages
listing ungrounded sentences — useful for regression tracking on eval sets.

### Privacy by construction

No network calls, no model downloads, no telemetry. `--entailment` uses `HashEmbedder`
(lexical token hashing) rather than calling an external embedding API. All I/O is
local file read + stdout/file write.

---

## Install

The fastest path is the **wrapper script** — no install, works from any
directory (it puts `tools/` on `PYTHONPATH` and prefers the repo `.venv`):

```bash
tools/rag-ground check \
  --answer tools/rag_ground/examples/answer.txt \
  --sources tools/rag_ground/examples/sources.json
```

To install the `rag-ground` **console script**:

```bash
pip install -e rag-protection-proxy     # provides verify_citations
pip install -e tools/rag_ground         # editable, dev

rag-ground check \
  --answer tools/rag_ground/examples/answer.txt \
  --sources tools/rag_ground/examples/sources.json
```

When run from a checkout the proxy resolves automatically (via the wrapper and a
`_bootstrap` shim); for an out-of-tree install also `pip install -e rag-protection-proxy`.

**Requirements:** Python ≥ 3.11. No third-party runtime deps of its own; it reuses
the proxy's `verify_citations` (which pulls `pydantic`). No ML model is downloaded.

---

## Usage

```bash
# Single answer (text verdict to stdout) — shipped example is intentionally UNGROUNDED
tools/rag-ground check \
  --answer tools/rag_ground/examples/answer.txt \
  --sources tools/rag_ground/examples/sources.json

# Tighten / loosen the grounding bar
tools/rag-ground check \
  --answer tools/rag_ground/examples/answer.txt \
  --sources tools/rag_ground/examples/sources.json \
  --threshold 0.9

# Batch eval set — one {answer, sources, [id]} per line
tools/rag-ground check --jsonl tools/rag_ground/examples/eval.jsonl

# Enable offline lexical entailment for paraphrased answers
tools/rag-ground check \
  --answer tools/rag_ground/examples/answer.txt \
  --sources tools/rag_ground/examples/sources.json \
  --entailment

# Machine-readable JSON / CI JUnit, written to a file
tools/rag-ground check \
  --jsonl tools/rag_ground/examples/eval.jsonl \
  --format junit --output grounding.xml

# Batch CI gate: pass only if at least 95% of answers are grounded
tools/rag-ground check \
  --jsonl tools/rag_ground/examples/eval.jsonl \
  --min-pass-rate 0.95
```

### Options

| Flag | Default | Meaning |
|------|---------|---------|
| `--answer PATH` | — | File with the answer text (single mode) |
| `--sources PATH` | — | JSON source chunks (single mode) |
| `--jsonl PATH` | — | Batch eval set, one record per line |
| `--threshold FLOAT` | `0.75` | Min coverage ratio for an answer to pass |
| `--entailment` | _(off)_ | Offline lexical entailment for paraphrases |
| `--entailment-threshold FLOAT` | `0.55` | Min entailment score when `--entailment` set |
| `--min-pass-rate FLOAT` | `1.0` | Batch gate: exit 1 if pass rate is below this |
| `--format {text,json,junit}` | `text` | Report format |
| `--output PATH` | _(stdout)_ | Write report to a file |
| `--version` | — | Print version and exit |

Provide **either** `--answer` + `--sources` **or** `--jsonl` (not both).

---

## Shipped examples

All example files live under [`examples/`](../../docs/ce/README.md). Run them from the **repo root**
so paths resolve correctly.

| File | Purpose |
|------|---------|
| [`examples/answer.txt`](examples/answer.txt) | Single-mode demo answer: 3/6 sentences grounded (uptime, encryption, free tier), 3 fabricated (emperor-penguin founders, Antarctica founders, Mars colony) → **UNGROUNDED** |
| [`examples/answer_leak.txt`](examples/answer_leak.txt) | Same Acme text plus “As an AI language model…” → **LEAK** (coverage forced to 0) |
| [`examples/sources.json`](examples/sources.json) | Three KB chunks supporting the grounded sentences only |
| [`examples/eval.jsonl`](examples/eval.jsonl) | Batch demo: one fully grounded row, one partial hallucination, one system-prompt leak |
| [`examples/GROUNDING.sample.txt`](examples/GROUNDING.sample.txt) | Committed text report from the batch example (regenerate — see below) |

**Expected single-mode result** on `answer.txt` (threshold 0.75):

```text
Verdict: UNGROUNDED  (coverage 0.50, threshold 0.75)
  3/6 sentences aligned with retrieved context

Ungrounded sentences (3):
  - "Acme was founded by emperor penguins in Argentina."
  - "Acme was founded by a team of former astronauts in Antarctica."
  - "The company plans to open a colony on Mars next decade."
```

**Expected single-mode LEAK** on `answer_leak.txt`:

```text
Verdict: LEAK  (coverage 0.00, threshold 0.75)
  response contains system-prompt-like phrasing

System-prompt-like phrasing detected in the answer.
```

**Expected batch result** on `eval.jsonl` (default `--min-pass-rate 1.0`):

```text
Pass rate: 1/3 (0.33)  threshold 0.75  min-pass-rate 1.00 -> FAIL
System-prompt leaks: 1
```

To use your own files, copy the examples as a template:

```bash
cp tools/rag_ground/examples/answer.txt my-answer.txt
cp tools/rag_ground/examples/sources.json my-sources.json
# edit my-answer.txt and my-sources.json, then:
tools/rag-ground check --answer my-answer.txt --sources my-sources.json
```

---

## Lab artifacts

Commercial lab deliverables (same structure as Lab 2) live under
[`docs/commercial/labs/lab6-grounding/`](../../ENTERPRISE.md):

| Doc | Purpose |
|-----|---------|
| [SPEC.md](../../ENTERPRISE.md) | Architecture, module map, CLI contract, implementation status |
| [CONTROL_MAP.md](../../ENTERPRISE.md) | Threat → control → residual + OWASP mapping |
| [BOUNDARY.md](../../ENTERPRISE.md) | Out-of-scope statements + CE/EE line |
| [DEMO_SCRIPT.md](../../ENTERPRISE.md) | ~3 min runnable demo (shipped examples) |
| [VERDICT_WALKTHROUGH.md](../../ENTERPRISE.md) | Full prose: how each shipped verdict is computed |
| [TALK_TRACK.md](../../ENTERPRISE.md) | 5 min buyer/engineer talk track |

Active CI workflow: [`.github/workflows/rag-ground.yml`](../../docs/ce/README.md)
(runs the 50-test suite on PRs; uploads JUnit from the batch example).

---

## Inputs

**`--sources` JSON** accepts several shapes:

```json
[{"id": "kb-1", "text": "..."}, {"id": "kb-2", "text": "..."}]
```

- a list of `{id, text}` objects (also accepts `chunk_id` / `content` keys),
- a bare list of strings (`["chunk a", "chunk b"]` — ids become the index), or
- a `{"chunks": [...]}` / `{"sources": [...]}` wrapper.

**`--jsonl` batch** — one JSON object per line:

```json
{"id": "ex-1", "answer": "The capital of France is Paris.", "sources": [{"id": "s1", "text": "Paris is the capital of France."}]}
```

`id` is optional (used to label items in the report); `answer` and `sources` are
required.

---

## Verdicts & scoring

Each answer is split into sentences; each sentence is grounded against the source
chunks (lexical overlap, with optional entailment). The **coverage ratio** is the
fraction of sentences supported by the context.

| Verdict | When |
|---------|------|
| **grounded** | `coverage_ratio ≥ --threshold` and no system-prompt leak |
| **ungrounded** | `coverage_ratio < --threshold` |
| **leak** | answer contains system-prompt-like phrasing (always fails) |

For a **batch**, the headline metric is the **pass rate** = grounded answers /
total. `--min-pass-rate` (default `1.0`) is the CI gate.

Scoring lives entirely in the shipped guardrail (`verify_citations`); this tool
only chooses the `min_citation_coverage` (= `--threshold`) and whether entailment
is on.

**Full prose walkthrough of the shipped examples** (single UNGROUNDED answer,
single LEAK answer, batch `--min-pass-rate`, and JUnit XML field-by-field):
[docs/commercial/labs/lab6-grounding/VERDICT_WALKTHROUGH.md](../../ENTERPRISE.md).

---

## Output formats

| `--format` | Use |
|------------|-----|
| `text` | Human-readable verdict + ungrounded sentences (default) |
| `json` | Stable machine shape for eval dashboards / badges |
| `junit` | JUnit XML — CI test panels show one case per answer |

The JSON shape is stable (single mode):

```json
{
  "tool": "rag-ground",
  "mode": "single",
  "verdict": "ungrounded",
  "passed": false,
  "coverage_ratio": 0.6,
  "threshold": 0.75,
  "system_prompt_leak": false,
  "claims": [{"sentence": "...", "chunk_id": "kb-1", "supported": true, "entailment_score": 0.8}],
  "ungrounded_sentences": ["..."]
}
```

In batch mode the payload carries `total`, `passed_count`, `leak_count`,
`pass_rate`, `min_pass_rate`, `gate_passed`, and a per-answer `items` array.

---

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Grounded (single) / pass rate ≥ `--min-pass-rate` (batch) |
| `1` | Ungrounded or system-prompt leak (single) / gate not met (batch) |
| `2` | Invalid input (missing file, bad JSON, malformed record) |

---

## CI integration

Gate an eval set so a drop in grounding fails the build:

```yaml
- name: RAG grounding gate
  run: |
    tools/rag-ground check --jsonl eval/grounding.jsonl \
      --threshold 0.75 --min-pass-rate 0.95 \
      --format junit --output grounding.xml
- uses: actions/upload-artifact@v4
  if: always()
  with:
    name: rag-grounding
    path: grounding.xml
```

See also the repo's own test workflow:
[`.github/workflows/rag-ground.yml`](../../docs/ce/README.md).

Pairs with [`rag-score` (A3)](../rag_score/README.md), which grades the *config*;
`rag-ground` grades the *answers*.

---

## Publishing as a lead magnet

The intended top-of-funnel flow (no legal entity required to publish):

1. Run the batch demo and capture output:
   `tools/rag-ground check --jsonl tools/rag_ground/examples/eval.jsonl`.
2. Share the README + examples; emphasize **runs locally, nothing is uploaded**.
3. Every team that wires this into their eval set and sees a poor pass rate is a
   qualified lead for the [assessment SKU](../../ENTERPRISE.md#1-genai--rag-security-assessment)
   or runtime output guardrail adoption.
4. Pair with [rag-score (A3)](../rag_score/README.md) in outbound: *"grade your
   config, then grade your answers"*.

---

## Sample output

A batch report (text) is committed at
[`examples/GROUNDING.sample.txt`](examples/GROUNDING.sample.txt). Regenerate it:

```bash
tools/rag-ground check --jsonl tools/rag_ground/examples/eval.jsonl \
  --format text --output tools/rag_ground/examples/GROUNDING.sample.txt
```

---

## Project layout

```text
tools/rag_ground/
├── __init__.py        # version + package docstring
├── __main__.py        # python -m rag_ground
├── _bootstrap.py      # locate rag_protection_proxy from a checkout
├── grounding.py       # input loaders + verify_citations wrapper + aggregation
├── report.py          # text / json / junit renderers + branding
├── cli.py             # argparse CLI, modes, exit codes, gates
├── pyproject.toml     # standalone package + rag-ground console script
├── README.md
├── examples/
│   ├── answer.txt     # single-mode demo (3/6 grounded) → UNGROUNDED
│   ├── answer_leak.txt # same + system-prompt-like phrasing → LEAK
│   ├── sources.json   # three KB chunks
│   ├── eval.jsonl     # batch: grounded + hallucination + leak
│   └── GROUNDING.sample.txt
└── tests/
    ├── _util.py           # reusable answers + sources fixtures
    ├── conftest.py
    ├── test_grounding.py  # core checks, normalization, loaders, batch
    ├── test_report.py     # text / json / junit rendering
    └── test_cli.py        # modes, formats, exit codes, gates, --version
tools/rag-ground           # convenience wrapper (any directory)
```

---

## Testing

### Run the suite

```bash
# From repo root (uses .venv if present)
python -m pytest tools/rag_ground/tests -q          # 50 tests

# Single file / single test
python -m pytest tools/rag_ground/tests/test_cli.py -q
python -m pytest tools/rag_ground/tests/test_cli.py::test_single_ungrounded_exits_one -q
```

### Test layout and what each file covers

| File | Tests | Coverage |
|------|-------|----------|
| [`tests/_util.py`](tests/_util.py) | _(fixtures)_ | Shared `GROUNDED_ANSWER`, `UNGROUNDED_ANSWER`, `LEAK_ANSWER`, `SOURCES`; path to shipped `examples/` |
| [`tests/test_grounding.py`](tests/test_grounding.py) | 24 | Core guardrail integration: grounded / ungrounded / leak verdicts, threshold behaviour, entailment flag, `build_policy` mapping, `normalize_sources` (dicts, strings, wrappers, errors), file loaders, batch aggregation + gate |
| [`tests/test_report.py`](tests/test_report.py) | 11 | Text verdict + ungrounded list + leak banner; batch pass rate + item ids; JSON round-trip fields; JUnit pass/fail counts + XML escaping; unknown format error |
| [`tests/test_cli.py`](tests/test_cli.py) | 15 | End-to-end CLI: single grounded (exit 0) / ungrounded (exit 1) using **shipped examples**, threshold relaxation, batch gate, json/junit formats, `--output` file, input validation (missing file, bad JSON, ambiguous modes), `--version` |

### Fixture design

Tests deliberately use **two fixture layers**:

1. **Programmatic fixtures** (`_util.py`) — minimal Paris/Louvre answers for precise
   unit tests of grounding, reporters, and CLI with temp files.
2. **Shipped examples** (`examples/answer.txt`, `examples/answer_leak.txt`, `examples/eval.jsonl`) — exercised
   by CLI integration tests (`test_single_ungrounded_exits_one`, batch gate tests)
   so the committed demo files cannot drift from expected behaviour unnoticed.

### What is *not* duplicated in tests

Scoring logic is **not** re-tested here — that belongs to the proxy's guardrail tests.
The rag-ground suite asserts **wiring**: correct policy mapping, input normalization,
aggregation, report shapes, exit codes, and that the shipped examples produce the
documented verdicts.

### Manual smoke test (matches README quick start)

```bash
# Expect exit 1 + UNGROUNDED
tools/rag-ground check \
  --answer tools/rag_ground/examples/answer.txt \
  --sources tools/rag_ground/examples/sources.json

# Expect exit 1 + batch FAIL (1/3 pass rate)
tools/rag-ground check --jsonl tools/rag_ground/examples/eval.jsonl

# Expect exit 0 after relaxing threshold
tools/rag-ground check \
  --answer tools/rag_ground/examples/answer.txt \
  --sources tools/rag_ground/examples/sources.json \
  --threshold 0.5
```

---

## FAQ

**Does my data leave my machine?** No. Everything runs locally; the report is
written to stdout or a file you choose. `--entailment` uses an offline lexical
embedder — no model download, no network.

**Is high coverage proof the answer is correct?** No. It proves the answer is
*supported by the supplied context*. A confidently wrong premise in the context
will still pass — this is a grounding gate, not a fact-checker.

**Why did a short sentence pass without an obvious match?** Two common cases,
both from the same gateway guardrail:

1. **Fewer than three tokens** (words of length ≥ 4) — treated leniently as
   supported (too few tokens to score).
2. **Brand-token overlap ≥ 25%** — a short fabrication that reuses a name already
   in the sources (e.g. *Acme*) can clear the bar even when the rest is fiction.
   *Acme was founded by penguins in Argentina.* → tokens `acme`, `founded`,
   `penguins`, `argentina` → only `acme` overlaps → **1/4 = 0.25** → marked
   supported. Adding one more unique word (*emperor penguins…*) drops overlap to
   1/5 = 0.20 and the sentence is listed as ungrounded. Full walkthrough:
   [VERDICT_WALKTHROUGH § edge case](../../ENTERPRISE.md#edge-case--short-fabrication-that-shares-a-brand-token).

**How is this different from `rag-score`?** `rag-score` (A3) grades your *config*;
`rag-ground` (A6) grades your *answers*. Both are local-only lead magnets that
wrap shipped modules.

**Why does the README use long paths like `tools/rag_ground/examples/answer.txt`?**
The example files ship inside the package directory. Run commands from the **repo
root** so those paths resolve, or copy the examples to your working directory.

---

## Boundaries

- Measures **grounding in the supplied context**, not factual correctness of that
  context — a wrong but well-supported claim still passes.
- Short invented sentences that reuse a brand token from the sources can clear
  the 25% lexical-overlap bar (see
  [VERDICT_WALKTHROUGH edge case](../../ENTERPRISE.md#edge-case--short-fabrication-that-shares-a-brand-token)).
- System-prompt-leak detection is **regex-based** (the shipped patterns); novel
  phrasings can slip.
- Lead magnet / CI gate, **not a hallucination guarantee**.
- Runs **locally**; no answer or source text leaves the machine.
- A standalone OSS/lead-gen asset that lives **beside** the product. The
  underlying capability is *already in the product* as the runtime output
  guardrail — A6 just repackages it as an external batch/CI tool (per the
  [do-now operating rule](../../ENTERPRISE.md#what-do-now-means-and-doesnt)).
