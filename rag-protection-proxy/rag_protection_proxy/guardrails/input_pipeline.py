"""Input guardrail pipeline — scan untrusted text before LLM context or corpus write.

Runs PromptInjectionScanner, ML injection classifier (E3.3), URLThreatScanner,
optional PII/secrets/NER scanners; aggregates findings into a risk score.
PII/NER/custom DLP findings redact and at most CHALLENGE — they cannot BLOCK.

Docs: docs/guardrails/GUARDRAIL_3_INJECTION.md
      docs/product/NEXT_STEPS.md § E3
"""

from __future__ import annotations

import time
from typing import List

from rag_protection_proxy.audit import audit_debug_active, build_audit_debug_preview, record
from rag_protection_proxy.config import Policy, filter_custom_patterns_by_kind
from rag_protection_proxy.guardrails.risk_scoring import (
    aggregate_risk,
    decide,
    findings_for_input_block,
)
from rag_protection_proxy.models import (
    AuditEvent,
    Decision,
    Finding,
    InputScanRequest,
    InputScanResponse,
    Verdict,
)
from rag_protection_proxy.scanners import (
    CustomPatternScanner,
    MLInjectionScanner,
    PIINERScanner,
    PIIScanner,
    PromptInjectionScanner,
    SecretsScanner,
    URLThreatScanner,
)
from rag_protection_proxy.scanners.dlp_labels import apply_dlp_labels, format_finding_categories


def scan_input(req: InputScanRequest, policy: Policy) -> InputScanResponse:
    start = time.perf_counter()

    injector = PromptInjectionScanner(
        strip_hidden_chars=policy.input.strip_hidden_chars,
        strip_html_comments=policy.input.strip_html_comments,
        enabled_categories=policy.input.injection_categories,
        extra_patterns=policy.input.custom_injection_patterns,
    )
    url = URLThreatScanner(
        allowed_domains=policy.network.allowed_domains,
        denylist=policy.network.denied_domains,
        block_private_ranges=policy.network.block_private_ranges,
    )

    text = req.text
    findings: List[Finding] = []
    redactions = 0

    for scanner in (injector, url):
        result = scanner.scan(text)
        text = result.sanitized_text
        findings.extend(result.findings)
        redactions += result.redactions

    if policy.input.ml_injection_enabled:
        ml = MLInjectionScanner(threshold=policy.input.ml_injection_threshold)
        result = ml.scan(text)
        text = result.sanitized_text
        findings.extend(result.findings)

    if policy.input.redact_pii:
        result = PIIScanner().scan(text)
        text = result.sanitized_text
        findings.extend(result.findings)
        redactions += result.redactions

    dlp_patterns = filter_custom_patterns_by_kind(policy.dlp.custom_patterns, "dlp")
    if dlp_patterns:
        result = CustomPatternScanner(dlp_patterns).scan(text)
        text = result.sanitized_text
        findings.extend(result.findings)
        redactions += result.redactions

    if policy.dlp.enable_ner:
        result = PIINERScanner().scan(text)
        text = result.sanitized_text
        findings.extend(result.findings)
        redactions += result.redactions

    if policy.input.redact_secrets:
        result = SecretsScanner().scan(text)
        text = result.sanitized_text
        findings.extend(result.findings)
        redactions += result.redactions

        secret_patterns = filter_custom_patterns_by_kind(policy.dlp.custom_patterns, "secret")
        if secret_patterns:
            result = CustomPatternScanner(secret_patterns).scan(text)
            text = result.sanitized_text
            findings.extend(result.findings)
            redactions += result.redactions

    findings = apply_dlp_labels(findings, policy.dlp.labels)

    risk = aggregate_risk(findings)
    if req.trusted:
        dec = Decision.ALLOW
        reason = "trusted-source (informational findings only)"
    else:
        # BLOCK uses injection/secrets/URL risk only. PII still redacts and may
        # raise CHALLENGE so audit stays visible; challenge_mode then decides
        # whether the sanitized chunk reaches the LLM.
        dec = decide(
            aggregate_risk(findings_for_input_block(findings)),
            policy.input.challenge_threshold,
            policy.input.block_threshold,
        )
        if dec != Decision.BLOCK and risk >= policy.input.challenge_threshold:
            dec = Decision.CHALLENGE
        reason = _reason_for(findings, dec)

    verdict = Verdict(decision=dec, risk_score=risk, reason=reason, findings=findings)

    record(AuditEvent(
        timestamp=time.time(),
        kind="scan_input",
        decision=dec,
        risk_score=risk,
        source=req.source,
        subject=req.subject,
        tenant_id=req.tenant_id,
        findings=findings,
        detail=reason,
        debug=build_audit_debug_preview(
            enabled=audit_debug_active(policy, request_flag=bool(req.context.get("audit_debug"))),
            max_preview_chars=policy.audit.debug_max_preview_chars,
            input_text=text,
            redactions=redactions or None,
        ),
    ))

    _ = time.perf_counter() - start
    return InputScanResponse(verdict=verdict, sanitized_text=text, redactions=redactions)


def _reason_for(findings: List[Finding], decision: Decision) -> str:
    if not findings:
        return "no findings"
    cats = format_finding_categories(findings)
    if decision == Decision.BLOCK:
        return f"blocked: {cats}"
    if decision == Decision.CHALLENGE:
        return f"sanitized + warning: {cats}"
    return f"allowed (informational): {cats}"
