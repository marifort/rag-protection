"""Canary / honeypot document tripwire (Lab 10).

A canary is an ordinary stored document tagged with marker metadata. Under correct
ACL enforcement a canary seeded to the reserved ``__canary__`` group is never
retrievable by a real user, so any retrieval of a canary by a non-auditor subject
is an unambiguous, high-signal alarm that enforcement has broken (or that a scraper
surfaced the decoy). This module owns seeding, the retrieval-time trap, an optional
output-path backstop, and audit recording.
"""

from __future__ import annotations

import json
import secrets
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from rag_protection_proxy.audit import record
from rag_protection_proxy.config import CanaryPolicy
from rag_protection_proxy.models import AuditEvent, Decision, Finding
from rag_protection_proxy.store import DocumentStoreBackend, new_document_id

CANARY_GROUP = "__canary__"
CANARY_KIND = "canary_triggered"

_META_CANARY = "canary"
_META_TOKEN = "canary_token"
_META_SENSITIVITY = "canary_sensitivity"


@dataclass(frozen=True)
class CanaryHit:
    document_id: str
    chunk_id: str
    subject: str
    tenant_id: str
    token: Optional[str]
    sensitivity: str
    stage: str  # "retrieval" | "output"


def generate_canary_token() -> str:
    """Unique, greppable marker embedded in canary bodies and metadata."""
    return f"RAGCANARY-{secrets.token_hex(8)}"


def _default_bait(token: str) -> str:
    return (
        "CONFIDENTIAL — RESTRICTED DISTRIBUTION. This record is a security control "
        "marker and must never appear in an answer to an ordinary user. "
        f"Reference: {token}."
    )


def is_metadata_canary(metadata: Optional[Dict[str, Any]]) -> bool:
    return bool(metadata) and bool(metadata.get(_META_CANARY))


def is_authorized_auditor(auth: Any, policy: CanaryPolicy) -> bool:
    """True when the subject/groups may retrieve canaries without tripping the alarm."""
    subject = getattr(auth, "subject", None)
    if subject and subject in set(policy.auditor_subjects):
        return True
    groups = set(getattr(auth, "groups", []) or [])
    return bool(groups & set(policy.auditor_groups))


def seed_canary(
    store: DocumentStoreBackend,
    *,
    title: str,
    body: Optional[str] = None,
    sensitivity: str = "restricted",
    allowed_groups: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Seed a canary document and return its record.

    Defaults to the reserved ``__canary__`` group (pure tripwire — unreachable under
    correct ACL). Pass ``allowed_groups`` for a reachable honeypot (e.g. demos/tests).
    """
    token = generate_canary_token()
    document_id = new_document_id(prefix="canary")
    content = body or _default_bait(token)
    groups = allowed_groups if allowed_groups else [CANARY_GROUP]
    metadata = {
        _META_CANARY: True,
        _META_TOKEN: token,
        _META_SENSITIVITY: sensitivity,
    }
    store.ingest(
        document_id=document_id,
        title=title,
        content=content,
        allowed_groups=groups,
        metadata=metadata,
    )
    return {
        "document_id": document_id,
        "title": title,
        "canary_token": token,
        "sensitivity": sensitivity,
        "allowed_groups": groups,
        "seeded_at": time.time(),
    }


def list_canaries(store: DocumentStoreBackend) -> List[Dict[str, Any]]:
    canaries: List[Dict[str, Any]] = []
    for doc in store.list_documents():
        metadata = doc.get("metadata") or {}
        if not is_metadata_canary(metadata):
            continue
        canaries.append(
            {
                "document_id": doc.get("document_id"),
                "title": doc.get("title"),
                "canary_token": metadata.get(_META_TOKEN),
                "sensitivity": metadata.get(_META_SENSITIVITY, "restricted"),
                "allowed_groups": doc.get("allowed_groups", []),
                "created_at": doc.get("created_at"),
            }
        )
    return canaries


def canary_tokens(store: DocumentStoreBackend) -> List[str]:
    return [c["canary_token"] for c in list_canaries(store) if c.get("canary_token")]


def inspect_candidates(chunks: Iterable[Any], auth: Any, policy: CanaryPolicy) -> Optional[CanaryHit]:
    """Return the first canary hit in a candidate set for a non-auditor subject.

    ``chunks`` are ``StoredChunk`` instances (``.metadata`` / ``.document_id`` / ``.chunk_id``).
    """
    if not policy.enabled:
        return None
    if is_authorized_auditor(auth, policy):
        return None
    for chunk in chunks:
        metadata = getattr(chunk, "metadata", None)
        if is_metadata_canary(metadata):
            return CanaryHit(
                document_id=getattr(chunk, "document_id", ""),
                chunk_id=getattr(chunk, "chunk_id", ""),
                subject=getattr(auth, "subject", "unknown"),
                tenant_id=getattr(auth, "tenant_id", "default"),
                token=metadata.get(_META_TOKEN),
                sensitivity=metadata.get(_META_SENSITIVITY, "restricted"),
                stage="retrieval",
            )
    return None


def filter_canaries(chunks: Iterable[Any]) -> List[Any]:
    """Drop canary chunks so they never enter context or the response."""
    return [c for c in chunks if not is_metadata_canary(getattr(c, "metadata", None))]


def find_canary_token_in_text(text: str, tokens: Iterable[str]) -> Optional[str]:
    if not text:
        return None
    for token in tokens:
        if token and token in text:
            return token
    return None


def record_canary_event(hit: CanaryHit) -> None:
    record(
        AuditEvent(
            timestamp=time.time(),
            kind=CANARY_KIND,
            decision=Decision.BLOCK,
            risk_score=1.0,
            subject=hit.subject,
            tenant_id=hit.tenant_id,
            source=f"{hit.stage}.canary",
            findings=[
                Finding(
                    scanner="canary",
                    category="acl_tripwire",
                    severity=1.0,
                    label=hit.sensitivity,
                    detail=f"canary {hit.document_id} surfaced at {hit.stage}",
                )
            ],
            detail=json.dumps(
                {
                    "document_id": hit.document_id,
                    "chunk_id": hit.chunk_id,
                    "canary_token": hit.token,
                    "stage": hit.stage,
                    "sensitivity": hit.sensitivity,
                },
                separators=(",", ":"),
            ),
        )
    )
