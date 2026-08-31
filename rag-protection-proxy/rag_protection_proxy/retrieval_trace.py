"""Retrieval-decision explainability (T0.7).

Explains why each candidate chunk was selected or excluded at retrieval time.
"""

from __future__ import annotations

import json
import time
from typing import Any, List, Optional, Tuple

from rag_protection_proxy.acl import user_can_access_document
from rag_protection_proxy.audit import record
from rag_protection_proxy.config import RetrievalPolicy
from rag_protection_proxy.models import AuditEvent, Decision, RetrievalDecision
from rag_protection_proxy.store import DocumentStore, StoredChunk, _is_quarantined, _score_overlap, _tokenize


def explain_search(
    store: Any,
    query: str,
    user_groups: List[str],
    *,
    top_k: int = 4,
    rules: RetrievalPolicy,
) -> Tuple[List[StoredChunk], List[RetrievalDecision]]:
    """Return selected chunks and a per-candidate retrieval trace."""
    traced = getattr(store, "search_with_trace", None)
    if traced is not None:
        return traced(query, user_groups, top_k=top_k, max_trace_candidates=rules.max_trace_candidates)
    if isinstance(store, DocumentStore):
        return store.search_with_trace(
            query, user_groups, top_k=top_k, max_trace_candidates=rules.max_trace_candidates
        )
    chunks = store.search(query, user_groups, top_k=top_k)
    decisions = [
        RetrievalDecision(
            chunk_id=c.chunk_id,
            document_id=c.document_id,
            title=c.title,
            score=c.score,
            outcome="selected",
            detail="trace unavailable for store backend",
        )
        for c in chunks
    ]
    return chunks, decisions


def record_retrieval_trace(
    *,
    subject: str,
    tenant_id: str,
    query: str,
    decisions: List[RetrievalDecision],
) -> None:
    selected = sum(1 for d in decisions if d.outcome == "selected")
    record(
        AuditEvent(
            timestamp=time.time(),
            kind="retrieval_trace",
            decision=Decision.ALLOW,
            risk_score=0.0,
            subject=subject,
            tenant_id=tenant_id,
            source="retrieval.explain",
            detail=json.dumps(
                {
                    "query_len": len(query or ""),
                    "candidates": len(decisions),
                    "selected": selected,
                    "trace": [d.model_dump() for d in decisions[:50]],
                },
                separators=(",", ":"),
            ),
        )
    )
