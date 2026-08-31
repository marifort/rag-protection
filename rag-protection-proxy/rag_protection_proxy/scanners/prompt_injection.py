"""Indirect and direct prompt-injection heuristics.

This module defines regex patterns, structural stripping (hidden Unicode,
HTML comments, javascript: markdown links), and base64 payload checks.
Each match emits a Finding (category + severity).

It is one scanner inside scan_input() (guardrails/input_pipeline.py), shared
by user queries, retrieved chunks, and ingest. Risk aggregation and
BLOCK/CHALLENGE/ALLOW decisions are in guardrails/risk_scoring.py; ingest
disposition (ok / quarantined / rejected) is in guardrails/ingest.py.

Docs: docs/guardrails/GUARDRAIL_3_INJECTION.md
      docs/guardrails/P1_INGEST_SECURITY.md#how-malicious-content-is-detected
"""

from __future__ import annotations

import base64
import binascii
import re
from typing import Dict, List, Optional, Tuple

from rag_protection_proxy.config import InjectionPattern, default_injection_categories
from rag_protection_proxy.models import Finding
from rag_protection_proxy.scanners.base import Scanner, ScannerResult
from rag_protection_proxy.scanners.custom_patterns import _safe_finditer

_BUILTIN_PATTERNS: List[Tuple[re.Pattern[str], str, float, str]] = [
    (re.compile(r"\b(ignore|disregard|forget)\b[^.\n]{0,40}\b(previous|prior|above|earlier|all)\b[^.\n]{0,40}\b(instructions?|prompts?|rules?|directives?)\b", re.I),
     "instruction_override", 0.9, "Direct attempt to override prior instructions."),
    (re.compile(
        r"\b(override|bypass|abandon|cancel)\b[^.\n]{0,40}\b"
        r"(safety|content policy|training constraints|rules?|constraints?|guidelines?)\b",
        re.I,
    ),
     "instruction_override", 0.85, "Attempt to override safety or policy constraints."),
    (re.compile(
        r"\b(stop following|do not follow|discard prior|ignore the developer)\b[^.\n]{0,60}\b"
        r"(instructions?|prompt|context|rules?)\b",
        re.I,
    ),
     "instruction_override", 0.85, "Attempt to discard prior instructions or context."),
    (re.compile(r"\b(you are|act as|pretend to be|roleplay as|from now on you('re| are))\b[^.\n]{0,60}\b(admin|root|developer|sudo|jailbroken|dan|unfiltered)\b", re.I),
     "role_hijack", 0.85, "Attempt to hijack the assistant's role."),
    (re.compile(
        r"\b(roleplay as|assume the identity|impersonate|become a privileged|switch to maintenance|"
        r"enter developer debug|emergency override|transform into)\b[^.\n]{0,60}\b"
        r"(unrestricted|auditor|operator|administrator|override|unconstrained|guardrails?|access controls?)\b",
        re.I,
    ),
     "role_hijack", 0.85, "Attempt to assume a privileged or unrestricted role."),
    (re.compile(r"\b(system|developer)\s*[:>]\s*", re.I),
     "fake_system_prompt", 0.7, "Embedded fake system/developer prefix."),
    (re.compile(r"<\s*\|?\s*(system|im_start|im_end|s)\s*\|?\s*>", re.I),
     "chat_template_injection", 0.85, "Chat-template control token injection."),
    (re.compile(r"\{\{#system\}\}|<\|endoftext\|><\|start\|>", re.I),
     "chat_template_injection", 0.85, "Chat-template control token injection."),
    (re.compile(r"\b(send|forward|exfiltrate|leak|email|post|upload)\b[^.\n]{0,40}\b(to|at)\b\s+[\w.+-]+@[\w.-]+", re.I),
     "exfiltration_directive", 0.85, "Instruction to send data to an external address."),
    (re.compile(r"\b(upload|post|send|exfiltrate|push|transmit|copy|leak)\b[^.\n]{0,80}\bhttps?://", re.I),
     "exfiltration_directive", 0.85, "Instruction to send data to an external URL."),
    (re.compile(r"\b(leak|exfiltrate|export)\b[^.\n]{0,40}\b(unauthorized|external)\b", re.I),
     "exfiltration_directive", 0.8, "Instruction to leak data externally."),
    (re.compile(r"\b(curl|wget|fetch|http\.get)\b\s+[\"']?https?://", re.I),
     "exfiltration_directive", 0.7, "Embedded outbound HTTP call instruction."),
    (re.compile(r"\b(delete|drop|truncate|wipe|destroy|rm\s+-rf)\b[^.\n]{0,40}\b(database|table|all|everything|users|files?)\b", re.I),
     "destructive_action", 0.9, "Destructive action directive."),
    (re.compile(
        r"\b(reveal|print|show|leak|dump|output|return)\b[^.\n]{0,40}\b"
        r"(api[\s_-]?keys?|secrets?|passwords?|tokens?|env(ironment)?(\s+vars?)?|system\s+prompts?)\b",
        re.I,
    ),
     "secret_extraction", 0.85, "Attempt to extract credentials or secrets."),
    (re.compile(
        r"\b(list|display|read|extract)\b[^.\n]{0,40}\b"
        r"(credentials?|environment variables|private keys?|/etc/shadow)\b",
        re.I,
    ),
     "secret_extraction", 0.85, "Attempt to extract credentials or secrets."),
    (re.compile(
        r"\b(list|dump|export|extract|reveal|show|give)\b[^.\n]{0,60}\b"
        r"(employee\s+)?"
        r"(ssns?|sins?|social\s*security\s*numbers?|social\s*insurance\s*numbers?|"
        r"pii|personal\s+identifiable\s+information)\b",
        re.I,
    ),
     "pii_exfiltration", 0.85, "Request to dump SSN/SIN/PII values."),
    (re.compile(r"\b(decode|base64|rot13|hex)\b[^.\n]{0,40}\b(then|and)\b[^.\n]{0,40}\b(execute|run|do|follow|obey)\b", re.I),
     "obfuscated_payload", 0.8, "Instruction to decode-then-execute."),
    (re.compile(
        r"\b(encoded command|rot13 message|hex string|shell command hidden|embedded directives|obfuscated block)\b",
        re.I,
    ),
     "obfuscated_payload", 0.75, "Reference to an obfuscated or encoded attack payload."),
    (re.compile(
        r"\b(decode|decrypt|unpack|interpret|reverse|reassemble)\b[^.\n]{0,40}\b"
        r"(instructions?|directives?|payload|command)\b",
        re.I,
    ),
     "obfuscated_payload", 0.8, "Instruction to decode or unpack hidden directives."),
]

_BASE64_BLOB_RE = re.compile(
    r"(?:^|(?<![A-Za-z0-9+/]))([A-Za-z0-9+/]{40,}={0,2})(?![A-Za-z0-9+/])"
)

_HIDDEN_CHAR_RE = re.compile(
    r"[\u200B-\u200D\uFEFF\u202A-\u202E]|[\U000E0000-\U000E007F]"
)
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
_MARKDOWN_HIDDEN_LINK_RE = re.compile(r"\[[^\]]*\]\(\s*javascript:[^)]+\)", re.I)
_SCAN_TIMEOUT_SEC = 0.25


class PromptInjectionScanner(Scanner):
    name = "prompt_injection"

    def __init__(
        self,
        strip_hidden_chars: bool = True,
        strip_html_comments: bool = True,
        decode_base64_max_len: int = 4000,
        enabled_categories: Optional[Dict[str, bool]] = None,
        extra_patterns: Optional[List[InjectionPattern]] = None,
    ) -> None:
        self.strip_hidden_chars = strip_hidden_chars
        self.strip_html_comments = strip_html_comments
        self.decode_base64_max_len = decode_base64_max_len
        self.enabled_categories = default_injection_categories()
        if enabled_categories:
            self.enabled_categories.update(enabled_categories)
        self.extra_patterns = [pattern for pattern in (extra_patterns or []) if pattern.enabled]

    def _category_enabled(self, category: str) -> bool:
        return self.enabled_categories.get(category, True)

    def scan(self, text: str) -> ScannerResult:
        if not isinstance(text, str):
            text = "" if text is None else str(text)

        findings: List[Finding] = []
        sanitized = text
        redactions = 0

        if self.strip_hidden_chars and self._category_enabled("hidden_chars"):
            new, n = _HIDDEN_CHAR_RE.subn("", sanitized)
            if n > 0:
                findings.append(Finding(
                    scanner=self.name,
                    category="hidden_chars",
                    severity=0.75,
                    detail=f"Stripped {n} invisible/zero-width/tag characters.",
                ))
                redactions += n
                sanitized = new

        if self.strip_html_comments and self._category_enabled("html_comment_injection"):
            comments = _HTML_COMMENT_RE.findall(sanitized)
            for c in comments:
                if _looks_instructional(c):
                    findings.append(Finding(
                        scanner=self.name,
                        category="html_comment_injection",
                        severity=0.75,
                        snippet=_snippet(c),
                        detail="Instructional content inside HTML comment.",
                    ))
            sanitized = _HTML_COMMENT_RE.sub("", sanitized)

        if self._category_enabled("markdown_js_link"):
            for m in _MARKDOWN_HIDDEN_LINK_RE.finditer(sanitized):
                findings.append(Finding(
                    scanner=self.name,
                    category="markdown_js_link",
                    severity=0.7,
                    snippet=_snippet(m.group(0)),
                    detail="Markdown link with javascript: scheme.",
                ))
            sanitized = _MARKDOWN_HIDDEN_LINK_RE.sub("[link removed]", sanitized)

        for regex, category, severity, detail in _BUILTIN_PATTERNS:
            if not self._category_enabled(category):
                continue
            for m in regex.finditer(sanitized):
                findings.append(Finding(
                    scanner=self.name,
                    category=category,
                    severity=severity,
                    snippet=_snippet(m.group(0)),
                    detail=detail,
                ))

        for pattern in self.extra_patterns:
            matches = _safe_finditer(pattern.regex, sanitized, _SCAN_TIMEOUT_SEC)
            for match in matches:
                findings.append(Finding(
                    scanner=self.name,
                    category=pattern.name,
                    severity=pattern.severity,
                    snippet=_snippet(match.group(0)),
                    detail=pattern.detail,
                ))

        if self._category_enabled("base64_payload") and len(sanitized) <= self.decode_base64_max_len:
            for m in _BASE64_BLOB_RE.finditer(sanitized):
                blob = m.group(1)
                try:
                    decoded = base64.b64decode(blob, validate=True).decode("utf-8", errors="ignore")
                except (binascii.Error, ValueError):
                    continue
                if _looks_instructional(decoded):
                    findings.append(Finding(
                        scanner=self.name,
                        category="base64_payload",
                        severity=0.8,
                        snippet=_snippet(decoded),
                        detail="Base64-encoded instruction-like payload.",
                    ))

        return ScannerResult(sanitized_text=sanitized, findings=findings, redactions=redactions)


def preview_custom_injection_patterns(
    text: str,
    patterns: List[InjectionPattern],
) -> ScannerResult:
    """Dry-run only custom injection patterns (built-in categories disabled)."""
    disabled = {category: False for category in default_injection_categories()}
    enabled = [pattern for pattern in patterns if pattern.enabled]
    return PromptInjectionScanner(
        strip_hidden_chars=False,
        strip_html_comments=False,
        enabled_categories=disabled,
        extra_patterns=enabled,
    ).scan(text)


def _snippet(text: str, max_len: int = 120) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= max_len else text[: max_len - 1] + "…"


def _looks_instructional(text: str) -> bool:
    lowered = text.lower()
    benign_phrases = (
        "password reset",
        "self-service",
        "office hours",
        "sales report",
        "hiring plan",
        "staging deployment",
        "delivery date",
        "revenue figure",
        "unit tests",
        "support info",
    )
    if any(phrase in lowered for phrase in benign_phrases):
        return False
    triggers = (
        "ignore", "disregard", "forget", "you are", "act as", "system:",
        "instruction", "execute", "run ", "delete", "drop ", "send to",
        "exfiltrate", "api key", "api keys", "passwords", "secret", "print", "reveal",
        "from now on", "new rule", "override", "im_start", "im_end", "jailbroken",
        "unrestricted", "guardrail", "exfil", "credential", "token",
    )
    return any(t in lowered for t in triggers)
