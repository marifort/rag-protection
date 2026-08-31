# CE feature cards

One-page reference per shipped `#N`. **Canonical IDs:** [INDEX.md](../../INDEX.md).

## Which doc for this feature?

| Job | Open | Owns |
|-----|------|------|
| Behavior, policy knobs, block reasons | **This card** (`features/#N-….md`) | Source of truth for what the feature does |
| Timed curl / UI script (~3–5 min) | [demos/#N](../demos/) | Commands + expected output only — link here for policy prose |
| Where it sits in the pipeline | [security/](../security/README.md) (when applicable) | Guardrail order, scan semantics, detection map |
| Learn from scratch (analogy + first try) | [learn/](../learn/README.md) | Teaching — do not re-specify knobs; link the card |
| Matrices, APIs, non-claims | [FEATURE_CATALOG.md](../FEATURE_CATALOG.md) | Technical reference (**not** `learn/`) |
| Multi-feature walk | [tutorials/](../tutorials/README.md) | Paths across several `#N` |
| GTM depth (SPEC / talk track) | [commercial/labs/](../../../ENTERPRISE.md) | Sales/lab packages only — link from card; don’t duplicate policy |

**Hard rule:** policy knobs and `block_reason` values live on the **card**. Demo, learn, and lab docs link to the card (or to a `#policy` heading on it).

Every card starts with a **Which doc?** box (Card · Demo · Security · Learn · Lab).

## Authoring template

Copy into `##-short-slug.md`. Replace placeholders. Drop rows that do not apply (e.g. no pipeline doc, no lab).

````markdown
# #N — Short title

> **Which doc?** **Card** (this page) = behavior / policy · **Demo** = show it · **Security** = pipeline depth · **Learn** = teach it · **Lab** = GTM depth
>
> [Demo](../README.md) · [Security](../README.md) · [Learn](../README.md) · [Lab](../../../ENTERPRISE.md) · [Tutorial](../README.md)

| Field | Value |
|-------|-------|
| **Edition** | CE |
| **Status** | Shipped \| Partial \| Pack |
| **Legacy alias** | Lab X / A# / E3.x (optional) |
| **Code** | `path/under/rag_protection_proxy/…` |
| **Tests** | `tests/…` |
| **Pipeline doc** | [GUARDRAIL_….md](../README.md) (optional) |

**Demo:** [../demos/NN-slug.md](../README.md) · **Tutorial:** [T0x §…](../README.md) · **Learn:** [learn §#N](../README.md) · **Lab:** [commercial/labs/…](../../../ENTERPRISE.md) (optional)

---

## What & why

One short paragraph: problem + what this control does.
One sentence: who cares / when to turn it on.

---

## How it works

```text
(flow diagram)
```

### Policy

```yaml
# knobs that ship with this feature — full prose for each below
```

**`knob_name`** — what it does, default/interaction with siblings, failure mode.

### Block behavior (if applicable)

| Field | Value |
|-------|-------|
| `blocked` / audit `kind` | … |
| `block_reason` | … |

---

## Validate (smoke)

Minimal curl or CLI + one pytest pointer. Full script: link **Demo**.

---

## Console

Which workspace / policy page (if any).

---

## Gaps & non-claims

Honest limits. Point to EE / deeper docs only as related — not as a second source of truth for CE knobs.

---

## Engineering reference

| Artifact | Path |
|----------|------|
| Module | `…` |
| Pipeline / phase doc | `…` |
````

### Section checklist

| Section | Required? | Notes |
|---------|-----------|-------|
| Which doc? box | Yes | Card · Demo · Security · Learn · Lab |
| Metadata table + nav line | Yes | Nav: Demo · Tutorial · Learn · Lab (omit missing) |
| What & why | Yes | No curl dumps here |
| How it works | Yes | Include **Policy** when the feature has knobs |
| Validate (smoke) | Yes | Keep short; demo owns the timed walk |
| Console | If UI exists | |
| Gaps & non-claims | Preferred | |
| Engineering reference | Preferred | |

### Do not

- Paste the full demo script into the card (link it).
- Re-teach analogies here (that belongs in `learn/`).
- Invent a second policy table in `security/` or lab SPECs — update the card, then link.

**Exemplar:** [#8 citation hard gate](08-citation-hard-gate.md) (policy knobs + hard rule applied).
