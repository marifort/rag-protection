"""Audit event recording with in-memory buffer and optional persistent sinks."""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

import httpx
from pydantic import ValidationError

from rag_protection_proxy.models import AuditDebugPreview, AuditEvent, CitationClaimAuditPreview
from rag_protection_proxy import audit_integrity

logger = logging.getLogger(__name__)

_BUFFER: Deque[AuditEvent] = deque(maxlen=int(os.getenv("RAG_AUDIT_BUFFER_SIZE", "1000")))
_LOCK = threading.Lock()
_AUDIT_FILE: Optional[Path] = None
_WEBHOOK_URL: Optional[str] = None
_WEBHOOK_TIMEOUT: float = 5.0
_WEBHOOK_HEADERS: Dict[str, str] = {}
_WEBHOOK_MAX_RETRIES: int = 3
_WEBHOOK_BACKOFF_SECONDS: float = 0.5
_DEAD_LETTER_FILE: Optional[Path] = None
_AUDIT_POLICY: Dict[str, object] = {
    "retention_days": 7,
    "backup_keep_days": 7,
    "scrub_export": True,
    "max_export_rows": 5000,
    "debug_webhook": False,
    "debug_retention_hours": 24,
    "sample_by_kind": {},
    "retention_by_kind": {},
    "retain_decisions": {},
}
_RECORDS_SINCE_PRUNE: int = 0
_SAMPLE_COUNTERS: Dict[str, int] = defaultdict(int)
_SAMPLE_DROPPED: Dict[str, int] = defaultdict(int)

_SCRUB_DETAIL_PATTERNS = [
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[REDACTED_SSN]"),
    (re.compile(r"\b\d{3}(?:-\d{3}-\d{3}|\s\d{3}\s\d{3})\b"), "[REDACTED_SIN]"),
    (re.compile(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b"), "[REDACTED_PHONE]"),
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[REDACTED_EMAIL]"),
]


def attach_audit_file(path: Optional[Path] = None) -> None:
    """Point the JSONL reader at ``path`` without rotating or pruning.

    Host CLIs such as ``tools/rag-evidence`` share a bind-mounted
    ``RAG_AUDIT_FILE`` with a running proxy and must not rewrite it.
    """
    global _AUDIT_FILE
    _AUDIT_FILE = path


def configure_audit() -> None:
    """Load persistent sink settings from environment (call at app startup)."""
    global _AUDIT_FILE, _WEBHOOK_URL, _WEBHOOK_TIMEOUT, _WEBHOOK_HEADERS
    global _WEBHOOK_MAX_RETRIES, _WEBHOOK_BACKOFF_SECONDS, _DEAD_LETTER_FILE

    file_path = os.getenv("RAG_AUDIT_FILE", "").strip()
    _AUDIT_FILE = Path(file_path) if file_path else None
    if _AUDIT_FILE is not None:
        _AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)

    _WEBHOOK_URL = os.getenv("RAG_AUDIT_WEBHOOK_URL", "").strip() or None
    _WEBHOOK_TIMEOUT = float(os.getenv("RAG_AUDIT_WEBHOOK_TIMEOUT", "5"))
    _WEBHOOK_MAX_RETRIES = max(1, int(os.getenv("RAG_AUDIT_WEBHOOK_RETRIES", "3")))
    _WEBHOOK_BACKOFF_SECONDS = float(os.getenv("RAG_AUDIT_WEBHOOK_BACKOFF", "0.5"))

    dead_letter_path = os.getenv("RAG_AUDIT_DEAD_LETTER_FILE", "").strip()
    _DEAD_LETTER_FILE = Path(dead_letter_path) if dead_letter_path else None
    if _DEAD_LETTER_FILE is not None:
        _DEAD_LETTER_FILE.parent.mkdir(parents=True, exist_ok=True)

    headers_raw = os.getenv("RAG_AUDIT_WEBHOOK_HEADERS", "").strip()
    if headers_raw:
        try:
            parsed = json.loads(headers_raw)
            _WEBHOOK_HEADERS = {str(k): str(v) for k, v in parsed.items()}
        except json.JSONDecodeError:
            logger.warning("Invalid RAG_AUDIT_WEBHOOK_HEADERS JSON; ignoring")
            _WEBHOOK_HEADERS = {}
    else:
        _WEBHOOK_HEADERS = {}

    warm_buffer_from_file()
    audit_integrity.load_chain_tip(_AUDIT_FILE)
    _maybe_rotate_audit_file()
    apply_retention()


def configure_audit_policy(
    *,
    retention_days: int = 7,
    backup_keep_days: int = 7,
    scrub_export: bool = True,
    max_export_rows: int = 5000,
    debug_webhook: bool = False,
    debug_retention_hours: int = 24,
    integrity_chain: bool = False,
    sample_by_kind: Optional[Dict[str, Any]] = None,
    retention_by_kind: Optional[Dict[str, int]] = None,
    retain_decisions: Optional[Dict[str, int]] = None,
) -> None:
    global _AUDIT_POLICY
    _AUDIT_POLICY = {
        "retention_days": max(0, int(retention_days)),
        "backup_keep_days": max(1, int(backup_keep_days)),
        "scrub_export": bool(scrub_export),
        "max_export_rows": max(1, int(max_export_rows)),
        "debug_webhook": bool(debug_webhook),
        "debug_retention_hours": max(0, int(debug_retention_hours)),
        "integrity_chain": bool(integrity_chain),
        "sample_by_kind": dict(sample_by_kind or {}),
        "retention_by_kind": {str(k): max(0, int(v)) for k, v in (retention_by_kind or {}).items()},
        "retain_decisions": {str(k).lower(): max(0, int(v)) for k, v in (retain_decisions or {}).items()},
    }
    audit_integrity.configure_integrity_chain(enabled=bool(integrity_chain))
    audit_integrity.load_chain_tip(_AUDIT_FILE)


def status() -> Dict[str, object]:
    backup_dir = _audit_backup_dir() if _AUDIT_FILE else None
    return {
        "buffer_max": _BUFFER.maxlen,
        "buffer_count": len(_BUFFER),
        "file_sink": str(_AUDIT_FILE) if _AUDIT_FILE else None,
        "backup_dir": str(backup_dir) if backup_dir else None,
        "backup_keep_days": _AUDIT_POLICY.get("backup_keep_days"),
        "webhook_configured": bool(_WEBHOOK_URL),
        "webhook_retries": _WEBHOOK_MAX_RETRIES,
        "dead_letter_sink": str(_DEAD_LETTER_FILE) if _DEAD_LETTER_FILE else None,
        "retention_days": _AUDIT_POLICY.get("retention_days"),
        "retention_by_kind": _AUDIT_POLICY.get("retention_by_kind"),
        "retain_decisions": _AUDIT_POLICY.get("retain_decisions"),
        "sample_by_kind": {
            kind: {
                "when_decision": getattr(rule, "when_decision", None)
                if not isinstance(rule, dict)
                else rule.get("when_decision"),
                "keep_every": getattr(rule, "keep_every", None)
                if not isinstance(rule, dict)
                else rule.get("keep_every"),
            }
            for kind, rule in dict(_AUDIT_POLICY.get("sample_by_kind") or {}).items()
        },
        "sample_dropped": dict(_SAMPLE_DROPPED),
        "scrub_export": _AUDIT_POLICY.get("scrub_export"),
        "max_export_rows": _AUDIT_POLICY.get("max_export_rows"),
        "debug_webhook": _AUDIT_POLICY.get("debug_webhook"),
        "debug_retention_hours": _AUDIT_POLICY.get("debug_retention_hours"),
        "integrity_chain": _AUDIT_POLICY.get("integrity_chain"),
        "integrity_chain_tip": audit_integrity.chain_tip() if audit_integrity.chain_enabled() else None,
    }


def _detail_dict(event: AuditEvent) -> Dict[str, Any]:
    raw = event.detail
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(str(raw))
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _is_interesting_connector_heartbeat(event: AuditEvent) -> bool:
    """True when a connector/acl sync row is worth keeping despite sample rules."""
    detail = _detail_dict(event)
    if str(detail.get("status") or "").lower() not in ("", "ok"):
        return True
    if detail.get("acl_updated") is True:
        return True
    if detail.get("acl_mapping_failed") is True:
        return True
    drift = str(detail.get("drift_severity") or "none").strip().lower()
    if drift and drift not in ("none", "null"):
        return True
    if detail.get("error"):
        return True
    return False


def should_record_event(event: AuditEvent) -> bool:
    """Return False when write-time sampling drops a routine hygiene event."""
    rules = _AUDIT_POLICY.get("sample_by_kind") or {}
    rule = rules.get(event.kind)
    if rule is None:
        return True

    when_decision = list(getattr(rule, "when_decision", None) or [])
    if isinstance(rule, dict):
        when_decision = list(rule.get("when_decision") or [])
    decision = str(getattr(event.decision, "value", event.decision) or "").lower()
    if when_decision and decision not in {str(item).lower() for item in when_decision}:
        return True

    if event.kind in ("connector_sync", "acl_sync") and _is_interesting_connector_heartbeat(event):
        return True

    keep_every = int(getattr(rule, "keep_every", 0) if not isinstance(rule, dict) else rule.get("keep_every", 0) or 0)
    if keep_every <= 0:
        return False

    with _LOCK:
        _SAMPLE_COUNTERS[event.kind] += 1
        return (_SAMPLE_COUNTERS[event.kind] % keep_every) == 0


def retention_days_for_event(kind: str, decision: str, *, default_days: int) -> int:
    """Effective TTL in days for one event (max of kind override and decision floor)."""
    by_kind = dict(_AUDIT_POLICY.get("retention_by_kind") or {})
    by_decision = dict(_AUDIT_POLICY.get("retain_decisions") or {})
    days = int(by_kind.get(kind, default_days) or default_days)
    decision_key = str(decision or "").lower()
    if decision_key in by_decision:
        days = max(days, int(by_decision[decision_key] or 0))
    return max(0, days)


def record(event: AuditEvent) -> bool:
    """Append an audit event. Returns False when sampling dropped it."""
    global _RECORDS_SINCE_PRUNE
    if not should_record_event(event):
        with _LOCK:
            _SAMPLE_DROPPED[event.kind] += 1
        logger.debug("Audit sample dropped kind=%s decision=%s", event.kind, event.decision)
        return False
    _BUFFER.append(event)
    payload = event.model_dump(mode="json")
    if audit_integrity.chain_enabled():
        payload = audit_integrity.append_chain_fields(payload)
    _maybe_rotate_audit_file()
    _persist_jsonl(payload)
    _dispatch_webhook(_webhook_payload(payload))
    _RECORDS_SINCE_PRUNE += 1
    if _RECORDS_SINCE_PRUNE >= 50:
        _RECORDS_SINCE_PRUNE = 0
        apply_retention()
    return True


def _payloads_to_recent_events(payloads: List[Dict[str, Any]]) -> List[AuditEvent]:
    events: List[AuditEvent] = []
    for payload in reversed(payloads):
        try:
            events.append(AuditEvent.model_validate(payload))
        except ValidationError:
            logger.warning("Skipping invalid audit event")
    return events


def warm_buffer_from_file() -> int:
    """Load the last buffer-max events from JSONL into the ring buffer."""
    if _AUDIT_FILE is None or not _AUDIT_FILE.exists():
        return 0
    maxlen = _BUFFER.maxlen or 1000
    _BUFFER.clear()
    payloads = iter_event_dicts(limit=maxlen)
    loaded = 0
    for payload in payloads:
        try:
            _BUFFER.append(AuditEvent.model_validate(payload))
            loaded += 1
        except ValidationError:
            logger.warning("Skipping invalid audit event during buffer warm")
    return loaded


def recent(limit: int = 50) -> List[AuditEvent]:
    cap = min(max(limit, 1), 200)
    if _BUFFER:
        return list(_BUFFER)[-cap:][::-1]
    if _AUDIT_FILE is not None and _AUDIT_FILE.exists():
        return _payloads_to_recent_events(iter_event_dicts(limit=cap))
    return []


def export_jsonl(
    limit: int = 1000,
    *,
    scrub: Optional[bool] = None,
    tenant_id: Optional[str] = None,
    include_debug: bool = True,
) -> str:
    """Return audit events as newline-delimited JSON (file sink preferred)."""
    apply_retention()
    max_rows = int(_AUDIT_POLICY.get("max_export_rows", 5000))
    capped = min(max(limit, 1), max_rows) if limit > 0 else max_rows
    use_scrub = _AUDIT_POLICY.get("scrub_export", True) if scrub is None else scrub
    events = iter_event_dicts(limit=capped, tenant_id=tenant_id)
    lines = []
    for payload in events[-capped:]:
        if not include_debug:
            payload = strip_debug_from_event_payload(payload)
        if use_scrub:
            payload = scrub_event_payload(payload)
        lines.append(json.dumps(payload, separators=(",", ":")))
    return "\n".join(lines) + ("\n" if lines else "")


def _parse_event_line(line: str) -> Optional[Dict[str, Any]]:
    line = line.strip()
    if not line:
        return None
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        logger.warning("Skipping invalid audit JSONL line")
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _event_dedup_key(payload: Dict[str, Any]) -> tuple:
    """Stable key for merging in-memory buffer rows with JSONL file rows."""
    return (
        round(float(payload.get("timestamp") or 0.0), 6),
        str(payload.get("kind") or ""),
        str(payload.get("subject") or ""),
        str(payload.get("source") or ""),
        str(payload.get("detail") or ""),
        str(payload.get("tenant_id") or "default"),
    )


def iter_event_dicts(
    *,
    since: Optional[float] = None,
    until: Optional[float] = None,
    limit: int = 10000,
    tenant_id: Optional[str] = None,
    apply_retention_now: bool = True,
) -> List[Dict[str, Any]]:
    """Load audit events from ring buffer and optional JSONL sink, filtered by timestamp/tenant."""
    if apply_retention_now:
        apply_retention()
    cap = max(1, min(limit, 10000))
    merged: Dict[tuple, Dict[str, Any]] = {}

    for event in _BUFFER:
        payload = event.model_dump(mode="json")
        merged[_event_dedup_key(payload)] = payload

    if _AUDIT_FILE is not None and _AUDIT_FILE.exists():
        with _LOCK:
            lines = _AUDIT_FILE.read_text(encoding="utf-8").splitlines()
        for line in lines:
            payload = _parse_event_line(line)
            if payload is not None:
                merged[_event_dedup_key(payload)] = payload

    events = list(merged.values())

    if since is not None or until is not None or tenant_id is not None:
        filtered: List[Dict[str, Any]] = []
        for payload in events:
            ts = float(payload.get("timestamp") or 0.0)
            if since is not None and ts < since:
                continue
            if until is not None and ts > until:
                continue
            if tenant_id is not None and str(payload.get("tenant_id") or "default") != tenant_id:
                continue
            filtered.append(payload)
        events = filtered

    events.sort(key=lambda item: float(item.get("timestamp") or 0.0))
    if len(events) > cap:
        events = events[-cap:]
    return events


def _bucket_start(ts: float, bucket_seconds: int) -> int:
    bucket = max(60, bucket_seconds)
    return int(ts // bucket) * bucket


def _trim_series_edges(series: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Drop leading/trailing empty buckets so charts focus on the data-bearing window."""
    if len(series) <= 1:
        return series
    start_idx = 0
    end_idx = len(series) - 1
    while start_idx < end_idx and series[start_idx].get("total", 0) == 0:
        start_idx += 1
    while end_idx > start_idx and series[end_idx].get("total", 0) == 0:
        end_idx -= 1
    return series[start_idx : end_idx + 1]


_LEGACY_QUERY_BLOCKED_KINDS = frozenset({"query_blocked", "citation_failed", "rate_limited"})


def _event_search_blob(payload: Dict[str, Any]) -> str:
    parts = [
        str(payload.get("kind") or ""),
        str(payload.get("decision") or ""),
        str(payload.get("subject") or ""),
        str(payload.get("detail") or ""),
        str(payload.get("tenant_id") or ""),
        str(payload.get("source") or ""),
    ]
    for finding in payload.get("findings") or []:
        if not isinstance(finding, dict):
            continue
        parts.extend(
            [
                str(finding.get("scanner") or ""),
                str(finding.get("category") or ""),
                str(finding.get("label") or ""),
                str(finding.get("detail") or ""),
            ]
        )
    debug = payload.get("debug")
    if isinstance(debug, dict):
        parts.extend(
            [
                str(debug.get("query_preview") or ""),
                str(debug.get("input_preview") or ""),
                str(debug.get("output_preview") or ""),
            ]
        )
        for claim in debug.get("citation_claims") or []:
            if not isinstance(claim, dict):
                continue
            parts.extend(
                [
                    str(claim.get("sentence") or ""),
                    str(claim.get("chunk_id") or ""),
                    str(claim.get("entailment_score") or ""),
                ]
            )
    return " ".join(parts).lower()


def event_source_where(source: Optional[str]) -> str:
    """Classify audit ``source`` into operator Where buckets (query, document, ingest, tool)."""
    value = str(source or "")
    if value == "rag:user_query" or value.startswith("rag:user_query:") or value == "rag:query":
        return "query"
    if value.startswith("rag:chunk:"):
        return "document"
    if value.startswith("rag:ingest:"):
        return "ingest"
    if value.startswith("tool:"):
        return "tool"
    if value == "rag:output" or value.startswith("rag:output:") or value == "rag:llm_routing":
        return "output"
    if value == "retrieval.explain" or value.startswith("retrieval."):
        return "knowledge_base"
    return ""


def _event_matches_filters(
    payload: Dict[str, Any],
    *,
    kind: Optional[str] = None,
    decision: Optional[str] = None,
    search: Optional[str] = None,
    where: Optional[str] = None,
) -> bool:
    if kind and str(payload.get("kind") or "").lower() != kind.strip().lower():
        return False
    if decision and str(payload.get("decision") or "").lower() != decision.strip().lower():
        return False
    if where:
        wanted = where.strip().lower()
        if wanted and event_source_where(payload.get("source")) != wanted:
            return False
    if search:
        needle = search.strip().lower()
        if needle and needle not in _event_search_blob(payload):
            return False
    return True


def query_audit_events(
    *,
    since: Optional[float] = None,
    until: Optional[float] = None,
    tenant_id: Optional[str] = None,
    kind: Optional[str] = None,
    decision: Optional[str] = None,
    search: Optional[str] = None,
    where: Optional[str] = None,
    offset: int = 0,
    limit: int = 50,
    scan_limit: int = 10000,
) -> Dict[str, Any]:
    """List audit events with time-window filtering, search, and pagination."""
    now = time.time()
    end = until if until is not None else now
    start = since if since is not None else end - (7 * 86400)
    if end < start:
        start, end = end, start

    page_limit = max(1, min(int(limit), 200))
    page_offset = max(0, int(offset))
    scan_cap = max(1, min(int(scan_limit), 10000))

    events = iter_event_dicts(since=start, until=end, limit=scan_cap, tenant_id=tenant_id)
    filtered = [
        payload
        for payload in events
        if _event_matches_filters(payload, kind=kind, decision=decision, search=search, where=where)
    ]
    filtered.sort(key=lambda item: float(item.get("timestamp") or 0.0), reverse=True)
    total = len(filtered)
    page = filtered[page_offset : page_offset + page_limit]

    return {
        "from": start,
        "to": end,
        "tenant_id": tenant_id,
        "filters": {
            "kind": kind or None,
            "decision": decision or None,
            "search": search or None,
            "where": where or None,
        },
        "total": total,
        "offset": page_offset,
        "limit": page_limit,
        "events": page,
    }


def compute_overview_stats(
    *,
    since: Optional[float] = None,
    until: Optional[float] = None,
    limit: int = 10000,
    tenant_id: Optional[str] = None,
    documents_current: Optional[int] = None,
    challenges_pending: Optional[int] = None,
) -> Dict[str, Any]:
    """Aggregate operator overview counters for a selected time window."""
    now = time.time()
    end = until if until is not None else now
    start = since if since is not None else end - (7 * 86400)
    if end < start:
        start, end = end, start

    events = iter_event_dicts(since=start, until=end, limit=limit, tenant_id=tenant_id)
    queries_allowed = 0
    queries_blocked = 0
    ingest_total = 0
    ingest_quarantined = 0
    challenge_approved = 0
    challenge_rejected = 0
    has_query_completed = False

    for payload in events:
        kind = str(payload.get("kind") or "")
        decision = str(payload.get("decision") or "").lower()
        if kind == "query_completed":
            has_query_completed = True
            if decision == "block":
                queries_blocked += 1
            else:
                queries_allowed += 1
        elif kind == "ingest_completed":
            ingest_total += 1
            if decision == "challenge":
                ingest_quarantined += 1
        elif kind == "challenge_approved":
            challenge_approved += 1
        elif kind == "challenge_rejected":
            challenge_rejected += 1

    if not has_query_completed:
        for payload in events:
            kind = str(payload.get("kind") or "")
            if kind in _LEGACY_QUERY_BLOCKED_KINDS:
                queries_blocked += 1

    return {
        "from": start,
        "to": end,
        "tenant_id": tenant_id,
        "documents_current": documents_current,
        "challenges_pending": challenges_pending,
        "queries_allowed": queries_allowed,
        "queries_blocked": queries_blocked,
        "ingest_total": ingest_total,
        "ingest_quarantined": ingest_quarantined,
        "challenge_approved": challenge_approved,
        "challenge_rejected": challenge_rejected,
        "audit_events_total": len(events),
    }


def compute_audit_stats(
    *,
    since: Optional[float] = None,
    until: Optional[float] = None,
    bucket_seconds: int = 3600,
    limit: int = 10000,
    tenant_id: Optional[str] = None,
    apply_retention_now: bool = True,
) -> Dict[str, Any]:
    """Aggregate allow/challenge/block time series and breakdowns for operator dashboards."""
    now = time.time()
    end = until if until is not None else now
    start = since if since is not None else end - (7 * 86400)
    if end < start:
        start, end = end, start

    events = iter_event_dicts(
        since=start,
        until=end,
        limit=limit,
        tenant_id=tenant_id,
        apply_retention_now=apply_retention_now,
    )
    bucket_seconds = max(60, min(bucket_seconds, 86400))

    by_decision: Counter[str] = Counter()
    by_kind: Counter[str] = Counter()
    by_scanner: Counter[str] = Counter()
    by_category: Counter[str] = Counter()
    series_map: Dict[int, Counter[str]] = defaultdict(Counter)

    for payload in events:
        decision = str(payload.get("decision") or "unknown").lower()
        kind = str(payload.get("kind") or "unknown")
        ts = float(payload.get("timestamp") or 0.0)
        by_decision[decision] += 1
        by_kind[kind] += 1
        series_map[_bucket_start(ts, bucket_seconds)][decision] += 1
        for finding in payload.get("findings") or []:
            if not isinstance(finding, dict):
                continue
            scanner = str(finding.get("scanner") or "unknown")
            category = str(finding.get("category") or "unknown")
            by_scanner[scanner] += 1
            by_category[category] += 1

    series = []
    if events:
        cursor = _bucket_start(start, bucket_seconds)
        end_bucket = _bucket_start(end, bucket_seconds)
        while cursor <= end_bucket:
            counts = series_map.get(cursor, Counter())
            series.append(
                {
                    "bucket_start": cursor,
                    "allow": counts.get("allow", 0),
                    "challenge": counts.get("challenge", 0),
                    "block": counts.get("block", 0),
                    "total": sum(counts.values()),
                }
            )
            cursor += bucket_seconds
        series = _trim_series_edges(series)

    series_from = series[0]["bucket_start"] if series else start
    series_to = (series[-1]["bucket_start"] + bucket_seconds) if series else end

    return {
        "from": start,
        "to": end,
        "series_from": series_from,
        "series_to": series_to,
        "tenant_id": tenant_id,
        "bucket_seconds": bucket_seconds,
        "total_events": len(events),
        "by_decision": dict(by_decision),
        "by_kind": dict(by_kind),
        "by_scanner": dict(by_scanner.most_common(20)),
        "by_category": dict(by_category.most_common(20)),
        "series": series,
    }


def scrub_text(value: Optional[str]) -> Optional[str]:
    if not value:
        return value
    scrubbed = value
    for pattern, replacement in _SCRUB_DETAIL_PATTERNS:
        scrubbed = pattern.sub(replacement, scrubbed)
    return scrubbed


def audit_debug_active(policy: object, *, request_flag: bool = False) -> bool:
    """True when global audit debug or a per-request flag is enabled."""
    audit = getattr(policy, "audit", None)
    global_debug = bool(getattr(audit, "debug_mode", False)) if audit is not None else False
    return global_debug or bool(request_flag)


def audit_preview_text(text: str, *, max_chars: int = 500) -> str:
    """Scrub then truncate sanitized text for optional audit debug previews."""
    cap = max(64, int(max_chars))
    scrubbed = scrub_text(text) or text
    trimmed = scrubbed[:cap]
    if len(scrubbed) > cap:
        trimmed += "…"
    return trimmed


def build_audit_debug_preview(
    *,
    enabled: bool,
    max_preview_chars: int = 500,
    input_text: Optional[str] = None,
    output_text: Optional[str] = None,
    query_text: Optional[str] = None,
    redactions: Optional[int] = None,
    chunk_ids: Optional[List[str]] = None,
    citation_coverage_ratio: Optional[float] = None,
    citation_claims: Optional[List[CitationClaimAuditPreview | Dict[str, Any]]] = None,
) -> Optional[AuditDebugPreview]:
    if not enabled:
        return None
    preview = AuditDebugPreview()
    if query_text is not None:
        preview.query_preview = audit_preview_text(query_text, max_chars=max_preview_chars)
    if input_text is not None:
        preview.input_preview = audit_preview_text(input_text, max_chars=max_preview_chars)
    if output_text is not None:
        preview.output_preview = audit_preview_text(output_text, max_chars=max_preview_chars)
    if redactions is not None:
        preview.redactions = redactions
    if chunk_ids:
        preview.chunk_ids = list(chunk_ids)
    if citation_coverage_ratio is not None:
        preview.citation_coverage_ratio = float(citation_coverage_ratio)
    if citation_claims:
        normalized: List[CitationClaimAuditPreview] = []
        for claim in citation_claims[:20]:
            if isinstance(claim, CitationClaimAuditPreview):
                row = claim.model_copy(deep=True)
            elif isinstance(claim, dict):
                row = CitationClaimAuditPreview(
                    sentence=str(claim.get("sentence") or "")[:200],
                    chunk_id=claim.get("chunk_id"),
                    supported=bool(claim.get("supported")),
                    entailment_score=claim.get("entailment_score"),
                )
            else:
                continue
            row.sentence = audit_preview_text(row.sentence, max_chars=min(200, max_preview_chars)) or ""
            normalized.append(row)
        preview.citation_claims = normalized
    if (
        preview.query_preview is None
        and preview.input_preview is None
        and preview.output_preview is None
        and preview.redactions is None
        and not preview.chunk_ids
        and preview.citation_coverage_ratio is None
        and not preview.citation_claims
    ):
        return None
    return preview


def scrub_event_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(payload)
    out["detail"] = scrub_text(out.get("detail"))
    findings = []
    for finding in out.get("findings") or []:
        if not isinstance(finding, dict):
            continue
        item = dict(finding)
        item["snippet"] = scrub_text(item.get("snippet"))
        item["detail"] = scrub_text(item.get("detail"))
        findings.append(item)
    out["findings"] = findings
    debug = out.get("debug")
    if isinstance(debug, dict):
        item = dict(debug)
        item["query_preview"] = scrub_text(item.get("query_preview"))
        item["input_preview"] = scrub_text(item.get("input_preview"))
        item["output_preview"] = scrub_text(item.get("output_preview"))
        claims = []
        for claim in item.get("citation_claims") or []:
            if not isinstance(claim, dict):
                continue
            claim_row = dict(claim)
            claim_row["sentence"] = scrub_text(claim_row.get("sentence"))
            claims.append(claim_row)
        if claims or "citation_claims" in item:
            item["citation_claims"] = claims
        out["debug"] = item
    return out


def strip_debug_from_event_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Remove optional debug block from a serialized audit event dict."""
    if "debug" not in payload:
        return payload
    out = dict(payload)
    out.pop("debug", None)
    return out


def redact_audit_events_response(result: Dict[str, Any], *, include_debug: bool) -> Dict[str, Any]:
    """Strip debug previews from paginated admin audit event responses when required."""
    if include_debug:
        return result
    events = result.get("events")
    if not isinstance(events, list):
        return result
    redacted = dict(result)
    redacted["events"] = [
        strip_debug_from_event_payload(item) for item in events if isinstance(item, dict)
    ]
    return redacted


def _webhook_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    if _AUDIT_POLICY.get("debug_webhook"):
        return payload
    return strip_debug_from_event_payload(payload)


def strip_expired_debug_previews() -> int:
    """Remove debug previews from events older than debug_retention_hours (event row kept)."""
    hours = int(_AUDIT_POLICY.get("debug_retention_hours", 0) or 0)
    if hours <= 0:
        return 0
    cutoff = time.time() - (hours * 3600)
    stripped = 0

    if _BUFFER:
        refreshed: List[AuditEvent] = []
        for event in _BUFFER:
            if event.debug is not None and event.timestamp < cutoff:
                refreshed.append(event.model_copy(update={"debug": None}))
                stripped += 1
            else:
                refreshed.append(event)
        _BUFFER.clear()
        _BUFFER.extend(refreshed)

    if _AUDIT_FILE is not None and _AUDIT_FILE.exists():
        with _LOCK:
            lines = _AUDIT_FILE.read_text(encoding="utf-8").splitlines()
            rewritten: List[str] = []
            changed = False
            for line in lines:
                payload = _parse_event_line(line)
                if payload is None:
                    continue
                ts = float(payload.get("timestamp") or 0.0)
                if payload.get("debug") and ts < cutoff:
                    payload = strip_debug_from_event_payload(payload)
                    stripped += 1
                    changed = True
                rewritten.append(json.dumps(payload, separators=(",", ":")))
            if changed:
                if audit_integrity.chain_enabled():
                    payloads = [_parse_event_line(line) for line in rewritten]
                    chained = audit_integrity.rechain_payloads(
                        [p for p in payloads if isinstance(p, dict)]
                    )
                    rewritten = [json.dumps(p, separators=(",", ":")) for p in chained]
                    audit_integrity.persist_chain_tip(_AUDIT_FILE)
                _AUDIT_FILE.write_text(
                    ("\n".join(rewritten) + ("\n" if rewritten else "")),
                    encoding="utf-8",
                )

    return stripped


def apply_retention() -> int:
    """Prune events past their effective TTL (global, per-kind, or decision floor)."""
    _maybe_rotate_audit_file()
    retention_days = int(_AUDIT_POLICY.get("retention_days", 0) or 0)
    by_kind = dict(_AUDIT_POLICY.get("retention_by_kind") or {})
    by_decision = dict(_AUDIT_POLICY.get("retain_decisions") or {})
    if retention_days <= 0 and not by_kind and not by_decision:
        strip_expired_debug_previews()
        return 0
    default_days = retention_days if retention_days > 0 else 7
    now = time.time()
    removed = 0

    def _keep_payload(payload: Dict[str, Any]) -> bool:
        kind = str(payload.get("kind") or "")
        decision = str(payload.get("decision") or "")
        days = retention_days_for_event(kind, decision, default_days=default_days)
        if days <= 0:
            return True
        cutoff = now - (days * 86400)
        return float(payload.get("timestamp") or 0.0) >= cutoff

    if _AUDIT_FILE is not None and _AUDIT_FILE.exists():
        with _LOCK:
            lines = _AUDIT_FILE.read_text(encoding="utf-8").splitlines()
            kept: List[str] = []
            pruned: List[str] = []
            for line in lines:
                payload = _parse_event_line(line)
                if payload is None:
                    continue
                if not _keep_payload(payload):
                    pruned.append(line)
                    removed += 1
                    continue
                kept.append(line)
            if pruned:
                _append_audit_backup_lines(pruned, label="pruned")
                if audit_integrity.chain_enabled():
                    payloads = [_parse_event_line(line) for line in kept]
                    chained = audit_integrity.rechain_payloads(
                        [p for p in payloads if isinstance(p, dict)]
                    )
                    kept = [json.dumps(p, separators=(",", ":")) for p in chained]
                    audit_integrity.persist_chain_tip(_AUDIT_FILE)
                _AUDIT_FILE.write_text(
                    ("\n".join(kept) + ("\n" if kept else "")),
                    encoding="utf-8",
                )

    if _BUFFER:
        kept_events: List[AuditEvent] = []
        for event in list(_BUFFER):
            days = retention_days_for_event(
                event.kind,
                str(getattr(event.decision, "value", event.decision) or ""),
                default_days=default_days,
            )
            if days <= 0:
                kept_events.append(event)
                continue
            cutoff = now - (days * 86400)
            if event.timestamp >= cutoff:
                kept_events.append(event)
            else:
                removed += 1
        _BUFFER.clear()
        _BUFFER.extend(kept_events)

    strip_expired_debug_previews()
    _prune_audit_backups()
    return removed


def _audit_backup_dir() -> Path:
    override = os.getenv("RAG_AUDIT_BACKUP_DIR", "").strip()
    if override:
        return Path(override)
    if _AUDIT_FILE is not None:
        return _AUDIT_FILE.parent / "audit-backups"
    return Path("audit-backups")


def _rotation_marker_path() -> Optional[Path]:
    if _AUDIT_FILE is None:
        return None
    return _AUDIT_FILE.parent / f"{_AUDIT_FILE.name}.rotation"


def _read_last_rotation_day() -> Optional[str]:
    marker = _rotation_marker_path()
    if marker is None or not marker.exists():
        return None
    day = marker.read_text(encoding="utf-8").strip()
    if re.fullmatch(r"\d{8}", day):
        return day
    return None


def _write_last_rotation_day(day: str) -> None:
    marker = _rotation_marker_path()
    if marker is None:
        return
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(day, encoding="utf-8")


def _backup_keep_days() -> int:
    env_keep = os.getenv("RAG_AUDIT_BACKUP_KEEP", "").strip()
    if env_keep:
        return max(1, int(env_keep))
    return max(1, int(_AUDIT_POLICY.get("backup_keep_days", 7) or 7))


def _prune_audit_backups() -> None:
    backup_dir = _audit_backup_dir()
    if not backup_dir.exists():
        return
    cutoff = time.time() - (_backup_keep_days() * 86400)
    for path in backup_dir.glob("audit-*"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
        except OSError:
            logger.warning("Failed to prune audit backup %s", path)


def _append_audit_backup_lines(lines: List[str], *, label: str) -> None:
    if not lines or _AUDIT_FILE is None:
        return
    backup_dir = _audit_backup_dir()
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d", time.gmtime())
    backup_path = backup_dir / f"audit-{label}-{stamp}{_AUDIT_FILE.suffix}"
    payload = "\n".join(lines)
    if not payload.endswith("\n"):
        payload += "\n"
    with backup_path.open("a", encoding="utf-8") as fh:
        fh.write(payload)


def _maybe_rotate_audit_file() -> None:
    """Rotate the active JSONL file at UTC day boundary into audit-backups/."""
    if _AUDIT_FILE is None:
        return
    today = time.strftime("%Y%m%d", time.gmtime())
    last_day = _read_last_rotation_day()
    if last_day is None:
        _write_last_rotation_day(today)
        return
    if last_day >= today:
        return

    with _LOCK:
        last_day = _read_last_rotation_day()
        today = time.strftime("%Y%m%d", time.gmtime())
        if last_day is None:
            _write_last_rotation_day(today)
            return
        if last_day >= today:
            return
        if not _AUDIT_FILE.exists():
            _write_last_rotation_day(today)
            return
        content = _AUDIT_FILE.read_text(encoding="utf-8")
        if content.strip():
            backup_dir = _audit_backup_dir()
            backup_dir.mkdir(parents=True, exist_ok=True)
            rotated_path = backup_dir / f"audit-{last_day}{_AUDIT_FILE.suffix}"
            with rotated_path.open("a", encoding="utf-8") as fh:
                if not content.endswith("\n"):
                    content += "\n"
                fh.write(content)
            _AUDIT_FILE.write_text("", encoding="utf-8")
            # New day = new chain segment rooted at genesis (verify expects GENESIS).
            if audit_integrity.chain_enabled():
                audit_integrity.reset_chain_tip_to_genesis()
                audit_integrity.persist_chain_tip(_AUDIT_FILE)
            _prune_audit_backups()
        _write_last_rotation_day(today)


def reset_for_tests() -> None:
    """Clear in-memory buffer and sink configuration (tests only)."""
    global _AUDIT_FILE, _WEBHOOK_URL, _WEBHOOK_TIMEOUT, _WEBHOOK_HEADERS
    global _WEBHOOK_MAX_RETRIES, _WEBHOOK_BACKOFF_SECONDS, _DEAD_LETTER_FILE, _RECORDS_SINCE_PRUNE
    global _BUFFER, _SAMPLE_COUNTERS, _SAMPLE_DROPPED
    _BUFFER = deque(maxlen=int(os.getenv("RAG_AUDIT_BUFFER_SIZE", "1000")))
    _AUDIT_FILE = None
    _WEBHOOK_URL = None
    _WEBHOOK_TIMEOUT = 5.0
    _WEBHOOK_HEADERS = {}
    _WEBHOOK_MAX_RETRIES = 3
    _WEBHOOK_BACKOFF_SECONDS = 0.5
    _DEAD_LETTER_FILE = None
    _RECORDS_SINCE_PRUNE = 0
    _SAMPLE_COUNTERS = defaultdict(int)
    _SAMPLE_DROPPED = defaultdict(int)
    configure_audit_policy()
    audit_integrity.reset_integrity_for_tests()


def verify_audit_integrity(*, path: Optional[Path] = None, limit: Optional[int] = None) -> Dict[str, object]:
    """Verify hash chain for the configured audit file or an explicit path."""
    target = path or _AUDIT_FILE
    if target is None:
        return {
            "valid": False,
            "events_checked": 0,
            "error": "no audit file configured",
            "broken_at_line": None,
            "last_hash": None,
            "integrity_chain_enabled": audit_integrity.chain_enabled(),
        }
    result = audit_integrity.verify_audit_file(target, limit=limit)
    result["integrity_chain_enabled"] = audit_integrity.chain_enabled()
    result["audit_file"] = str(target)
    return result


def _persist_jsonl(payload: dict) -> None:
    if _AUDIT_FILE is None:
        return
    line = json.dumps(payload, separators=(",", ":")) + "\n"
    with _LOCK:
        with _AUDIT_FILE.open("a", encoding="utf-8") as fh:
            fh.write(line)
    if audit_integrity.chain_enabled():
        audit_integrity.persist_chain_tip(_AUDIT_FILE)


def _dispatch_webhook(payload: dict) -> None:
    if not _WEBHOOK_URL:
        return
    threading.Thread(
        target=_post_webhook,
        args=(payload,),
        daemon=True,
        name="audit-webhook",
    ).start()


def _post_webhook(payload: dict) -> None:
    last_exc: Optional[Exception] = None
    backoff = _WEBHOOK_BACKOFF_SECONDS
    for attempt in range(1, _WEBHOOK_MAX_RETRIES + 1):
        try:
            resp = httpx.post(
                _WEBHOOK_URL,
                json=payload,
                headers={"Content-Type": "application/json", **_WEBHOOK_HEADERS},
                timeout=_WEBHOOK_TIMEOUT,
            )
            resp.raise_for_status()
            return
        except Exception as exc:
            last_exc = exc
            if attempt < _WEBHOOK_MAX_RETRIES:
                logger.warning(
                    "Audit webhook delivery failed (attempt %d/%d): %s",
                    attempt,
                    _WEBHOOK_MAX_RETRIES,
                    exc,
                )
                time.sleep(backoff)
                backoff *= 2
    logger.error(
        "Audit webhook delivery failed after %d attempts: %s",
        _WEBHOOK_MAX_RETRIES,
        last_exc,
    )
    _write_dead_letter(payload, last_exc)


def _write_dead_letter(payload: dict, exc: Optional[Exception]) -> None:
    if _DEAD_LETTER_FILE is None:
        return
    entry = {
        "failed_at": time.time(),
        "error": str(exc) if exc else "unknown",
        "payload": payload,
    }
    line = json.dumps(entry, separators=(",", ":")) + "\n"
    with _LOCK:
        with _DEAD_LETTER_FILE.open("a", encoding="utf-8") as fh:
            fh.write(line)
