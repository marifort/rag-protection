"""Output guardrail pipeline — scrub LLM responses before returning to users."""

from __future__ import annotations

import time
from typing import List

from rag_protection_proxy.audit import audit_debug_active, build_audit_debug_preview, record
from rag_protection_proxy.config import Policy, filter_custom_patterns_by_kind
from rag_protection_proxy.guardrails.risk_scoring import aggregate_risk, decide
from rag_protection_proxy.models import AuditEvent, Finding, OutputScanRequest, OutputScanResponse, Verdict
from rag_protection_proxy.scanners import (
    CustomPatternScanner,
    PIINERScanner,
    PIIScanner,
    PromptInjectionScanner,
    SecretsScanner,
    URLThreatScanner,
)
from rag_protection_proxy.scanners.dlp_labels import apply_dlp_labels, format_finding_categories


def scan_output(req: OutputScanRequest, policy: Policy) -> OutputScanResponse:
    start = time.perf_counter()

    text = req.text
    findings: List[Finding] = []
    redactions = 0

    for scanner in (
        SecretsScanner(),
        PIIScanner(),
        URLThreatScanner(
            allowed_domains=policy.network.allowed_domains,
            denylist=policy.network.denied_domains,
            block_private_ranges=policy.network.block_private_ranges,
        ),
    ):
        result = scanner.scan(text)
        text = result.sanitized_text
        findings.extend(result.findings)
        redactions += result.redactions

    dlp_patterns = filter_custom_patterns_by_kind(policy.dlp.custom_patterns, "dlp")
    if dlp_patterns:
        result = CustomPatternScanner(dlp_patterns).scan(text)
        text = result.sanitized_text
        findings.extend(result.findings)
        redactions += result.redactions

    secret_patterns = filter_custom_patterns_by_kind(policy.dlp.custom_patterns, "secret")
    if secret_patterns:
        result = CustomPatternScanner(secret_patterns).scan(text)
        text = result.sanitized_text
        findings.extend(result.findings)
        redactions += result.redactions

    if policy.dlp.enable_ner:
        result = PIINERScanner().scan(text)
        text = result.sanitized_text
        findings.extend(result.findings)
        redactions += result.redactions

    findings = apply_dlp_labels(findings, policy.dlp.labels)

    risk = aggregate_risk(findings)
    dec = decide(risk, policy.output.challenge_threshold, policy.output.block_threshold)
    reason = f"output scan: {format_finding_categories(findings) or 'clean'}"

    verdict = Verdict(decision=dec, risk_score=risk, reason=reason, findings=findings)

    record(AuditEvent(
        timestamp=time.time(),
        kind="scan_output",
        decision=dec,
        risk_score=risk,
        subject=req.subject,
        tenant_id=req.tenant_id,
        findings=findings,
        detail=reason,
        debug=build_audit_debug_preview(
            enabled=audit_debug_active(policy, request_flag=bool(req.context.get("audit_debug"))),
            max_preview_chars=policy.audit.debug_max_preview_chars,
            output_text=text,
            redactions=redactions or None,
        ),
    ))

    _ = time.perf_counter() - start
    return OutputScanResponse(verdict=verdict, sanitized_text=text, redactions=redactions)
