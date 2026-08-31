"""Tool gateway policy loading."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


class ToolPolicyValidationError(ValueError):
    """Raised when tool_policy.yaml is invalid."""


@dataclass
class ToolPolicyEntry:
    name: str
    description: str
    backend: str
    allowed_groups: List[str] = field(default_factory=lambda: ["all-staff"])
    max_args_bytes: int = 4096
    blocked_patterns: List[str] = field(default_factory=list)
    blocked_domains: List[str] = field(default_factory=list)
    scan_arguments: List[str] = field(default_factory=list)
    mcp_tool: Optional[str] = None
    description_blocked: bool = False
    description_findings_count: int = 0


@dataclass
class ToolGatewayPolicy:
    tools: Dict[str, ToolPolicyEntry] = field(default_factory=dict)
    challenge_threshold: float = 0.4
    block_threshold: float = 0.8
    challenge_mode: str = "block"
    source_path: Optional[str] = None


def default_tool_policy_path() -> Path:
    return Path(os.getenv("RAG_TOOL_POLICY_FILE", "./config/tool_policy.yaml"))


def _path_is_writable(path: Path) -> bool:
    """Return True only if we can actually write (os.access lies on some Docker RO mounts)."""
    try:
        if path.exists():
            with path.open("a", encoding="utf-8"):
                return True
        parent = path.parent
        parent.mkdir(parents=True, exist_ok=True)
        probe = parent / f".rp_write_probe_{os.getpid()}"
        probe.write_text("", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def tool_policy_writable_path() -> Path:
    """Writable path for registry CRUD — falls back to RAG_DATA_DIR when source is RO."""
    override = os.getenv("RAG_TOOL_POLICY_WRITABLE_FILE", "").strip()
    if override:
        return Path(override)
    source = default_tool_policy_path()
    if _path_is_writable(source):
        return source
    return Path(os.getenv("RAG_DATA_DIR", "./data")) / source.name


def ensure_writable_tool_policy_file() -> Path:
    """Return the tool policy used for load/save; seed from source when the image mount is read-only.

    Docker MCP overlay sets ``RAG_TOOL_POLICY_FILE=/app/config/tool_policy.mcp.yaml`` which is
    not writable in the container. Mirror the RAG ``ensure_writable_policy_file`` pattern so
    EE registry CRUD can persist under ``RAG_DATA_DIR``.
    """
    source = default_tool_policy_path()
    writable = tool_policy_writable_path()
    writable.parent.mkdir(parents=True, exist_ok=True)
    if not writable.exists():
        if not source.exists():
            raise ToolPolicyValidationError(f"Tool policy file not found: {source}")
        writable.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return writable


def load_tool_policy(path: Optional[str] = None) -> ToolGatewayPolicy:
    policy_path = Path(path) if path else ensure_writable_tool_policy_file()
    if not policy_path.exists():
        raise ToolPolicyValidationError(f"Tool policy file not found: {policy_path}")

    raw = yaml.safe_load(policy_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ToolPolicyValidationError("tool_policy.yaml root must be a mapping")

    defaults = raw.get("defaults") or {}
    if not isinstance(defaults, dict):
        raise ToolPolicyValidationError("defaults must be a mapping")

    tools_raw = raw.get("tools") or {}
    if not isinstance(tools_raw, dict):
        raise ToolPolicyValidationError("tools must be a mapping")

    tools: Dict[str, ToolPolicyEntry] = {}
    for name, entry in tools_raw.items():
        if not isinstance(entry, dict):
            raise ToolPolicyValidationError(f"tools.{name} must be a mapping")
        backend = str(entry.get("backend") or "").strip()
        if not backend:
            raise ToolPolicyValidationError(f"tools.{name}.backend is required")
        description = str(entry.get("description") or "").strip()
        if not description:
            raise ToolPolicyValidationError(f"tools.{name}.description is required")

        mcp_tool_raw = entry.get("mcp_tool")
        mcp_tool = str(mcp_tool_raw).strip() if mcp_tool_raw else None

        tools[name] = ToolPolicyEntry(
            name=name,
            description=description,
            backend=backend,
            allowed_groups=_as_str_list(entry.get("allowed_groups"), default=["all-staff"]),
            max_args_bytes=max(256, int(entry.get("max_args_bytes") or 4096)),
            blocked_patterns=_as_str_list(entry.get("blocked_patterns")),
            blocked_domains=[d.lower() for d in _as_str_list(entry.get("blocked_domains"))],
            scan_arguments=_as_str_list(entry.get("scan_arguments")),
            mcp_tool=mcp_tool or None,
        )

    return ToolGatewayPolicy(
        tools=tools,
        challenge_threshold=float(defaults.get("challenge_threshold", 0.4)),
        block_threshold=float(defaults.get("block_threshold", 0.8)),
        challenge_mode=str(defaults.get("challenge_mode", "block")),
        source_path=str(policy_path.resolve()),
    )


def _as_str_list(value: Any, default: Optional[List[str]] = None) -> List[str]:
    if value is None:
        return list(default or [])
    if isinstance(value, str):
        return [value.strip()] if value.strip() else list(default or [])
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    raise ToolPolicyValidationError("Expected string or list of strings")


def caller_allowed_for_tool(caller_groups: List[str], tool: ToolPolicyEntry) -> bool:
    caller = set(caller_groups)
    return bool(caller.intersection(tool.allowed_groups))


def args_byte_size(arguments: Dict[str, Any]) -> int:
    import json

    return len(json.dumps(arguments, separators=(",", ":"), default=str).encode("utf-8"))


def find_blocked_patterns(arguments: Dict[str, Any], patterns: List[str]) -> List[str]:
    hits: List[str] = []
    for key, value in arguments.items():
        if not isinstance(value, str):
            continue
        haystack = value
        for pattern in patterns:
            if pattern and pattern in haystack:
                hits.append(f"{key}: matched blocked pattern {pattern!r}")
    return hits


_EMAIL_RE = re.compile(r"[\w.+-]+@([\w.-]+\.[A-Za-z]{2,})")


def find_blocked_domains(arguments: Dict[str, Any], domains: List[str]) -> List[str]:
    if not domains:
        return []
    blocked = {d.lower() for d in domains}
    hits: List[str] = []
    for key, value in arguments.items():
        if not isinstance(value, str):
            continue
        for match in _EMAIL_RE.finditer(value):
            domain = match.group(1).lower()
            if domain in blocked:
                hits.append(f"{key}: blocked domain {domain!r}")
    return hits


def tool_entry_to_dict(entry: ToolPolicyEntry) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "description": entry.description,
        "backend": entry.backend,
        "allowed_groups": list(entry.allowed_groups),
        "max_args_bytes": entry.max_args_bytes,
    }
    if entry.blocked_patterns:
        payload["blocked_patterns"] = list(entry.blocked_patterns)
    if entry.blocked_domains:
        payload["blocked_domains"] = list(entry.blocked_domains)
    if entry.scan_arguments:
        payload["scan_arguments"] = list(entry.scan_arguments)
    if entry.mcp_tool:
        payload["mcp_tool"] = entry.mcp_tool
    return payload


def tool_entry_admin_dict(entry: ToolPolicyEntry) -> Dict[str, Any]:
    """Serialize a tool for operator console (includes runtime deny flags)."""
    payload = tool_entry_to_dict(entry)
    payload["name"] = entry.name
    payload["description_blocked"] = bool(entry.description_blocked)
    payload["description_findings_count"] = int(entry.description_findings_count or 0)
    return payload


def tool_policy_admin_summary(policy: ToolGatewayPolicy, registry: Dict[str, ToolPolicyEntry]) -> Dict[str, Any]:
    """Read-only tool gateway summary for GET /admin/tools/policy."""
    tools = {
        name: tool_entry_admin_dict(entry)
        for name, entry in sorted(registry.items(), key=lambda item: item[0])
    }
    return {
        "source_path": policy.source_path,
        "tool_count": len(tools),
        "defaults": {
            "challenge_threshold": policy.challenge_threshold,
            "block_threshold": policy.block_threshold,
            "challenge_mode": policy.challenge_mode,
        },
        "tools": tools,
    }


def tool_policy_to_yaml(policy: ToolGatewayPolicy) -> str:
    raw: Dict[str, Any] = {
        "defaults": {
            "challenge_threshold": policy.challenge_threshold,
            "block_threshold": policy.block_threshold,
            "challenge_mode": policy.challenge_mode,
        },
        "tools": {name: tool_entry_to_dict(entry) for name, entry in sorted(policy.tools.items())},
    }
    return yaml.safe_dump(raw, sort_keys=False, default_flow_style=False)


def save_tool_policy(policy: ToolGatewayPolicy, path: Optional[str] = None) -> Path:
    """Persist tool policy YAML, falling back to ``RAG_DATA_DIR`` when the source mount is read-only."""
    payload = tool_policy_to_yaml(policy)
    attempts: List[Path] = []
    if path:
        attempts.append(Path(path))
    try:
        attempts.append(ensure_writable_tool_policy_file())
    except ToolPolicyValidationError:
        # Explicit-path unit tests may not set RAG_TOOL_POLICY_FILE.
        pass
    data_fallback = Path(os.getenv("RAG_DATA_DIR", "./data")) / default_tool_policy_path().name
    if data_fallback.resolve() not in {p.resolve() for p in attempts}:
        attempts.append(data_fallback)

    if not attempts:
        raise ToolPolicyValidationError("No tool policy path available to write")

    last_error: Optional[OSError] = None
    for policy_path in attempts:
        try:
            policy_path.parent.mkdir(parents=True, exist_ok=True)
            policy_path.write_text(payload, encoding="utf-8")
            return policy_path.resolve()
        except OSError as exc:
            last_error = exc
            continue
    raise ToolPolicyValidationError(
        f"Tool policy is not writable (tried {', '.join(str(p) for p in attempts)}): {last_error}"
    ) from last_error
