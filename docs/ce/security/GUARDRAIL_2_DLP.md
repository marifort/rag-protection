# Guardrail 2 — Semantic Data Loss Prevention (DLP)

This document explains how the RAG Protection Proxy prevents **sensitive data leakage** through the RAG pipeline: raw PII, infrastructure secrets, and risky URLs are detected and redacted (or blocked) before they reach the LLM or appear in chat logs.

**Index:** [guardrails/README.md](README.md) · **Related:** [RAG_Protection.md § 2](../README.md#2-semantic-data-loss-prevention-dlp) · [ARCHITECTURE.md § Guardrail 2 demo](../README.md#guardrail-2--semantic-dlp-post-retrieval-pre-llm) · [KNOWLEDGE_BASE.md](../README.md)

---

## Quick answers

| Question | Answer |
|----------|--------|
| What is semantic DLP here? | Post-retrieval scanning that **redacts or blocks** PII, secrets, and suspicious URLs in chunk text before LLM context is built. |
| Is the user query scanned? | **Yes (v1 P1)** — `scan_input()` runs on `req.query` before retrieval; same PII/secrets/URL scanners apply. See [P1_USER_QUERY_GUARDRAILS.md](P1_USER_QUERY_GUARDRAILS.md). |
| Where does input DLP run? | `scan_input()` on **user query** (P1), each ACL-authorized **chunk**, and **ingest content** (P1); `scan_output()` on the LLM answer. |
| Redact or block? | **Redact** by default (replace matches with tokens like `[REDACTED_SSN]`). High-severity secrets (e.g. private keys, API keys) can push risk ≥ `block_threshold` → chunk **blocked**. |
| What if all chunks are blocked? | No LLM call; response with `block_reason: "all_chunks_blocked"`. |
| Output backstop? | `scan_output()` re-runs PII, secrets, and URL scanners on the final answer before returning it to the user. |
| How is sensitive content detected? | Regex scanners in `scanners/pii.py`, `secrets.py`, `url_threat.py`, plus optional **NER-style** person-name/address detection in `scanners/pii_ner.py` when `dlp.enable_ner: true` — see [How sensitive content is detected](#how-sensitive-content-is-detected) |
| What is `dlp.enable_ner`? | Policy toggle that runs `PIINERScanner` on input and output paths — see [Scanner 4 — NER PII](#scanner-4--ner-pii-piinerscanner) |

---

## How sensitive content is detected

Sensitive data is found primarily by **regex patterns** in three scanner modules, plus an optional **NER-style** scanner (E3.1) for person names and street addresses. All scanners are orchestrated by `scan_input()` (chunks, query, ingest) and `scan_output()` (LLM answers).

The NER scanner is **not** a spaCy/Presidio ML model — it is a lightweight heuristic in `scanners/pii_ner.py` (capitalized name patterns, US-style street suffixes, blocklists). It is toggled by `dlp.enable_ner` (default `true` in code; shipped `config/policy.yaml` may differ).

### Input path (query, chunks, ingest)

Same stack as Guardrail 3 — DLP scanners run **after** `PromptInjectionScanner`:

```text
scan_input(text)
  ├─ PromptInjectionScanner     (Guardrail 3 — runs first)
  ├─ URLThreatScanner           ← this doc
  ├─ PIIScanner                 ← this doc (if redact_pii)
  ├─ CustomPatternScanner       ← E6.2 dlp.custom_patterns (kind: dlp)
  ├─ PIINERScanner              ← this doc (if dlp.enable_ner)
  └─ SecretsScanner             ← this doc (if redact_secrets)
       │
       ▼
apply_dlp_labels()              E3.2 — PCI/PHI labels on findings
       │
       ▼
aggregate_risk() + decide()     guardrails/risk_scoring.py
```

Reported `risk_score` still includes every finding. **Input BLOCK** uses only injection, secrets, and URL findings. PII, NER, and `kind: dlp` custom patterns redact and at most `CHALLENGE` — they cannot withhold the rest of the chunk. High-severity secrets or metadata URLs still push that block score ≥ `block_threshold` → `BLOCK`.

### Module responsibilities

| Module | Detects | Redacts? |
|--------|---------|----------|
| `scanners/pii.py` | Email, US phone, US SSN, Canadian SIN, Luhn-valid credit cards | Yes → `[REDACTED_EMAIL]`, etc. |
| `scanners/pii_ner.py` | Person names, US-style street addresses (when `dlp.enable_ner`) | Yes → `[REDACTED_PERSON_NAME]`, `[REDACTED_ADDRESS]` |
| `scanners/secrets.py` | OpenAI/Anthropic keys, AWS keys, GitHub PATs, Slack tokens, private keys, JWTs, `password=` assignments | Yes → `[REDACTED_*]` |
| `scanners/url_threat.py` | Cloud metadata hosts, private/loopback IPs, denylist, optional domain allowlist | No — flags only |
| `scanners/dlp_labels.py` | Maps finding categories to audit labels (`PHI`, `PCI`) | No — labels only |
| `guardrails/input_pipeline.py` | Runs scanners, audit, verdict | — |
| `guardrails/output_pipeline.py` | Same scanners on LLM output | — |

Pattern catalogs: [Scanner 1 — PII](#scanner-1--pii-piiscanner), [Scanner 2 — Secrets](#scanner-2--secrets-secretsscanner), [Scanner 3 — URL threats](#scanner-3--url-threats-urlthreatscanner), [Scanner 4 — NER PII](#scanner-4--ner-pii-piinerscanner).

Overview of all guardrails: [DETECTION_OVERVIEW.md](DETECTION_OVERVIEW.md).

### Worked examples (default policy, chunk path)

#### SSN in payroll text — redacted, mid-risk

```text
Employee SSN on file example format: 123-45-6789
```

| Category | Severity | Sanitized text |
|----------|----------|----------------|
| `ssn` | 0.70 | `… [REDACTED_SSN] …` |

Risk **0.70** → `CHALLENGE` → with default `challenge_mode: block`, chunk **blocked**. With `challenge_mode: allow`, redacted text may reach the LLM.

#### SIN in payroll text — redacted as SIN, not SSN

```text
Employee SIN on file example format: 046-454-286
```

| Category | Severity | Sanitized text |
|----------|----------|----------------|
| `sin` | 0.70 | `… [REDACTED_SIN] …` |

Same risk band as SSN. Audit Log Findings show **SIN (PHI)**; Detail shows `sanitized + warning: SIN` (not `ssn`). A 3-2-4 number labeled as SIN in nearby text (`Look up SIN 123-45-6789`) is also logged as **SIN**. A true `SSN 123-45-6789` stays **SSN**. See [Scanner 1 — SSN vs SIN](#ssn-vs-sin).

#### AWS access key — blocked

```text
AWS backup key: AKIAIOSFODNN7EXAMPLE
```

| Category | Severity |
|----------|----------|
| `aws_access_key` | 0.95 |

Risk **0.95** → `BLOCK` → chunk excluded from LLM context (redaction alone is not enough).

#### Private key — blocked

```text
-----BEGIN RSA PRIVATE KEY-----
```

| Category | Severity |
|----------|----------|
| `private_key` | 1.00 |

Risk **1.00** → `BLOCK`.

#### Cloud metadata URL — blocked

```text
Fetch config from http://169.254.169.254/latest/meta-data/
```

| Category | Severity |
|----------|----------|
| `cloud_metadata_url` | 1.00 |

Risk **1.00** → `BLOCK`. URL text is **not** redacted — the whole chunk is excluded.

### How sensitive content is detected on output

After the LLM generates an answer, **`verify_citations()` runs first** (Guardrail 4), then `scan_output()` scrubs the answer:

```text
LLM answer
       │
       ▼
verify_citations()              Guardrail 4 (grounding / leak check)
       │
       ▼
scan_output(answer)             Guardrail 2 output DLP
  ├─ SecretsScanner
  ├─ PIIScanner
  └─ URLThreatScanner
       │
       ▼
decide(risk, output.challenge_threshold, output.block_threshold)
  defaults: 0.5 / 0.85
```

Catches secrets or PII the model **re-introduced** even when input chunks were clean. Example:

```text
answer: Contact leaked@corp.com or use sk-abcdefghijklmnopqrstuvwxyz123456
```

| Finding | Severity |
|---------|----------|
| `openai_api_key` | 0.95 |
| `email` | 0.30 |

Risk **0.95** → output `BLOCK` → `block_reason: output_guardrail_blocked`.

### Limitations

- Regex PII and heuristic NER only — no spaCy/Presidio enterprise NER packs (E6.1 planned)
- Heuristic NER covers Latin-script capitalized names and US-style street suffixes; international addresses and non-Latin names are out of scope
- Custom enterprise identifiers use E6.2 `dlp.custom_patterns[]`, not NER
- No vault integration
- URL scanner uses structural rules, not phishing reputation feeds

See [MVP scope and gaps](#mvp-scope-and-gaps).

---

## The threat

Even when ACL (Guardrail 1) correctly limits *which* documents a user can retrieve, authorized content may still contain data that should not flow to an external LLM provider or persist in chat logs:

```text
HR Payroll Summary — Q1 (CONFIDENTIAL)

Total payroll disbursement: $4.2M across 128 employees.

Employee SSN on file example format: 123-45-6789 (redacted in exports).

Employee SIN on file example format: 046-454-286 (redacted in exports).

AWS backup key: AKIAIOSFODNN7EXAMPLE
```

A naive RAG stack may:

- Send the raw SSN, SIN, and API key in the prompt to a third-party model
- Summarize or repeat those values in the assistant reply
- Log full chunk text in observability tools without redaction

The demo corpus includes this pattern in document `hr-payroll` (`config/sample_documents.json`), restricted to `hr` and `executives` groups.

---

## Pipeline placement

DLP is **not** a separate HTTP step. It runs inside the shared input guardrail pipeline (`scan_input()`), after Guardrail 3's injection scanner and before context is packed for the LLM.

```text
scan_input(user_query)          ← P1 (Guardrails 2+3 on query)
       │
       ▼
store.search()  (Guardrail 1 — ACL filter)
       │
       ▼
for each chunk:
  scan_input()
    ├─ PromptInjectionScanner   ← Guardrail 3
    ├─ URLThreatScanner         ← Guardrail 2 (this doc)
    ├─ PIIScanner               ← Guardrail 2
    ├─ PIINERScanner            ← Guardrail 2 (E3.1, if dlp.enable_ner)
    └─ SecretsScanner           ← Guardrail 2
       │
       ▼
sanitized chunks → build_messages()
       │
       ▼
LLMClient.chat()
       │
       ▼
scan_output()                   ← Guardrail 2 (output DLP)
       │
       ▼
verify_citations()              ← Guardrail 4
```

**Key modules:**

| Module | Role |
|--------|------|
| `scanners/pii.py` | Email, phone, SSN, SIN, credit card redaction |
| `scanners/pii_ner.py` | Person name and street address redaction (E3.1) |
| `scanners/secrets.py` | API keys, tokens, private keys redaction |
| `scanners/url_threat.py` | Cloud metadata, private IP, allowlist violations |
| `guardrails/input_pipeline.py` | Orchestrates scanners, risk scoring, audit on chunks |
| `guardrails/output_pipeline.py` | Same scanners on LLM response text |
| `guardrails/risk_scoring.py` | `aggregate_risk()`, `decide()` |

---

## Scanner 1 — PII (`PIIScanner`)

Enabled when `policy.input.redact_pii` is `true` (default). Each match is **replaced** in `sanitized_text` and recorded as a finding.

| Category | Pattern (summary) | Replacement | Severity |
|----------|-------------------|-------------|----------|
| `email` | Standard email addresses | `[REDACTED_EMAIL]` | 0.3 |
| `phone` | US-style phone numbers | `[REDACTED_PHONE]` | 0.3 |
| `ssn` | `NNN-NN-NNNN` (US Social Security) | `[REDACTED_SSN]` | 0.7 |
| `sin` | `NNN-NNN-NNN` (Canadian Social Insurance; also spaces or dots) | `[REDACTED_SIN]` | 0.7 |
| `credit_card` | 13–19 digits passing Luhn check | `[REDACTED_CC]` | 0.5 |

Findings store a **masked snippet** (first/last two chars visible) for audit, not the full value. Audit Log Findings and Detail use operator names (**SSN**, **SIN**, **Name**), not snake_case `ssn` / `sin` / `person_name`.

**Typical payroll demo behavior:** SSN or SIN severity 0.7 → risk below default `block_threshold` (0.8) → chunk **passes** with redacted text. The LLM never sees `123-45-6789` or `046-454-286`; it sees `[REDACTED_SSN]` or `[REDACTED_SIN]`.

**Ask vs value:** `PIIScanner` only matches **values** in text. A query like “List all employee SSNs” or “List all employee SINs” contains no digits, so DLP does not block it. Query-intent blocking for dump asks is Guardrail 3 category `pii_exfiltration` (SSN / SIN / PII wording — not names); see [GUARDRAIL_3_INJECTION.md](GUARDRAIL_3_INJECTION.md).

### SSN vs SIN

US SSN and Canadian SIN are different national IDs. The scanner must not report SSN when the value is a SIN.

| Shape | Nearby wording | Category | Audit Findings / Detail |
|-------|----------------|----------|-------------------------|
| `NNN-NN-NNNN` | `SSN` / `social security`, or none | `ssn` | **SSN (PHI)** / `… SSN` |
| `NNN-NN-NNNN` | `SIN` / `social insurance` (and not SSN) | `sin` | **SIN (PHI)** / `… SIN` |
| `NNN-NNN-NNN` (hyphens, spaces, or dots) | any | `sin` | **SIN (PHI)** / `… SIN` |

Demo values: US SSN `123-45-6789`; CRA fictitious SIN `046-454-286`. Query Lab **PHI sample** includes both so the query-scan row shows **SSN (PHI)** and **SIN (PHI)**. Payroll chunks in `config/sample_documents.json` include both formats; a payroll *question* with no digits still stamps PHI on the **Retrieved document** scan, not on the **Query** scan.

The two regex PII detectors in Audit charts are **Emails, phones, SSN, SIN, cards** (`pii`) and **Names and addresses** (`pii_ner`).

---

## Scanner 2 — Secrets (`SecretsScanner`)

Enabled when `policy.input.redact_secrets` is `true` (default). Matches are redacted to category-specific tokens.

| Category | Example pattern | Replacement | Severity |
|----------|-----------------|-------------|----------|
| `openai_api_key` | `sk-…` (20+ chars) | `[REDACTED_OPENAI_API_KEY]` | 0.95 |
| `anthropic_api_key` | `sk-ant-…` | `[REDACTED_ANTHROPIC_API_KEY]` | 0.95 |
| `aws_access_key` | `AKIA…` (16 chars) | `[REDACTED_AWS_ACCESS_KEY]` | 0.95 |
| `github_pat` | `ghp_…` | `[REDACTED_GITHUB_PAT]` | 0.95 |
| `slack_token` | `xoxb-…` / similar | `[REDACTED_SLACK_TOKEN]` | 0.9 |
| `private_key` | `-----BEGIN … PRIVATE KEY-----` | `[REDACTED_PRIVATE_KEY]` | **1.0** |
| `jwt_token` | Three-part JWT shape | `[REDACTED_JWT_TOKEN]` | 0.6 |
| `credential_assignment` | `password: …` / `api_key=…` (16+ chars) | `[REDACTED_CREDENTIAL_ASSIGNMENT]` | 0.7 |

High-severity secrets (≥ 0.95) usually produce risk ≥ 0.8 → **`BLOCK`** — the chunk is excluded from LLM context entirely rather than partially redacted.

---

## Scanner 3 — URL threats (`URLThreatScanner`)

Runs on every chunk **before** PII/secrets scanners. Unlike PII and secrets, this scanner **does not redact URLs** — it only adds findings. The original URL text remains in `sanitized_text` unless the chunk is blocked by aggregate risk.

| Category | Trigger | Severity |
|----------|---------|----------|
| `cloud_metadata_url` | Host is `169.254.169.254`, `metadata.google.internal`, etc. | 1.0 |
| `denied_domain` | Host on `network.denied_domains[]` (subdomains match) | 0.9 |
| `private_ip_url` | URL host is private, loopback, link-local, or reserved IP | 0.85 |
| `domain_not_allowlisted` | `network.allowed_domains` is non-empty and host not listed | 0.5 |

Default `policy.yaml` sets `network.allowed_domains: []` (allowlist disabled) and `block_private_ranges: true`.

Poisoned-ticket URLs such as `http://evil.example/phish` are flagged only if they match the above rules (e.g. not on a denylist by default). Injection handling for that demo is primarily Guardrail 3 — see [GUARDRAIL_3_INJECTION.md](GUARDRAIL_3_INJECTION.md).

**CHALLENGE handling:** Mid-risk DLP findings may become effective `BLOCK` when `input.challenge_mode: block` (default). See [P1_CHALLENGE_MODE.md](P1_CHALLENGE_MODE.md).

---

## Scanner 4 — NER PII (`PIINERScanner`)

**NER-based DLP** here means: detect **named entities** (person names, street addresses) in free text and **redact** them before the LLM sees the content or before the answer is returned. This complements regex PII (`PIIScanner`), which handles structured formats like SSNs and credit cards but cannot reliably catch arbitrary person names.

### What `dlp.enable_ner` controls

| Setting | Type | Default (code) | Effect |
|---------|------|----------------|--------|
| `dlp.enable_ner` | `bool` | `true` | When `true`, run `PIINERScanner` in `scan_input()` and `scan_output()` |
| API knob name | — | — | `dlp_enable_ner` in `PATCH /admin/policy-knobs` (maps to `dlp.enable_ner`) |

When `dlp.enable_ner: false`, person names and addresses are **not** redacted by the NER scanner. Regex PII (`redact_pii`) and secrets (`redact_secrets`) still run independently.

**Requires:** `input.redact_pii: true` on the input path for the full DLP stack (regex + NER). Output path always runs NER when enabled.

### Implementation (`scanners/pii_ner.py`)

`PIINERScanner` uses lightweight heuristics — **no spaCy, Presidio, or other ML dependency**:

1. **Address pass** (runs first): US-style street pattern (`\d{1,5} … Street|St|Ave|…`) → `[REDACTED_ADDRESS]`
2. **Person-name pass**: 2–4 capitalized tokens (`Jane Martinez`) with blocklists for weekdays, months, doc titles, city names, and common false positives

| Category | Replacement | Severity | Audit label (`dlp.labels`) |
|----------|-------------|----------|----------------------------|
| `person_name` | `[REDACTED_PERSON_NAME]` | 0.45 | `PHI` |
| `address` | `[REDACTED_ADDRESS]` | 0.50 | `PHI` |

Labels are applied by `scanners/dlp_labels.py` when `dlp.labels` includes `PHI`.

### Worked examples

**Person name (payroll demo):**

```text
Payroll lead contact: Jane Martinez (employee ID 4421).
```

| Finding | Severity | Sanitized |
|---------|----------|-----------|
| `person_name` | 0.45 | `Payroll lead contact: [REDACTED_PERSON_NAME] (employee ID 4421).` |

**Street address:**

```text
Our headquarters is at 100 Market Street, San Francisco.
```

| Finding | Severity | Sanitized |
|---------|----------|-----------|
| `address` | 0.50 | `Our headquarters is at [REDACTED_ADDRESS], San Francisco.` |

**False positive avoided (weekday blocklist):**

```text
Support is available Monday through Friday.
```

**Expected:** No NER findings.

### Disable NER only

```yaml
dlp:
  enable_ner: false
  labels: [PCI, PHI]   # unchanged — labels still apply to regex PII/secrets
```

Reload: `POST /admin/reload-policy`.

**Deep dive:** [E3_1_NER_DLP.md](../../../ENTERPRISE.md) · **Tests:** `pytest -q tests/test_e3.py -k pii_ner`

---

## Risk scoring and verdicts

`scan_input` reports one `risk_score` across all findings:

```text
risk = min(1.0, max(severity) + bump)
```

- `bump` = up to 0.15 when multiple findings have severity ≥ 0.7

**BLOCK** is decided from injection, secrets, and URL findings only (`findings_for_input_block`). PII, NER, and `kind: dlp` custom patterns are redact-and-pass: they cannot `BLOCK`. If reported risk is at least `challenge_threshold` and nothing block-eligible fired, the verdict is `CHALLENGE` (sanitized text may still reach the LLM when `challenge_mode` is `allow` or `audit_only`).

Compared to `policy.yaml` thresholds:

| Threshold | Default | Verdict |
|-----------|---------|---------|
| `input.challenge_threshold` | 0.4 | `CHALLENGE` — sanitized text may still reach LLM; flagged in audit |
| `input.block_threshold` | 0.8 | `BLOCK` — chunk excluded from LLM context |

| Scenario | Typical outcome |
|----------|-----------------|
| Payroll chunk with SSN and SIN | Redacted; `CHALLENGE` (not `BLOCK`, even when SSN+SIN bump risk to 0.80) |
| Chunk with OpenAI key or private key | Redacted + often `BLOCK` (severity ≥ 0.95) |
| Chunk with cloud metadata URL | Often `BLOCK` (severity 1.0) |

`pipeline.py` behavior:

- `BLOCK` → chunk shown as `[blocked chunk]` in API response; not passed to `build_messages()`
- All chunks blocked → static answer, `blocked: true`, `block_reason: "all_chunks_blocked"`, **no LLM call**

Every `scan_input` run records an audit event (`kind: scan_input`) with findings and decision.

---

## Output DLP (`scan_output`)

After the LLM generates an answer, `scan_output()` runs **before** citation auditing:

1. `PIIScanner`
2. `CustomPatternScanner` (E6.2 `kind: dlp` / `kind: secret`)
3. `PIINERScanner` (if `dlp.enable_ner`)
4. `SecretsScanner` (built-in + `kind: secret` custom patterns)

This catches cases where the model **re-introduces** sensitive patterns not present in sanitized context, or echoes redacted placeholders incorrectly. Output uses separate thresholds (`output.challenge_threshold` 0.5, `output.block_threshold` 0.85). Audit events use `kind: scan_output`.

---

## Configuration

From `config/policy.yaml`:

**Input (chunk) DLP:**

| Key | Default | Purpose |
|-----|---------|---------|
| `redact_pii` | `true` | Run `PIIScanner` on retrieved chunks |
| `redact_secrets` | `true` | Run `SecretsScanner` on retrieved chunks |
| `challenge_threshold` | `0.4` | Minimum risk for `CHALLENGE` |
| `block_threshold` | `0.8` | Minimum risk for `BLOCK` |

**Network (URL scanner, shared input + output):**

| Key | Default | Purpose |
|-----|---------|---------|
| `allowed_domains` | `[]` | If non-empty, flag URLs whose host is not allowlisted |
| `denied_domains` | `[]` | Flag URLs whose host matches a denied domain (subdomains included) |
| `block_private_ranges` | `true` | Flag URLs targeting private/loopback IPs |

**Operator UI:** Policy Viewer/Admin → **Edit → Injection & DLP** → `network.denied_domains[]` (one domain per line) via `PATCH /admin/policy-knobs` with `network_denied_domains`. Then **Query Lab** with the URL in the query to confirm a block ([a8 UI_TESTING](../README.md)). **`allowed_domains[]` and `block_private_ranges` shipped in Policy UI** (polish Tier 1, UI `e5-v21+`). See [TC-E5-210–211](../../../ENTERPRISE.md#tc-e5-210--network-allowlist-editable-in-policy-ui-shipped).

**DLP policy (`dlp.*`):**

| Key | Default (code) | Purpose |
|-----|----------------|---------|
| `enable_ner` | `true` | Run `PIINERScanner` for person names and addresses (E3.1) |
| `labels` | `[PCI, PHI]` | Attach PCI/PHI labels to findings in audit export (E3.2) |
| `custom_patterns` | `[]` | E6.2 org-specific regex (`kind: dlp` or `kind: secret`) |

**Operator UI:** Policy Viewer/Admin → **DLP** group → `dlp_enable_ner` toggle and `dlp_labels` via `PATCH /admin/policy-knobs`. See [E5_2_POLICY_FORMS.md](../../../ENTERPRISE.md).

**Custom enterprise secrets:** Add patterns to `dlp.custom_patterns[]` with `kind: secret` — same ReDoS validation as E6.2; findings use `scanner: secrets`. For `dlp` vs `secret` guidance, see [E6_2_CUSTOM_PATTERNS.md § Pattern kinds](../../../ENTERPRISE.md#pattern-kinds-dlp-vs-secret).

Reload without restart: `POST /admin/reload-policy` (see [ARCHITECTURE.md § Configuration](../README.md#configuration-reference)).

---

## Demo scenario (payroll SSN and SIN)

**Query:** *"What SSN format is on file for payroll?"* or *"What SIN format is on file for payroll?"*  
**Token:** `hr-demo-token` (can retrieve `hr-payroll`)

```bash
curl -s http://localhost:8090/v1/query \
  -H "Authorization: Bearer hr-demo-token" \
  -H "Content-Type: application/json" \
  -d '{"query":"What SSN format is on file for payroll?","top_k":4}' | python3 -m json.tool
```

**Expected:**

- `hr-payroll` chunk in response
- `chunks[].text` shows `[REDACTED_SSN]` and `[REDACTED_SIN]` — raw `123-45-6789` and `046-454-286` must **not** appear in sanitized chunk text sent to the model
- LLM may still answer using redacted context (e.g. describing the redaction token or payroll totals)
- Audit **Retrieved document** scan Findings: **SSN (PHI)**, **SIN (PHI)**, **Name (PHI)** when NER is on. The Query scan for these questions has no digits, so it does not stamp SSN/SIN.

**ACL contrast (no DLP path):** same query with `employee-demo-token` never retrieves `hr-payroll` — Guardrail 1 blocks at search; no LLM call.

### Demo scenario (payroll person name, E3.1)

**Query:** *"Who is the payroll lead contact?"*  
**Token:** `hr-demo-token`  
**Precondition:** `dlp.enable_ner: true`

```bash
curl -s http://localhost:8090/v1/query \
  -H "Authorization: Bearer hr-demo-token" \
  -H "Content-Type: application/json" \
  -d '{"query":"Who is the payroll lead contact?","top_k":4}' | python3 -m json.tool
```

**Expected:**

- `hr-payroll` chunk in response
- `chunks[].text` shows `[REDACTED_PERSON_NAME]` — raw `Jane Martinez` must **not** appear
- Audit export includes `findings[].label: "PHI"` for `person_name` category

With `dlp.enable_ner: false`, the name may appear in sanitized chunk text (regex PII does not catch names).

**Audit:**

```bash
curl -s "http://localhost:8090/audit/recent?limit=10" \
  -H "Authorization: Bearer hr-demo-token" | python3 -m json.tool
```

**Expected:** Recent `scan_input` events with `pii` findings; `detail` names **SSN** and/or **SIN** (API `findings[].category` remains `ssn` / `sin`).

Full walkthrough: [ARCHITECTURE.md § Guardrail Demo Walkthrough](../README.md#guardrail-demo-walkthrough).

---

## UI walkthrough

**Detailed test cases (label B):** [test-plans/GUARDRAIL_TEST_PLAN.md § B](../../../ENTERPRISE.md#b--semantic-dlp) (TC-GR-B-001–005).

| Step | UI action | Expected |
|------|-----------|----------|
| 1 | **Query Lab** → `hr-demo-token` → **Payroll sample** → **Run Query** | Retrieved chunks show `[REDACTED_SSN]` / `[REDACTED_SIN]` if payroll text includes those patterns |
| 2 | Inspect **Retrieved Chunks** panel | `scan_verdict` on each chunk; blocked chunks show `[blocked chunk]` |
| 3 | **Audit Log** → refresh | `scan_input` events with `pii` / `secrets` findings |
| 4 | **Query Lab** → **PHI / PCI / GDPR / INTERNAL sample** → **Run Query** | Audit Log filter `scan_input` / Where **Query**: Findings show **SSN (PHI)**, **SIN (PHI)**, **Name (PHI)**; PCI / GDPR / INTERNAL samples stamp those labels. Drawer **Label** column. GDPR needs the imported pack. |
| 5 | **Documents & Ingest** → ingest doc with fake API key in body | With default `challenge_mode: block`, ingest rejected (422) — see [P1_INGEST_SECURITY.md](P1_INGEST_SECURITY.md) |

Payroll sample (“What is the Q1 payroll total?”) does **not** put an SSN or SIN in the query. PHI on that path appears when **retrieved chunk** text is scanned (Where **Retrieved document**). Asking “list all SSNs” or “list all SINs” is injection (`pii_exfiltration`), not a DLP label. Details: [E3_2_DLP_LABELS.md](../../../ENTERPRISE.md) · [a1 UI_TESTING](../../../ENTERPRISE.md#step-4--query-lab-samples--audit-log-labels).

---

## Tests

| Test | File | What it checks |
|------|------|----------------|
| `test_pii_redacts_email` | `tests/test_rag_protection.py` | Email → `[REDACTED_EMAIL]` |
| `test_secrets_redacts_openai_key` | `tests/test_rag_protection.py` | OpenAI key → `[REDACTED_OPENAI_API_KEY]` |
| `test_pii_ner_redacts_person_name` | `tests/test_e3.py` | `Jane Martinez` → `[REDACTED_PERSON_NAME]` |
| `test_pii_ner_redacts_street_address` | `tests/test_e3.py` | `100 Market Street` → `[REDACTED_ADDRESS]` |
| `test_pii_ner_skips_weekday_false_positive` | `tests/test_e3.py` | Weekdays not flagged as names |

Run:

```bash
cd rag-protection-proxy
pytest -q tests/test_rag_protection.py -k "pii or secrets"
pytest -q tests/test_e3.py -k pii_ner
pytest -q tests/test_p1.py -k ingest
```

---

## MVP scope and gaps

| Shipped | Not yet implemented |
|---------|---------------------|
| Regex PII scanner (email, phone, SSN, SIN, Luhn-validated cards) | spaCy/Presidio enterprise NER backend (E6.1) |
| **Heuristic NER** person names + US street addresses (`dlp.enable_ner`, E3.1) | International addresses; non-Latin names |
| **PCI/PHI audit labels** on findings (`dlp.labels`, E3.2) | Per-tenant label packs |
| Regex secrets scanner (common key formats) + **E6.2 `kind: secret` custom patterns** | Vault integration |
| URL threat heuristics (metadata, private IP, **denied_domains**, optional allowlist) | Full URL reputation / phishing feeds (E6.4) |
| `scan_input` on query, chunks, ingest + `scan_output` on answers | Hash/tokenize modes; reversible tokenization |
| Redaction tokens in sanitized text | ML-assisted severity scoring |
| CHALLENGE mode policy (v1 P1) | — |

**Enterprise next:** Presidio/spaCy NER backend for fewer false positives. See [E6_1_PRESIDIO_NER.md](../../../ENTERPRISE.md), [IMPLEMENTATION_STATUS.md](../README.md), and [NEXT_STEPS.md](../README.md).

---

## Related documentation

| Topic | Document |
|-------|----------|
| Guardrails index | [README.md](README.md) |
| Detection map (all guardrails) | [DETECTION_OVERVIEW.md](DETECTION_OVERVIEW.md) |
| User-query + ingest DLP paths | [P1_USER_QUERY_GUARDRAILS.md](P1_USER_QUERY_GUARDRAILS.md) · [P1_INGEST_SECURITY.md](P1_INGEST_SECURITY.md) |
| CHALLENGE policy | [P1_CHALLENGE_MODE.md](P1_CHALLENGE_MODE.md) |
| Document ACL (pre-retrieval) | [GUARDRAIL_1_ACL.md](GUARDRAIL_1_ACL.md) |
| Injection shielding (shared pipeline) | [GUARDRAIL_3_INJECTION.md](GUARDRAIL_3_INJECTION.md) |
| Citation and output guardrails | [GUARDRAIL_4_CITATION.md](GUARDRAIL_4_CITATION.md) |
| Payroll sample document | [KNOWLEDGE_BASE.md](../README.md) |
| NER DLP deep dive (E3.1) | [E3_1_NER_DLP.md](../../../ENTERPRISE.md) |
| DLP audit labels (E3.2) | [E3_2_DLP_LABELS.md](../../../ENTERPRISE.md) |
| Module map | [TECH_STACK.md](../../product/TECH_STACK.md) |
