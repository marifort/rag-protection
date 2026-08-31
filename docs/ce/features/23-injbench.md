# #23 — Prompt-injection benchmark

> **Which doc?** **Card** (this page) = behavior / policy · **Demo** = show it · **Learn** = teach it · **Lab** = GTM depth
>
> [Demo](../demos/23-injbench.md) · [Learn](../learn/03-tools-and-assessment.md#23-prompt-injection-benchmark) · [Lab](../../../ENTERPRISE.md) · [Tutorial](../tutorials/06-labs-a2-a3-a6-a7.md)

| Field | Value |
|-------|-------|
| **Edition** | CE harness · EE full corpus (`inj_corpus:full`) |
| **Status** | Shipped |
| **Code** | `tools/inj_bench/` · EE corpus under `rag-protection-enterprise/corpus/injection/` |

**Demo:** [../demos/23-injbench.md](../demos/23-injbench.md) · **Tutorial:** [T06](../tutorials/06-labs-a2-a3-a6-a7.md)

---

## What & why

InjBench is a regression test for your prompt-injection defenses, not a live attack tool and not a claim that you’re “safe.”

When someone ships an injection filter—regex rules, an ML model, or a whole proxy—they often have no shared way to answer: “Did we get better or worse than last week?” Vendors quote block rates on private prompt sets. Engineers tweak one jailbreak and silently break benign traffic. Regressions show up in production. InjBench exists to close that gap with a versioned, labeled set of examples and a scoring harness that always runs the same way.

You run `rag-injbench`. It loads a corpus of YAML cases. Each case is a short text payload plus labels: what kind of attack it is (instruction override, role hijack, exfiltration, secret extraction, obfuscation, chat-template tricks, or deliberately benign), how it’s delivered (direct user text, an indirect poisoned chunk, hidden Unicode, base64, and so on), and what the filter should do—**block** it hard, **flag** it, or **pass** it because it’s harmless. The runner feeds every payload into a target. The default target is the same `PromptInjectionScanner` and `MLInjectionScanner` your product already uses in production, so the score reflects real shipped behavior rather than a separate demo engine that can drift. You can also point it at any HTTP scan API and score someone else’s filter with the same yardstick.

After the run, it answers three questions. Of the cases that should have been caught, how many were? Of the benign controls, how many were wrongly flagged? And how does that break down by attack category? Those numbers are compared to a committed baseline file. If detection drops or false positives rise, the process exits non-zero—so CI can refuse a merge that quietly weakened the shield. On the community edition sampler (about 39 cases), the gate is strict: 100% detection and 0% false positives. Enterprise gets a much larger matrix (320 cases) behind an entitlement; that bigger set is a coverage yardstick, not a promise of perfection.

What it is *not* matters as much as what it is. It does not explore novel jailbreaks, multi-turn social engineering, or live exploit chains—that’s red-team territory. It does not enforce policy in production; Guardrail 3 and your `policy.yaml` do that. Passing the benchmark does not certify a third-party product. The small public subset (~15 payloads) is intentionally limited so people can’t overfit to the full private set and then claim victory.

In one sentence: InjBench repeatedly runs the same known injection (and benign) examples against your real scanners, scores catch rate and false alarms, and fails the build when those numbers get worse—a standardized test route for injection defense, not a guarantee that every possible attack is covered.

CE ships a sampler; EE entitlement unlocks the full corpus.

## Defaults (`tools/rag-injbench run --target builtin`)

With no other flags, the CLI uses:

| Input | Default | Path |
|-------|---------|------|
| **Corpus** | `--corpus sampler` | `tools/inj_bench/corpus/sampler.yaml` |
| **Baseline** | auto-selected when `--baseline` is omitted | `tools/inj_bench/baseline/builtin.json` |

`--published-only` still reads that same YAML file but keeps only entries with `published: true` (~15 payloads).

EE full matrix (`--corpus full-v1` / `ee-full-v1`, requires `inj_corpus:full`):

| Input | Path |
|-------|------|
| **Corpus** | `rag-protection-enterprise/corpus/injection/full-v1.yaml` |
| **Baseline** | pass explicitly: `tools/inj_bench/baseline/ee-full-v1.json` (do not reuse `builtin.json`) |

Short names starting with `full-` always resolve via the EE package, not `tools/inj_bench/corpus/`. For a CE-side copy, use a non-`full-*` stem (e.g. `--corpus local-v1` after placing `tools/inj_bench/corpus/local-v1.yaml`) or pass an explicit path. See [tools/inj_bench/README.md](../../../tools/inj_bench/README.md).

## Gaps

Not a guarantee of injection safety or exhaustive coverage.

## Engineering

[a7 SPEC](../../../ENTERPRISE.md) · CLI [README](../../../tools/inj_bench/README.md)
