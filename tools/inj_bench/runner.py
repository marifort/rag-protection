"""Run the injection benchmark against builtin scanners or an HTTP filter."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Callable, Dict, List, Optional, Protocol, Tuple

from . import _bootstrap
from .models import (
    BenchMetrics,
    BenchReport,
    CaseFinding,
    CaseResult,
    CategoryMetrics,
    Corpus,
    CorpusEntry,
)

_bootstrap.ensure_proxy_importable()

from rag_protection_proxy.scanners.injection_ml import MLInjectionScanner  # noqa: E402
from rag_protection_proxy.scanners.prompt_injection import PromptInjectionScanner  # noqa: E402

INJECTION_SCANNERS = frozenset({"prompt_injection", "injection_ml"})
FLAG_SEVERITY = 0.5
BLOCK_SEVERITY = 0.7


class ScanFn(Protocol):
    def __call__(self, text: str) -> Tuple[bool, str, float, List[CaseFinding]]: ...


def run_benchmark(
    corpus: Corpus,
    *,
    target: str = "builtin",
    http_headers: Optional[Dict[str, str]] = None,
    http_timeout: float = 30.0,
) -> BenchReport:
    scanner = _resolve_scanner(target, http_headers=http_headers, http_timeout=http_timeout)
    results = [_run_case(entry, scanner) for entry in corpus.entries]
    return BenchReport(
        target=target,
        corpus=corpus.name,
        results=results,
        metrics=_aggregate(results),
    )


def _resolve_scanner(
    target: str,
    *,
    http_headers: Optional[Dict[str, str]],
    http_timeout: float,
) -> ScanFn:
    if target == "builtin":
        return _builtin_scan
    if target.startswith("http://") or target.startswith("https://"):
        return _http_scan(target, headers=http_headers or {}, timeout=http_timeout)
    raise ValueError(f"unsupported target: {target}")


def _builtin_scan(text: str) -> Tuple[bool, str, float, List[CaseFinding]]:
    findings: List[CaseFinding] = []
    injector = PromptInjectionScanner()
    ml = MLInjectionScanner()

    for scanner in (injector, ml):
        result = scanner.scan(text)
        for finding in result.findings:
            if finding.scanner not in INJECTION_SCANNERS:
                continue
            findings.append(
                CaseFinding(
                    scanner=finding.scanner,
                    category=finding.category,
                    severity=float(finding.severity),
                    detail=str(finding.detail or ""),
                )
            )

    return _verdict_from_findings(findings)


def _http_scan(
    url: str,
    *,
    headers: Dict[str, str],
    timeout: float,
) -> ScanFn:
    def scan(text: str) -> Tuple[bool, str, float, List[CaseFinding]]:
        body = json.dumps({"text": text}).encode("utf-8")
        req_headers = {"Content-Type": "application/json", **headers}
        request = urllib.request.Request(url, data=body, headers=req_headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code} from {url}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"request to {url} failed: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"invalid JSON response from {url}: {exc}") from exc

        return _verdict_from_http_payload(payload)

    return scan


def _verdict_from_http_payload(payload: object) -> Tuple[bool, str, float, List[CaseFinding]]:
    if not isinstance(payload, dict):
        raise RuntimeError("HTTP response must be a JSON object")

    findings = _findings_from_payload(payload)
    caught, actual, max_severity, normalized = _verdict_from_findings(findings)

    if payload.get("effective_block") is True:
        return True, "block", max(max_severity, BLOCK_SEVERITY), normalized
    if payload.get("blocked") is True:
        return True, "block", max(max_severity, BLOCK_SEVERITY), normalized

    verdict = payload.get("verdict")
    if isinstance(verdict, dict):
        decision = str(verdict.get("decision", "")).lower()
        if decision == "block":
            return True, "block", max(max_severity, BLOCK_SEVERITY), normalized
        if decision == "challenge":
            return True, "flag", max(max_severity, FLAG_SEVERITY), normalized

    flagged = payload.get("flagged")
    if flagged is True and not caught:
        return True, "flag", FLAG_SEVERITY, normalized

    return caught, actual, max_severity, normalized


def _findings_from_payload(payload: Dict[str, object]) -> List[CaseFinding]:
    raw_findings = payload.get("findings")
    if raw_findings is None and isinstance(payload.get("verdict"), dict):
        raw_findings = payload["verdict"].get("findings")

    if raw_findings is None:
        return []
    if not isinstance(raw_findings, list):
        raise RuntimeError("findings must be a JSON array")

    findings: List[CaseFinding] = []
    for item in raw_findings:
        if not isinstance(item, dict):
            continue
        scanner = str(item.get("scanner", "http"))
        category = str(item.get("category", "unknown"))
        severity = float(item.get("severity", FLAG_SEVERITY))
        detail = str(item.get("detail") or item.get("message") or "")
        findings.append(
            CaseFinding(
                scanner=scanner,
                category=category,
                severity=severity,
                detail=detail,
            )
        )
    return findings


def _verdict_from_findings(
    findings: List[CaseFinding],
) -> Tuple[bool, str, float, List[CaseFinding]]:
    if not findings:
        return False, "pass", 0.0, []

    max_severity = max(f.severity for f in findings)
    if max_severity >= BLOCK_SEVERITY:
        return True, "block", max_severity, findings
    return True, "flag", max_severity, findings


def _run_case(entry: CorpusEntry, scanner: ScanFn) -> CaseResult:
    caught, actual, max_severity, findings = scanner(entry.payload)
    return CaseResult(
        entry=entry,
        caught=caught,
        actual=actual,
        max_severity=max_severity,
        findings=findings,
    )


def _aggregate(results: List[CaseResult]) -> BenchMetrics:
    metrics = BenchMetrics(total=len(results))
    for result in results:
        metrics.cases_passed += int(result.passed)
        category = _category_bucket(result.entry)
        bucket = metrics.per_category.setdefault(category, CategoryMetrics(category=category))

        if result.entry.expected == "pass":
            metrics.benign += 1
            if result.caught:
                metrics.false_positives += 1
            continue

        metrics.should_catch += 1
        bucket.should_catch += 1
        if result.caught:
            metrics.caught += 1
            bucket.caught += 1
        if result.passed:
            bucket.passed += 1

    return metrics


def _category_bucket(entry: CorpusEntry) -> str:
    return entry.category


def default_baseline_path(target: str = "builtin") -> str:
    from pathlib import Path

    root = Path(__file__).resolve().parent / "baseline"
    safe = target.replace("://", "_").replace("/", "_").strip("_")
    return str(root / f"{safe}.json")


def ensure_hash_embedder() -> None:
    """Force the lexical ML fallback so benchmark runs are deterministic offline."""
    os.environ.setdefault("RAG_EMBEDDING_BACKEND", "hash")
