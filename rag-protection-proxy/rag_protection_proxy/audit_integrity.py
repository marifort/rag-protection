"""Hash-chained audit log integrity (T0.4).

Each persisted audit event includes ``prev_hash`` and ``event_hash`` linking to the
prior event. Verification replays the chain to detect tampering or truncation.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

GENESIS_HASH = hashlib.sha256(b"RAG_PROTECTION_AUDIT_GENESIS_v1").hexdigest()
_INTEGRITY_FIELDS = frozenset({"prev_hash", "event_hash"})

_last_hash: str = GENESIS_HASH
_enabled: bool = False


def configure_integrity_chain(*, enabled: bool) -> None:
    global _enabled, _last_hash
    _enabled = bool(enabled)
    if not _enabled:
        _last_hash = GENESIS_HASH


def reset_integrity_for_tests() -> None:
    configure_integrity_chain(enabled=False)


def reset_chain_tip_to_genesis() -> None:
    """Start a new chain segment (used after daily rotation empties the active file)."""
    global _last_hash
    _last_hash = GENESIS_HASH


def chain_tip() -> str:
    return _last_hash


def chain_enabled() -> bool:
    return _enabled


def _canonical_body(payload: Dict[str, Any]) -> str:
    body = {k: v for k, v in payload.items() if k not in _INTEGRITY_FIELDS}
    return json.dumps(body, sort_keys=True, separators=(",", ":"))


def _compute_event_hash(prev_hash: str, payload: Dict[str, Any]) -> str:
    material = f"{prev_hash}:{_canonical_body(payload)}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def append_chain_fields(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Mutate payload with chain fields when integrity is enabled."""
    global _last_hash
    if not _enabled:
        return payload
    out = dict(payload)
    prev = _last_hash
    event_hash = _compute_event_hash(prev, out)
    out["prev_hash"] = prev
    out["event_hash"] = event_hash
    _last_hash = event_hash
    return out


def rechain_payloads(payloads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Rewrite integrity fields so the sequence forms a valid chain from genesis.

    Used after retention prune or debug-strip rewrites the active JSONL so verify
    still starts at GENESIS_HASH. Does not require ``_enabled``.
    """
    global _last_hash
    prev = GENESIS_HASH
    out: List[Dict[str, Any]] = []
    for payload in payloads:
        body = {k: v for k, v in payload.items() if k not in _INTEGRITY_FIELDS}
        event_hash = _compute_event_hash(prev, body)
        body["prev_hash"] = prev
        body["event_hash"] = event_hash
        prev = event_hash
        out.append(body)
    _last_hash = prev
    return out


def rechain_audit_file(audit_file: Path) -> Dict[str, Any]:
    """Recompute prev_hash/event_hash for every JSON object line from genesis."""
    if not audit_file.is_file():
        reset_chain_tip_to_genesis()
        return {"rewritten": 0, "last_hash": GENESIS_HASH}
    payloads: List[Dict[str, Any]] = []
    for line in audit_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            payloads.append(obj)
    chained = rechain_payloads(payloads)
    text = "".join(json.dumps(p, separators=(",", ":")) + "\n" for p in chained)
    audit_file.write_text(text, encoding="utf-8")
    if _enabled:
        persist_chain_tip(audit_file)
    return {"rewritten": len(chained), "last_hash": _last_hash}


def _chain_state_path(audit_file: Path) -> Path:
    return audit_file.with_suffix(audit_file.suffix + ".chain")


def persist_chain_tip(audit_file: Path) -> None:
    if not _enabled:
        return
    path = _chain_state_path(audit_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"last_hash": _last_hash}, separators=(",", ":")), encoding="utf-8")


def load_chain_tip(audit_file: Optional[Path]) -> None:
    """Restore chain tip from the active audit file (heal legacy non-genesis segments)."""
    global _last_hash
    if not _enabled:
        _last_hash = GENESIS_HASH
        return
    if audit_file is None:
        _last_hash = GENESIS_HASH
        return
    if audit_file.is_file() and audit_file.stat().st_size > 0:
        result = verify_audit_file(audit_file)
        if result.get("valid") and result.get("last_hash"):
            _last_hash = str(result["last_hash"])
            persist_chain_tip(audit_file)
            return
        # Legacy daily rotation / prune left a segment that does not start at genesis.
        # Re-anchor once so verify and append agree. Mid-chain tamper is not auto-healed.
        if result.get("error") == "prev_hash mismatch" and int(result.get("broken_at_line") or 0) == 1:
            rechain_audit_file(audit_file)
            return
        if result.get("last_hash"):
            _last_hash = str(result["last_hash"])
            persist_chain_tip(audit_file)
            return
    # Empty or missing active file (e.g. just rotated): always start a new segment.
    _last_hash = GENESIS_HASH
    persist_chain_tip(audit_file)


def verify_audit_file(path: Path, *, limit: Optional[int] = None) -> Dict[str, Any]:
    """Verify hash chain in a JSONL audit file."""
    if not path.is_file():
        return {
            "valid": False,
            "events_checked": 0,
            "error": f"file not found: {path}",
            "broken_at_line": None,
            "last_hash": None,
        }
    prev = GENESIS_HASH
    checked = 0
    line_no = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        line_no += 1
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            return {
                "valid": False,
                "events_checked": checked,
                "error": "invalid JSON",
                "broken_at_line": line_no,
                "last_hash": prev,
            }
        if not isinstance(payload, dict):
            continue
        if "prev_hash" not in payload or "event_hash" not in payload:
            continue
        if str(payload.get("prev_hash")) != prev:
            return {
                "valid": False,
                "events_checked": checked,
                "error": "prev_hash mismatch",
                "broken_at_line": line_no,
                "last_hash": prev,
            }
        expected = _compute_event_hash(prev, payload)
        if str(payload.get("event_hash")) != expected:
            return {
                "valid": False,
                "events_checked": checked,
                "error": "event_hash mismatch",
                "broken_at_line": line_no,
                "last_hash": prev,
            }
        prev = str(payload["event_hash"])
        checked += 1
        if limit is not None and checked >= limit:
            break
    if checked == 0:
        return {
            "valid": True,
            "events_checked": 0,
            "error": None,
            "broken_at_line": None,
            "last_hash": GENESIS_HASH,
            "note": "no chained events in file",
        }
    return {
        "valid": True,
        "events_checked": checked,
        "error": None,
        "broken_at_line": None,
        "last_hash": prev,
    }
