"""Pending tool-invoke CHALLENGE queue (L1-201 / D3).

Stores mid-risk invokes when ``defaults.challenge_mode: allow`` so an operator
can Approve (run backend once) or Deny (never run). Mirrors E5.5 ingest
quarantine semantics for tools.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class PendingToolChallenge:
    id: str
    tool: str
    arguments: Dict[str, Any]
    subject: str
    groups: List[str]
    tenant_id: str
    risk_score: float
    reason: str
    findings: List[Dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    status: str = "pending"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PendingToolChallenge":
        return cls(
            id=str(data["id"]),
            tool=str(data["tool"]),
            arguments=dict(data.get("arguments") or {}),
            subject=str(data.get("subject") or ""),
            groups=[str(g) for g in (data.get("groups") or [])],
            tenant_id=str(data.get("tenant_id") or "default"),
            risk_score=float(data.get("risk_score") or 0.0),
            reason=str(data.get("reason") or ""),
            findings=list(data.get("findings") or []),
            created_at=float(data.get("created_at") or time.time()),
            status=str(data.get("status") or "pending"),
        )


class ToolChallengeQueue:
    """JSON-file backed pending invoke store (tenant-scoped files under RAG_DATA_DIR)."""

    def __init__(self, root: Optional[Path] = None) -> None:
        self._root = Path(root) if root else Path(os.getenv("RAG_DATA_DIR", "./data"))
        self._lock = threading.RLock()

    def _path(self, tenant_id: str) -> Path:
        safe = (tenant_id or "default").replace("/", "_")
        return self._root / "tenants" / safe / "tool_challenges.json"

    def _load(self, tenant_id: str) -> Dict[str, PendingToolChallenge]:
        path = self._path(tenant_id)
        if not path.exists():
            return {}
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        items = raw.get("pending") if isinstance(raw, dict) else raw
        if not isinstance(items, list):
            return {}
        out: Dict[str, PendingToolChallenge] = {}
        for item in items:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            row = PendingToolChallenge.from_dict(item)
            if row.status == "pending":
                out[row.id] = row
        return out

    def _save(self, tenant_id: str, rows: Dict[str, PendingToolChallenge]) -> None:
        path = self._path(tenant_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"pending": [row.to_dict() for row in rows.values()]}
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(path)

    def enqueue(
        self,
        *,
        tool: str,
        arguments: Dict[str, Any],
        subject: str,
        groups: List[str],
        tenant_id: str,
        risk_score: float,
        reason: str,
        findings: List[Dict[str, Any]],
    ) -> PendingToolChallenge:
        row = PendingToolChallenge(
            id=str(uuid.uuid4()),
            tool=tool,
            arguments=dict(arguments or {}),
            subject=subject,
            groups=list(groups or []),
            tenant_id=tenant_id or "default",
            risk_score=risk_score,
            reason=reason,
            findings=list(findings or []),
        )
        with self._lock:
            rows = self._load(row.tenant_id)
            rows[row.id] = row
            self._save(row.tenant_id, rows)
        return row

    def list_pending(self, tenant_id: str = "default") -> List[PendingToolChallenge]:
        with self._lock:
            rows = self._load(tenant_id)
        return sorted(rows.values(), key=lambda r: r.created_at, reverse=True)

    def get(self, challenge_id: str, tenant_id: str = "default") -> Optional[PendingToolChallenge]:
        with self._lock:
            return self._load(tenant_id).get(challenge_id)

    def remove(self, challenge_id: str, tenant_id: str = "default") -> Optional[PendingToolChallenge]:
        with self._lock:
            rows = self._load(tenant_id)
            row = rows.pop(challenge_id, None)
            if row is not None:
                self._save(tenant_id, rows)
            return row

    def count_pending(self, tenant_id: str = "default") -> int:
        with self._lock:
            return len(self._load(tenant_id))


_queue: Optional[ToolChallengeQueue] = None
_queue_lock = threading.Lock()


def get_tool_challenge_queue() -> ToolChallengeQueue:
    global _queue
    with _queue_lock:
        if _queue is None:
            _queue = ToolChallengeQueue()
        return _queue


def reset_tool_challenge_queue_for_tests(root: Optional[Path] = None) -> ToolChallengeQueue:
    """Test helper — point the singleton at a fresh temp directory."""
    global _queue
    with _queue_lock:
        _queue = ToolChallengeQueue(root=root)
        return _queue
