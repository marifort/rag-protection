# rag-redteam — Packaged RAG red-team harness (Lab 5)

Repeatable, evidence-based RAG attack scenarios for consulting engagements ($10K–$20K Tier 1 SKU). Black-box client against any deployed proxy — local demo stack or customer staging.

**Docs:** [product overview](../../docs/ce/README.md) · [Tutorial 08 §16](../../ENTERPRISE.md#part-16--lab-5-packaged-red-team-harness-rank-1) · [talk track](../../ENTERPRISE.md) · [demo script](../../ENTERPRISE.md) · [test plan](../../ENTERPRISE.md) · [SPEC](../../ENTERPRISE.md)

## Quick start

```bash
# Proxy running (e.g. bash tools/docker_start.sh)
export RAG_PROTECTION_ADMIN_KEY=rag-admin-demo-key
tools/rag-redteam run --all --base-url http://localhost:8090
```

Artifacts land in `tools/redteam/artifacts/engagement/`:

- `results.json` — PASS/FAIL per scenario
- `audit.ndjson` — evidence appendix
- `report.md` — executive summary

Exit `0` when all scenarios pass; `1` on any FAIL (CI-friendly).

## Scenarios

| File | Attack | Expected control |
|------|--------|------------------|
| `indirect_injection_ticket.yaml` | Poisoned ticket in corpus | Injection block |
| `corpus_poison_hr_policy.yaml` | Fake HR policy at ingest | Injection block |
| `acl_bypass_attempt.yaml` | Payroll as employee | Pre-retrieval ACL |
| `dlp_exfil_ssn_query.yaml` | “List all employee SSNs…” | `pii_exfiltration` intent **block** |
| `dlp_exfil_pii_query.yaml` | “List all employee PII…” | `pii_exfiltration` intent **block** |
| `dlp_exfil_employees_query.yaml` | “List all employees…” | Control does **not** fire (`safe_answer`) |
| `ungrounded_answer.yaml` | Figure not in corpus | Citation fail |

`pii_exfiltration` matches dump verbs near `ssn` / `social security number` / `pii` / `personal identifiable information` only — not names or generic “employees”. Details: [GUARDRAIL_3_INJECTION.md](../../docs/ce/security/GUARDRAIL_3_INJECTION.md).

## Options

```bash
tools/rag-redteam run --scenario acl_bypass_attempt --out /tmp/rt-demo
tools/rag-redteam run --scenario tools/redteam/scenarios/dlp_exfil_ssn_query.yaml
```

## Note: extraction monitor vs scenario ingest

Many scenarios share `employee-demo-token` (`alice.engineer`). Repeated runs accumulate in the proxy’s **corpus-extraction** sliding window (`kind=extraction_suspected`). That finding is about **subject retrieval coverage**, not the scenario’s `setup.ingest` document_id/title/content — changing those fields does not clear it.

Reset / verify:

- Live window: wait `extraction.window_seconds` or restart the proxy, then confirm `GET /admin/extraction/watch` shows `subjects: []`.
- Audit Log rows are historical — they do **not** disappear when the window ages out.
- Coverage can re-fire on a **single** new query if that retrieval alone meets `elevated_coverage` / `severe_coverage` (`min_window_queries` applies only to breadth/novelty).
- Knobs live in the active policy (`data/policy.yaml` under Docker); reload with `POST /admin/reload-policy`.

Full criteria and operator steps: [CE #2](../../docs/ce/features/02-extraction-monitor.md#severity-criteria) · [Operator notes](../../docs/ce/features/02-extraction-monitor.md#operator-notes-tuning--demos).

## Tests

```bash
pytest tools/redteam/tests -q
```
