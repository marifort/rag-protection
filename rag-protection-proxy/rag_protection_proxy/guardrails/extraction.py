"""Corpus-extraction (scraping) monitor (Lab 9).

A cross-query behavioral signal on the retrieval stream. ACL and DLP are per-query
and blind to *authorized breadth abuse* — a user who can see the corpus quietly
walking it end-to-end via many innocuous queries. This module keeps a per-subject
sliding window of retrieved-document sets and scores coverage / breadth / novelty,
emitting an ``extraction_suspected`` audit event when the behavior looks like a scrape.

State is in-process, per ``(tenant_id, subject)`` (mirrors the audit ring buffer).
No new datastore for MVP.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional, Set, Tuple

from rag_protection_proxy.audit import record
from rag_protection_proxy.config import ExtractionPolicy
from rag_protection_proxy.models import AuditEvent, Decision, Finding

EXTRACTION_KIND = "extraction_suspected"

_SEVERITY_RISK = {"none": 0.0, "elevated": 0.5, "severe": 0.9}
_SEVERITY_DECISION = {
    "none": Decision.ALLOW,
    "elevated": Decision.CHALLENGE,
    "severe": Decision.BLOCK,
}


def _trigger_summary(
    *,
    triggered_by: List[str],
    severity: str,
    corpus_coverage: float,
    breadth_ratio: float,
    novelty_ratio: float,
    rules: ExtractionPolicy,
) -> str:
    """Human-readable cause line for audit findings / blocked query responses."""
    parts: List[str] = []
    for signal in triggered_by:
        if signal == "coverage":
            thr = rules.severe_coverage if severity == "severe" else rules.elevated_coverage
            parts.append(f"coverage {corpus_coverage:.2f} ≥ {thr}")
        elif signal == "breadth":
            parts.append(f"breadth_ratio {breadth_ratio:.2f} ≥ {rules.breadth_ratio_threshold}")
        elif signal == "novelty":
            parts.append(f"novelty_ratio {novelty_ratio:.2f} ≥ {rules.novelty_ratio_threshold}")
    return "; ".join(parts)


@dataclass(frozen=True)
class ExtractionScore:
    subject: str
    tenant_id: str
    window_queries: int
    distinct_documents: int
    corpus_coverage: float
    breadth_ratio: float
    novelty_ratio: float
    severity: str  # "none" | "elevated" | "severe"
    detail: str
    triggered_by: Tuple[str, ...] = ()
    trigger_summary: str = ""

    def as_dict(self) -> Dict[str, object]:
        return {
            "subject": self.subject,
            "tenant_id": self.tenant_id,
            "window_queries": self.window_queries,
            "distinct_documents": self.distinct_documents,
            "corpus_coverage": round(self.corpus_coverage, 4),
            "breadth_ratio": round(self.breadth_ratio, 4),
            "novelty_ratio": round(self.novelty_ratio, 4),
            "severity": self.severity,
            "triggered_by": list(self.triggered_by),
            "trigger_summary": self.trigger_summary,
        }


@dataclass
class _Entry:
    ts: float
    document_ids: frozenset
    query_hash: str


@dataclass
class WindowState:
    """Per-subject time-bounded deque of retrieval events."""

    subject: str
    tenant_id: str
    entries: Deque[_Entry] = field(default_factory=deque)

    def prune(self, *, now: float, window_seconds: int, max_len: int = 1000) -> None:
        cutoff = now - window_seconds
        while self.entries and self.entries[0].ts < cutoff:
            self.entries.popleft()
        while len(self.entries) > max_len:
            self.entries.popleft()

    def add(self, entry: _Entry) -> None:
        self.entries.append(entry)


def _query_hash(query: str) -> str:
    return hashlib.sha1(" ".join((query or "").lower().split()).encode("utf-8")).hexdigest()[:16]


def score_window(state: WindowState, *, corpus_size: int, rules: ExtractionPolicy) -> ExtractionScore:
    """Derive coverage / breadth / novelty and classify severity for a window."""
    entries = list(state.entries)
    window_queries = len(entries)

    seen: Set[str] = set()
    novel_queries = 0
    for entry in entries:
        if entry.document_ids - seen:
            novel_queries += 1
        seen |= set(entry.document_ids)

    distinct_documents = len(seen)
    breadth_ratio = (distinct_documents / window_queries) if window_queries else 0.0
    novelty_ratio = (novel_queries / window_queries) if window_queries else 0.0

    coverage_active = corpus_size >= rules.min_corpus_size
    corpus_coverage = (distinct_documents / corpus_size) if (coverage_active and corpus_size) else 0.0

    have_full_window = window_queries >= rules.min_window_queries

    # Coverage, breadth, and novelty all require a full window so a single
    # Query Lab click (or top_k over a tiny sample corpus) cannot trip severe.
    # Without this, elevated_coverage 0.2 / severe 0.4 on a 5-doc demo corpus
    # blocks after one payroll query that touches 2 documents.
    coverage_severe = coverage_active and corpus_coverage >= rules.severe_coverage
    breadth_severe = breadth_ratio >= rules.breadth_ratio_threshold
    coverage_elevated = coverage_active and corpus_coverage >= rules.elevated_coverage
    novelty_elevated = novelty_ratio >= rules.novelty_ratio_threshold

    severe = have_full_window and (coverage_severe or breadth_severe)
    elevated = have_full_window and (coverage_elevated or novelty_elevated)
    severity = "severe" if severe else ("elevated" if elevated else "none")

    triggered: List[str] = []
    if severity == "severe":
        if coverage_severe:
            triggered.append("coverage")
        if breadth_severe:
            triggered.append("breadth")
    elif severity == "elevated":
        if coverage_elevated:
            triggered.append("coverage")
        if novelty_elevated:
            triggered.append("novelty")

    summary = _trigger_summary(
        triggered_by=triggered,
        severity=severity,
        corpus_coverage=corpus_coverage,
        breadth_ratio=breadth_ratio,
        novelty_ratio=novelty_ratio,
        rules=rules,
    )

    detail = json.dumps(
        {
            "coverage": round(corpus_coverage, 4),
            "breadth_ratio": round(breadth_ratio, 4),
            "novelty_ratio": round(novelty_ratio, 4),
            "distinct_documents": distinct_documents,
            "window_queries": window_queries,
            "corpus_size": corpus_size,
            "triggered_by": triggered,
            "trigger_summary": summary,
        },
        separators=(",", ":"),
    )
    return ExtractionScore(
        subject=state.subject,
        tenant_id=state.tenant_id,
        window_queries=window_queries,
        distinct_documents=distinct_documents,
        corpus_coverage=corpus_coverage,
        breadth_ratio=breadth_ratio,
        novelty_ratio=novelty_ratio,
        severity=severity,
        detail=detail,
        triggered_by=tuple(triggered),
        trigger_summary=summary,
    )


class ExtractionMonitor:
    def __init__(self) -> None:
        self._windows: Dict[Tuple[str, str], WindowState] = {}
        self._lock = threading.Lock()

    def _key(self, tenant_id: str, subject: str) -> Tuple[str, str]:
        return (tenant_id or "default", subject or "unknown")

    def observe(
        self,
        *,
        subject: str,
        tenant_id: str,
        document_ids: List[str],
        query: str,
        corpus_size: int,
        rules: ExtractionPolicy,
        now: Optional[float] = None,
    ) -> ExtractionScore:
        now = time.time() if now is None else now
        key = self._key(tenant_id, subject)
        with self._lock:
            state = self._windows.get(key)
            if state is None:
                state = WindowState(subject=subject or "unknown", tenant_id=tenant_id or "default")
                self._windows[key] = state
            state.add(
                _Entry(
                    ts=now,
                    document_ids=frozenset(d for d in document_ids if d),
                    query_hash=_query_hash(query),
                )
            )
            state.prune(now=now, window_seconds=rules.window_seconds)
            return score_window(state, corpus_size=corpus_size, rules=rules)

    def watch(self, *, rules: ExtractionPolicy, corpus_sizes: Optional[Dict[str, int]] = None) -> List[Dict[str, object]]:
        """Current subjects at elevated/severe severity, most-severe first."""
        now = time.time()
        offenders: List[Dict[str, object]] = []
        with self._lock:
            for state in self._windows.values():
                state.prune(now=now, window_seconds=rules.window_seconds)
                if not state.entries:
                    continue
                corpus_size = (corpus_sizes or {}).get(state.tenant_id, rules.min_corpus_size)
                score = score_window(state, corpus_size=corpus_size, rules=rules)
                if score.severity != "none":
                    offenders.append(score.as_dict())
        offenders.sort(key=lambda s: _SEVERITY_RISK.get(str(s["severity"]), 0.0), reverse=True)
        return offenders

    def reset_for_tests(self) -> None:
        with self._lock:
            self._windows.clear()


_MONITOR = ExtractionMonitor()


def record_extraction_event(score: ExtractionScore) -> None:
    category = "+".join(score.triggered_by) if score.triggered_by else "extraction"
    finding_detail = score.trigger_summary or (
        f"{score.distinct_documents} docs over {score.window_queries} queries"
    )
    record(
        AuditEvent(
            timestamp=time.time(),
            kind=EXTRACTION_KIND,
            decision=_SEVERITY_DECISION[score.severity],
            risk_score=_SEVERITY_RISK[score.severity],
            subject=score.subject,
            tenant_id=score.tenant_id,
            source="retrieval.monitor",
            findings=[
                Finding(
                    scanner="extraction",
                    category=category,
                    severity=_SEVERITY_RISK[score.severity],
                    label=score.severity,
                    detail=finding_detail,
                )
            ],
            detail=score.detail,
        )
    )


def observe_query(
    *,
    subject: str,
    tenant_id: str,
    document_ids: List[str],
    query: str,
    corpus_size: int,
    rules: ExtractionPolicy,
    now: Optional[float] = None,
) -> ExtractionScore:
    """Record one retrieval into the window, score it, and emit an event if suspicious."""
    score = _MONITOR.observe(
        subject=subject,
        tenant_id=tenant_id,
        document_ids=document_ids,
        query=query,
        corpus_size=corpus_size,
        rules=rules,
        now=now,
    )
    if score.severity != "none":
        record_extraction_event(score)
    return score


def watch(*, rules: ExtractionPolicy, corpus_sizes: Optional[Dict[str, int]] = None) -> List[Dict[str, object]]:
    return _MONITOR.watch(rules=rules, corpus_sizes=corpus_sizes)


def reset_for_tests() -> None:
    _MONITOR.reset_for_tests()
