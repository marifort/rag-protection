# Guardrail 4 — Citation Auditing and Hallucination Control

This document explains how the RAG Protection Proxy verifies **LLM answers after generation**: responses must align with sanitized retrieved context, and answers that resemble system-prompt leaks are blocked and replaced with a safe fallback.

> **Depth pair for citation:** this page (pipeline / soft coverage / leak regex) + feature card **[#8 Per-claim citation hard gate](../features/08-citation-hard-gate.md)** (hard-gate policy knobs and `citation_hard_gate_failed`). Do not restate hard-gate knobs elsewhere. Optional paraphrase rescue (E3.5) is summarized here; deep dive stays on the phase doc.

**Index:** [guardrails/README.md](README.md) · **Hard gate (card):** [#8](../features/08-citation-hard-gate.md) · **Related (not peer depth):** [DETECTION_OVERVIEW.md](DETECTION_OVERVIEW.md) · [E3.4 per-claim API](../../../ENTERPRISE.md) · [E3.5 entailment](../../../ENTERPRISE.md) · [RAG_Protection.md § 4](../README.md#4-hallucination-and-citation-auditing-post-processing) · output DLP in [GUARDRAIL_2_DLP.md](GUARDRAIL_2_DLP.md)

---

## Quick answers

| Question | Answer |
|----------|--------|
| What is citation auditing? | Post-generation check that answer sentences are **grounded** in retrieved chunk text passed to the LLM. |
| When does it run? | **After** `LLMClient.chat()`, **before** output DLP (`scan_output()`). |
| What sources are checked? | Sanitized text from chunks that **passed** input guardrails (same strings in `build_messages()`). |
| What if verification fails? | Raw answer discarded; user sees `SAFE_FALLBACK`; `blocked: true`, `block_reason: "citation_verification_failed"`. |
| System-prompt leaks? | Regex patterns (e.g. *"As an AI assistant…"*) fail immediately when `block_system_prompt_leak: true`. |
| Backstop for injection? | If Guardrail 3 misses poisoned content, citation may catch ungrounded claims — heuristic, not guaranteed. |
| How is ungrounded content detected? | Token overlap + substring match, optional **entailment rescue** (E3.5), + system-prompt leak regex — see [How ungrounded content is detected](#how-ungrounded-content-is-detected) |
| Entailment / paraphrase rescue? | Optional second pass when lexical checks fail (`output.entailment_check`) — embedding similarity, not an LLM judge. Deep dive: [E3.5](../../../ENTERPRISE.md) |

---

## How ungrounded content is detected

Guardrail 4 does **not** scan for prompt injection or PII. It verifies the **LLM answer** against sanitized retrieved context **after generation**:

```text
LLM answer + source chunk texts
       │
       ▼
verify_citations()              guardrails/citation.py
  Step 1: system-prompt leak regex
  Step 2: per-sentence grounding
       · token overlap / substring
       · optional entailment rescue (E3.5) when lexical checks fail
       │
       ▼
passed → scan_output() (Guardrail 2)
failed → SAFE_FALLBACK, citation_verification_failed
```

Module: **`guardrails/citation.py`** only. No shared scanner stack.

Overview: [DETECTION_OVERVIEW.md](DETECTION_OVERVIEW.md).

### Step 1 — System-prompt leak detection

If `output.block_system_prompt_leak: true` (default), the full answer is scanned with `_SYSTEM_PROMPT_LEAK_PATTERNS`:

| Pattern (summary) | Example match |
|-------------------|---------------|
| `as an ai (assistant\|language model)` | *"As an AI assistant…"* |
| `my (core )?(programming\|instructions\|system prompt)` | *"my system prompt says…"* |
| `i (was\|am) (trained\|designed\|programmed) (by\|to)` | *"I was trained by…"* |
| `< retrieved_untrusted_context` | Model echoing context wrapper tags |

Any match → `passed: false`, `system_prompt_leak: true`, coverage `0.0` — **immediate block**, no grounding check.

**Example:**

```text
answer: As an AI assistant, I must follow my core programming.
→ blocked (system_prompt_leak: true)
```

### Step 2 — Sentence grounding (hallucination heuristic)

1. Join all source chunk texts (lowercased)
2. Split answer into sentences
3. For each sentence:
   - **Short** (< 3 tokens of length ≥ 4) → counted as supported
   - **Token overlap** ≥ 25% with source tokens → supported
   - **Substring match** — first 6 significant words appear in sources → supported
   - **Else if** `output.entailment_check: true` → optional **entailment rescue** (E3.5): embedding cosine (or test lexical fallback) vs each chunk; supported if best score ≥ `entailment_threshold` (default **0.55**)
4. `coverage_ratio = supported / total`
5. `passed = coverage_ratio >= min_citation_coverage` (default **0.15**)

Tokenization: `[a-z0-9]{4,}` — short words ignored.

**Examples** (source: *"Support is available Monday through Friday, 9am to 6pm Eastern."*):

| Answer | Coverage | Result |
|--------|----------|--------|
| *Support hours are Monday through Friday, 9am to 6pm Eastern.* | 1.0 | **PASS** — grounded |
| *The Q1 payroll total was 4.2 million dollars.* | 0.0 | **FAIL** — no overlap with source |
| *We offer phone support only on weekends.* | 0.0 | **FAIL** — contradicts source |

Lexical checks alone are a lightweight heuristic. Correct **paraphrases** can false-fail on word overlap; with entailment enabled they may still become `supported` via similarity scoring (see below).

<a id="brand-token-false-support"></a>

**Residual — short fabrications that share a brand token.** Overlap is
`|sentence_tokens ∩ source_tokens| / |sentence_tokens|`. A short invented
sentence that reuses a common entity name from the KB can clear the 25% bar
even when every other content word is unsupported:

| Sentence (vs sources that mention *Acme* only) | Tokens (≥ 4) | Overlap | Result |
|------------------------------------------------|--------------|---------|--------|
| *Acme was founded by penguins in Argentina.* | 4 (`acme`, `founded`, `penguins`, `argentina`) | 1/4 = **0.25** | **supported** (false pass) |
| *Acme was founded by emperor penguins in Argentina.* | 5 (+ `emperor`) | 1/5 = **0.20** | **unsupported** |
| *Acme was founded by a team of former astronauts in Antarctica.* | 6 | 1/6 ≈ **0.17** | **unsupported** |

Worked demo of the same rule in `rag-ground`: [lab6 VERDICT_WALKTHROUGH § 1](../../../ENTERPRISE.md#edge-case--short-fabrication-that-shares-a-brand-token). Mitigations: raise `min_citation_coverage`, enable `hard_citation_gate` / per-claim review, or add entailment / NLI depth where paraphrases matter.

### Step 2b — Entailment rescue (E3.5, optional)

When overlap and substring both fail for a sentence and `output.entailment_check` is on, `_ground_sentence()` runs a **second pass**:

- Compare the answer sentence to each retrieved chunk with the shared sentence-transformers embedder (MiniLM by default)
- If best cosine similarity ≥ `output.entailment_threshold` → mark **supported** and record `CitationClaim.entailment_score`
- Does **not** call the chat LLM; does **not** prove logical NLI entailment; does **not** overturn a sentence that already passed lexical checks

| Goal | Knob |
|------|------|
| Rescue rephrased FAQ answers | `entailment_check: true`, threshold ~`0.55` |
| Stricter rescue bar | Raise `entailment_threshold` (e.g. `0.75`–`0.9`) |
| Lexical-only grounding | `entailment_check: false` |

Scores appear on `citations.claims[].entailment_score` (Query Lab), and in audit `citation_failed` detail / debug `citation_claims` when forensics are on.

**Field naming caveat:** `entailment_score` is also filled on the **lexical** path (overlap ratio, or `1.0` for substring-only). A UI value of **`1` usually means near-copy / substring match**, not a perfect E3.5 embedding rescue. True second-pass scores are typically mid-range (e.g. ~0.6–0.85). See [E3.5 — Reading the Entailment column](../../../ENTERPRISE.md#reading-the-entailment-column-what-1-usually-means).

**Deep dive (plain English, demos, audit UI):** [E3.5 — Entailment Check](../../../ENTERPRISE.md). True cross-encoder NLI is planned as [E6.3](../../../ENTERPRISE.md).

### Relationship to injection detection

| Scenario | Guardrail 3 (injection) | Guardrail 4 (citation) |
|----------|---------------------------|-------------------------|
| Poisoned chunk blocked at scan | Chunk never reaches LLM | Not applicable |
| Poisoned chunk slips through | — | May fail if answer repeats attacker claim not in sanitized sources |
| Benign chunk, model hallucinates | — | May fail on low coverage |
| Model echoes system prompt | — | Leak regex blocks |

### Limitations

- Token overlap ≠ semantic correctness — subtle hallucinations can pass
- Without entailment, strict paraphrases may false-fail if coverage drops below threshold
- Entailment is similarity, not contradiction detection — fluent wrong numbers can still look “close”
- Soft coverage is text-level only; per-sentence `chunk_id` mapping and the **hard gate** are documented on [#8](../features/08-citation-hard-gate.md#policy) (API shape also in [E3.4](../../../ENTERPRISE.md))

---

## The threat

RAG models can:

1. **Hallucinate** — invent payroll figures, dates, or policies not present in retrieved chunks
2. **Leak instructions** — echo system-prompt phrasing (*"As an AI assistant, my core programming…"*)
3. **Obey poisoned context** — summarize attacker claims (fees waived, phishing URLs) not supported by sanitized sources

Citation auditing is a **post-generation gate**: the user never sees the raw LLM output when grounding or leak checks fail.

```text
Retrieved context: "Support is available Monday through Friday, 9am to 6pm Eastern."

Bad answer:  "Support is 24/7 worldwide."           → low coverage → BLOCK
Bad answer:  "As an AI assistant, I must help…"     → system leak  → BLOCK
Good answer: "Support hours are Mon–Fri 9am–6pm."   → grounded     → PASS
```

---

## Pipeline placement

Guardrail 4 runs at the **end** of the query pipeline, after the LLM and before the response is returned.

```text
scan_input(user_query)  (P1)
       │
       ▼
store.search()  (Guardrail 1)
       │
       ▼
scan_input(chunks)  (Guardrails 2 + 3)
       │
       ▼
build_messages() + LLMClient.chat()
       │
       ▼
verify_citations()              ← Guardrail 4 (this doc)
       │
       ▼
scan_output()                   ← Guardrail 2 output DLP
       │
       ▼
QueryResponse to client
```

**Key modules:**

| Module | Role |
|--------|------|
| `guardrails/citation.py` | `verify_citations()` — grounding + leak detection |
| `guardrails/output_pipeline.py` | Output DLP after citation passes |
| `pipeline.py` | Orchestration, `SAFE_FALLBACK`, audit on failure |

---

## Verification algorithm (`verify_citations`)

### Step 1 — System-prompt leak check

If `policy.output.block_system_prompt_leak` is `true` (default), the full answer is scanned for:

| Pattern (summary) | Example match |
|-------------------|---------------|
| `as an ai (assistant\|language model)` | *"As an AI assistant…"* |
| `my (core )?(programming\|instructions\|system prompt)` | *"my system prompt says…"* |
| `i (was\|am) (trained\|designed\|programmed) (by\|to)` | *"I was trained by…"* |
| `< retrieved_untrusted_context` | Model echoing context wrapper tags |

Any match → `passed: false`, `system_prompt_leak: true`, coverage `0.0`.

### Step 2 — Sentence grounding

1. Join all source chunk texts (lowercased) into one string
2. Split the answer into sentences (on `.`, `!`, `?`)
3. For each sentence:
   - **Short sentences** (< 3 tokens of length ≥ 4) → counted as supported (skip strict check)
   - **Token overlap** — ≥ 25% of sentence tokens appear in source tokens → supported
   - **Substring match** — first 6 significant words (5+ chars, stopwords removed) appear as a phrase in sources → supported
   - **Entailment rescue (optional)** — if lexical checks fail and `output.entailment_check: true`, embedding cosine vs chunks; supported when best score ≥ `entailment_threshold` (see [Step 2b](#step-2b--entailment-rescue-e35-optional) / [E3.5](../../../ENTERPRISE.md))

4. `coverage_ratio = supported_sentences / total_sentences`
5. `passed = coverage_ratio >= policy.output.min_citation_coverage` (default **0.15**)

Tokenization uses `[a-z0-9]{4,}` — short words and punctuation are ignored.

### Empty edge cases

| Case | Result |
|------|--------|
| Empty answer | `passed: false`, detail `"empty answer"` |
| No source tokens (should not happen if LLM was called) | `passed: true`, coverage `1.0` |

---

## Failure handling

When `verify_citations()` returns `passed: false`:

```python
SAFE_FALLBACK = (
    "I cannot provide that answer because the response failed security verification. "
    "Please rephrase your question or contact an administrator."
)
```

API response fields:

| Field | Value |
|-------|-------|
| `answer` | `SAFE_FALLBACK` (not the raw LLM text) |
| `blocked` | `true` |
| `block_reason` | `"citation_verification_failed"` |
| `citations` | `CitationCheck` with `passed: false`, `coverage_ratio`, `detail` |

An audit event is recorded: `kind: citation_failed`.

When citation **passes** but output DLP blocks (high-severity secret in answer), `block_reason` is `"output_guardrail_blocked"` instead — see [GUARDRAIL_2_DLP.md](GUARDRAIL_2_DLP.md).

---

## Configuration

From `config/policy.yaml` (`output` section) — **soft citation / leak** knobs owned here:

| Key | Default | Purpose |
|-----|---------|---------|
| `min_citation_coverage` | `0.15` | Minimum fraction of sentences that must align with sources |
| `block_system_prompt_leak` | `true` | Block answers matching leak regex patterns |
| `entailment_check` | `true` (code default) | Second-pass paraphrase rescue when lexical grounding fails ([E3.5](../../../ENTERPRISE.md)) |
| `entailment_threshold` | `0.55` | Min embedding similarity to count a sentence as supported |
| `challenge_threshold` | `0.5` | Output DLP risk threshold (separate from citation) |
| `block_threshold` | `0.85` | Output DLP block threshold |

**Hard gate / per-claim knobs** (`per_claim_citations`, `hard_citation_gate`, `substantive_min_tokens`) and `block_reason: citation_hard_gate_failed` — source of truth: [#8 feature card § Policy](../features/08-citation-hard-gate.md#policy). Do not duplicate that prose here.

**Tuning (soft coverage):** Lower `min_citation_coverage` → fewer false blocks, more hallucination tolerance. Raise it → stricter grounding, more false positives on paraphrased answers. Prefer enabling/tuning **entailment** before lowering coverage if the pain is mostly rephrased-but-correct FAQ answers.

Reload: `POST /admin/reload-policy`.

---

## Demo scenarios

### Grounded FAQ (should pass)

**Query:** *"What are support hours?"*  
**Token:** any demo token (`public-faq` is accessible to all)

```bash
curl -s http://localhost:8090/v1/query \
  -H "Authorization: Bearer employee-demo-token" \
  -H "Content-Type: application/json" \
  -d '{"query":"What are support hours?","top_k":4}' | python3 -m json.tool
```

**Expected:**

- `citations.passed: true`
- `citations.coverage_ratio` ≥ `0.15`
- Answer aligns with FAQ (*Monday through Friday, 9am to 6pm*)

### Payroll query (metadata visible)

```bash
curl -s http://localhost:8090/v1/query \
  -H "Authorization: Bearer hr-demo-token" \
  -H "Content-Type: application/json" \
  -d '{"query":"What is the Q1 payroll total?","top_k":4}' | python3 -m json.tool
```

**Expected:** `citations` object present. If the model stays grounded on `$4.2M` from context, `passed: true`. If it invents figures, `blocked: true` and `block_reason: "citation_verification_failed"`.

### Audit trail

```bash
curl -s "http://localhost:8090/audit/recent?limit=20" \
  -H "Authorization: Bearer hr-demo-token" | python3 -m json.tool
```

**Expected:** On failure, events with `kind: citation_failed` and `detail` such as `"2/3 sentences aligned with retrieved context"`.

Full walkthrough: [ARCHITECTURE.md § Guardrail Demo Walkthrough](../README.md#guardrail-demo-walkthrough).

---

## UI walkthrough

**Detailed test cases (label D):** [test-plans/GUARDRAIL_TEST_PLAN.md § D](../../../ENTERPRISE.md#d--citation-auditing) (TC-GR-D-001–005).

| Step | UI action | Expected |
|------|-----------|----------|
| 1 | **Query Lab** → **FAQ sample** → **Run Query** | **Citation / Output Checks** panel shows `passed: true`, coverage ≥ 0.15 |
| 2 | Enable **include_audit** → run FAQ query | Response includes audit slice; `citation_failed` absent |
| 3 | `hr-demo-token` + payroll query | Citation object present; grounded answers pass; invented figures may trigger safe fallback |
| 4 | **Audit Log** | On failure, `kind: citation_failed` with sentence alignment detail |
| 5 | **Policy Viewer/Admin** → `policy.yaml` | Tune `output.min_citation_coverage` (default 0.15); optional `entailment_check` / `entailment_threshold` |

Persistent `citation_failed` events export via [P2_PERSISTENT_AUDIT.md](P2_PERSISTENT_AUDIT.md) when `RAG_AUDIT_FILE` is set.

---

## Tests

| Test | File | What it checks |
|------|------|----------------|
| `test_citation_verification_passes_grounded_answer` | `tests/test_rag_protection.py` | FAQ-style grounded answer passes at 0.15 coverage |
| `test_citation_blocks_system_prompt_leak` | `tests/test_rag_protection.py` | *"As an AI assistant…"* fails with `system_prompt_leak` |

Run:

```bash
cd rag-protection-proxy
pytest -q tests/test_rag_protection.py -k citation
```

---

## MVP scope and gaps

| Shipped (this doc / soft path) | Documented elsewhere / not yet |
|--------------------------------|--------------------------------|
| Token-overlap + substring grounding | Per-claim mapping + hard gate → [#8](../features/08-citation-hard-gate.md) |
| Configurable `min_citation_coverage` | Cross-encoder NLI judge → [E6.3](../../../ENTERPRISE.md) (planned) |
| Optional embedding entailment rescue | Full plain-English / demo depth → [E3.5](../../../ENTERPRISE.md) |
| System-prompt leak regex blocklist | Semantic similarity to system prompt |
| Safe fallback on failure | Partial answer redaction (replace only bad sentences) |
| Audit event on citation failure (incl. claim entailment scores) | Tenant-scoped citation retention policies |
| Persistent audit export of failures (v1 P2) | |

Citation checks are **heuristic**. Paraphrased correct answers may still fail when entailment is off or below threshold; some hallucinations may pass if they share tokens or embedding neighborhood with context.

**Relationship to Guardrail 3:** Injection shielding blocks or sanitizes poisoned chunks before the LLM. Citation auditing is a **secondary backstop** if malicious content still influences the answer — it does not replace input scanning.

---

## Related documentation

| Topic | Document | Role |
|-------|----------|------|
| **#8 Hard gate (policy)** | [features/08-citation-hard-gate.md](../features/08-citation-hard-gate.md) | Peer depth — knobs / block reasons |
| Guardrails index | [README.md](README.md) | Index |
| Detection map (all guardrails) | [DETECTION_OVERVIEW.md](DETECTION_OVERVIEW.md) | Related — severity / risk overview |
| E3.4 per-claim API | [E3_4_PER_CLAIM_CITATIONS.md](../../../ENTERPRISE.md) | Related — delivery / schema track |
| E3.5 entailment rescue | [E3_5_ENTAILMENT_CHECK.md](../../../ENTERPRISE.md) | Related — paraphrase second pass (depth) |
| Persistent audit | [P2_PERSISTENT_AUDIT.md](P2_PERSISTENT_AUDIT.md) | Related |
| Output DLP (runs after citation) | [GUARDRAIL_2_DLP.md](GUARDRAIL_2_DLP.md) | Related |
| Injection backstop context | [GUARDRAIL_3_INJECTION.md](GUARDRAIL_3_INJECTION.md) | Related |
| When the LLM is skipped entirely | [TECH_STACK.md § When POST /v1/query invokes the LLM](../../product/TECH_STACK.md#when-post-v1query-invokes-the-llm) | Related |
| Quality techniques (rerank / HyDE) vs this gate | [RAG_QUALITY_VS_SECURITY.md](../../product/RAG_QUALITY_VS_SECURITY.md) | Related — what we ship vs keep in the client chain |
