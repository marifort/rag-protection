"""Custom DLP pattern scanner — policy-driven regex packs (E6.2)."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from typing import List

from rag_protection_proxy.config import CustomPattern
from rag_protection_proxy.models import Finding
from rag_protection_proxy.scanners.base import Scanner, ScannerResult

_SCAN_TIMEOUT_SEC = 0.25


class CustomPatternScanner(Scanner):
    name = "custom_pattern"

    def __init__(self, patterns: List[CustomPattern]) -> None:
        self._patterns = [pattern for pattern in patterns if pattern.enabled]

    def scan(self, text: str) -> ScannerResult:
        if not isinstance(text, str):
            text = "" if text is None else str(text)
        if not self._patterns or not text:
            return ScannerResult(sanitized_text=text)

        findings: List[Finding] = []
        sanitized = text
        redactions = 0

        for pattern in self._patterns:
            matches = _safe_finditer(pattern.regex, sanitized, _SCAN_TIMEOUT_SEC)
            if not matches:
                continue
            scanner_name = _scanner_for_kind(pattern.kind)
            for match in matches:
                findings.append(
                    Finding(
                        scanner=scanner_name,
                        category=pattern.name,
                        severity=pattern.severity,
                        snippet=_snippet_for_match(match, pattern.kind, pattern.name),
                        label=pattern.label.upper() if pattern.label else None,
                    )
                )
            sanitized = pattern.regex.sub(pattern.replacement, sanitized)
            redactions += len(matches)

        return ScannerResult(sanitized_text=sanitized, findings=findings, redactions=redactions)


def _scanner_for_kind(kind: str) -> str:
    return "secrets" if kind == "secret" else "custom_pattern"


def _snippet_for_match(match: re.Match[str], kind: str, category: str) -> str:
    if kind == "secret":
        return f"[redacted:{category}]"
    return _mask(match.group(0))


def _safe_finditer(regex: re.Pattern[str], text: str, timeout: float) -> List[re.Match[str]]:
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(lambda: list(regex.finditer(text)))
        try:
            return future.result(timeout=timeout)
        except FuturesTimeout:
            return []


def _mask(value: str) -> str:
    if len(value) <= 4:
        return "*" * len(value)
    return value[:2] + "*" * (len(value) - 4) + value[-2:]
