# RAG Red-Team Engagement — Executive Summary

**Engagement:** {{ENGAGEMENT}}  
**Generated:** {{GENERATED_AT}}  
**Target:** {{BASE_URL}}

## Summary

| Metric | Value |
|--------|------:|
| Scenarios run | {{TOTAL}} |
| Passed | {{PASSED}} |
| Failed | {{FAILED}} |

## Scenario scorecard

| ID | Title | Result | Risk | Notes |
|----|-------|--------|-----:|-------|
{{SCORECARD}}

## Findings (ranked by risk)

{{FINDINGS}}

## Recommendations

1. Remediate any **FAIL** scenarios before production sign-off.
2. Attach `audit.ndjson` from this run as the evidence appendix.
3. Use [POC pass criteria](../../ENTERPRISE.md) for the follow-on 2-week RAG Protection POC.

## Boundary

This engagement red-teams the **RAG pipeline** (retrieval, guardrails, ACL, audit) — not model weights. Scenario outcomes depend on the deployed policy and corpus at run time.
