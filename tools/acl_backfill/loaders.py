"""Load permissions matrices and group maps for ACL backfill."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Literal, Mapping, MutableMapping, Union

import yaml

PermFormat = Literal["auto", "drive", "flat", "notion"]
PermissionEntry = Union[List[str], List[Dict[str, Any]]]
PermissionsMap = Dict[str, PermissionEntry]


class LoaderError(ValueError):
    """Invalid permissions / group-map input."""


def load_group_map(path: Path | str) -> Dict[str, str]:
    """Load ``email|@domain → group`` map from YAML or JSON."""
    raw = _load_structured(Path(path))
    if not isinstance(raw, Mapping):
        raise LoaderError(f"group-map must be a mapping, got {type(raw).__name__}")
    out: Dict[str, str] = {}
    for key, value in raw.items():
        k = str(key).strip()
        v = str(value).strip()
        if not k or not v:
            raise LoaderError(f"group-map entry empty: {key!r} → {value!r}")
        out[k] = v
    if not out:
        raise LoaderError("group-map is empty")
    return out


def load_permissions(path: Path | str, *, perm_format: PermFormat = "auto") -> tuple[PermissionsMap, PermFormat]:
    """Load document_id → permissions (Drive/Notion) or flat groups.

    Returns ``(map, resolved_format)``.
    """
    p = Path(path)
    if p.suffix.lower() == ".csv":
        data = _load_permissions_csv(p)
        resolved: PermFormat = "flat"
        return data, resolved

    raw = _load_structured(p)
    if not isinstance(raw, Mapping):
        raise LoaderError(f"permissions must be a mapping, got {type(raw).__name__}")
    data = {str(k): _normalize_entry(v) for k, v in raw.items()}
    if not data:
        raise LoaderError("permissions file is empty")
    resolved = _resolve_format(data, perm_format)
    _validate_format(data, resolved)
    return data, resolved


def _load_structured(path: Path) -> Any:
    if not path.is_file():
        raise LoaderError(f"file not found: {path}")
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        return yaml.safe_load(text)
    if suffix == ".json":
        return json.loads(text)
    # Try JSON then YAML for extensionless / .txt exports.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return yaml.safe_load(text)


def _load_permissions_csv(path: Path) -> PermissionsMap:
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if not reader.fieldnames:
            raise LoaderError("CSV permissions file has no header")
        fields = {f.lower().strip(): f for f in reader.fieldnames}
        id_col = fields.get("document_id") or fields.get("doc_id") or fields.get("id")
        groups_col = fields.get("groups") or fields.get("allowed_groups")
        if not id_col or not groups_col:
            raise LoaderError(
                "CSV must include document_id (or doc_id) and groups (or allowed_groups) columns"
            )
        out: PermissionsMap = {}
        for row in reader:
            doc_id = str(row.get(id_col) or "").strip()
            if not doc_id:
                continue
            raw_groups = str(row.get(groups_col) or "").strip()
            groups = [g.strip() for g in raw_groups.split(",") if g.strip()]
            out[doc_id] = groups
        if not out:
            raise LoaderError("CSV permissions file has no data rows")
        return out


def _normalize_entry(value: Any) -> PermissionEntry:
    if value is None:
        return []
    if isinstance(value, str):
        return [g.strip() for g in value.split(",") if g.strip()]
    if isinstance(value, list):
        return list(value)
    raise LoaderError(f"permission entry must be a list or string, got {type(value).__name__}")


def _resolve_format(data: PermissionsMap, requested: PermFormat) -> PermFormat:
    if requested != "auto":
        return requested
    for entry in data.values():
        if not entry:
            continue
        first = entry[0]
        if isinstance(first, str):
            return "flat"
        if isinstance(first, Mapping):
            if "group" in first or "public" in first:
                return "notion"
            return "drive"
        raise LoaderError(f"unsupported permission entry type: {type(first).__name__}")
    return "flat"


def _validate_format(data: PermissionsMap, fmt: PermFormat) -> None:
    for doc_id, entry in data.items():
        if fmt == "flat":
            if not all(isinstance(x, str) for x in entry):
                raise LoaderError(f"{doc_id}: flat format requires string groups")
        else:
            if entry and not all(isinstance(x, Mapping) for x in entry):
                raise LoaderError(f"{doc_id}: {fmt} format requires permission objects")


def snapshot_from_mapping(raw: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Normalize a memory-backend store snapshot.

    Shape: ``{document_id: {allowed_groups: [...], metadata: {...}}}``.
    """
    out: Dict[str, Dict[str, Any]] = {}
    for doc_id, value in raw.items():
        if not isinstance(value, MutableMapping):
            raise LoaderError(f"snapshot entry for {doc_id!r} must be an object")
        groups = value.get("allowed_groups") or []
        if isinstance(groups, str):
            groups = [g.strip() for g in groups.split(",") if g.strip()]
        if not isinstance(groups, list):
            raise LoaderError(f"snapshot {doc_id!r}: allowed_groups must be a list")
        meta = value.get("metadata") or {}
        if not isinstance(meta, Mapping):
            raise LoaderError(f"snapshot {doc_id!r}: metadata must be an object")
        out[str(doc_id)] = {
            "allowed_groups": [str(g) for g in groups],
            "metadata": dict(meta),
        }
    return out


def load_store_snapshot(path: Path | str) -> Dict[str, Dict[str, Any]]:
    raw = _load_structured(Path(path))
    if not isinstance(raw, Mapping):
        raise LoaderError("store snapshot must be a mapping of document_id → state")
    return snapshot_from_mapping(raw)
