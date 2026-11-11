"""Agent access-matrix scanner (competency — fixture IdP, not a CASB).

Skill: CISOs ask 'what can this Copilot actually do in Graph / Jira / SQL?'
This CLI answers from two JSON files: Entra grants on a service principal, and
the MCP ``tools/list`` the agent was given. It flags least-privilege breaks.

Not in scope: live Graph crawl, Slack/Confluence connectors, network shadow AI.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Sequence


@dataclass
class AccessFinding:
    code: str
    severity: str  # high | medium | low
    entity: str
    detail: str

    def as_dict(self) -> Dict[str, str]:
        return asdict(self)


def _as_scope_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [p for p in value.replace(",", " ").split() if p]
    if isinstance(value, list):
        out: List[str] = []
        for item in value:
            out.extend(_as_scope_list(item))
        return out
    return []


def _load_json(path: Path) -> Dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path} root must be a JSON object")
    return raw


def scan_access_matrix(
    entra: Dict[str, Any],
    mcp_tools: Dict[str, Any],
) -> List[AccessFinding]:
    """Compare SP grants to tool requirements. Pure function — fixtures or live JSON."""
    findings: List[AccessFinding] = []
    tools = mcp_tools.get("tools") or []
    if not isinstance(tools, list):
        raise ValueError("mcp_tools.tools must be a list")

    required_scopes: List[str] = []
    delegated_tools: List[str] = []
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        name = str(tool.get("name") or "unknown")
        mode = str(tool.get("identity_mode") or "delegated").lower()
        scopes = _as_scope_list(tool.get("required_scopes"))
        required_scopes.extend(scopes)
        if mode in {"delegated", "obo"}:
            delegated_tools.append(name)
        if mode in {"delegated", "obo"} and not scopes:
            findings.append(
                AccessFinding(
                    code="MATRIX006",
                    severity="medium",
                    entity=name,
                    detail="Tool declares delegated/OBO identity but lists no required_scopes",
                )
            )

    required_set = set(required_scopes)
    sps = entra.get("service_principals") or []
    if not isinstance(sps, list):
        raise ValueError("entra.service_principals must be a list")

    for sp in sps:
        if not isinstance(sp, dict):
            continue
        display = str(sp.get("displayName") or sp.get("appId") or "service-principal")
        app_roles = _collect_app_roles(sp)
        delegated = _collect_delegated_scopes(sp)

        if app_roles and delegated_tools:
            findings.append(
                AccessFinding(
                    code="MATRIX001",
                    severity="high",
                    entity=display,
                    detail=(
                        "Application permissions present while MCP tools declare delegated/OBO "
                        f"({', '.join(sorted(app_roles))}). Downstream APIs will run as the bot."
                    ),
                )
            )

        if delegated_tools and app_roles and not delegated:
            findings.append(
                AccessFinding(
                    code="MATRIX004",
                    severity="high",
                    entity=display,
                    detail=(
                        "Tools require delegated identity but this SP has only app roles — "
                        "no oauth2PermissionGrants"
                    ),
                )
            )

        for role in app_roles:
            if role.endswith(".All") or role in {"Files.ReadWrite.All", "Mail.ReadWrite", "Directory.ReadWrite.All"}:
                findings.append(
                    AccessFinding(
                        code="MATRIX005",
                        severity="high",
                        entity=display,
                        detail=f"Standing application role {role!r} is broader than any named tool",
                    )
                )

        unused = sorted(delegated - required_set)
        for scope in unused:
            findings.append(
                AccessFinding(
                    code="MATRIX002",
                    severity="medium",
                    entity=display,
                    detail=f"Delegated scope {scope!r} is granted but no MCP tool lists it",
                )
            )

        missing = sorted(required_set - delegated)
        for scope in missing:
            findings.append(
                AccessFinding(
                    code="MATRIX003",
                    severity="medium",
                    entity=display,
                    detail=f"MCP tools require {scope!r} but this SP has no matching delegated grant",
                )
            )

    return findings


def _collect_app_roles(sp: Dict[str, Any]) -> List[str]:
    roles: List[str] = []
    for row in sp.get("appRoleAssignments") or []:
        if not isinstance(row, dict):
            continue
        role = str(row.get("role") or row.get("appRole") or "").strip()
        if role:
            roles.append(role)
    return roles


def _collect_delegated_scopes(sp: Dict[str, Any]) -> set[str]:
    scopes: set[str] = set()
    for row in sp.get("oauth2PermissionGrants") or []:
        if not isinstance(row, dict):
            continue
        scopes.update(_as_scope_list(row.get("scope") or row.get("scopes")))
    return scopes


def scan_files(entra_path: Path, tools_path: Path) -> List[AccessFinding]:
    return scan_access_matrix(_load_json(entra_path), _load_json(tools_path))


def format_text(findings: Sequence[AccessFinding]) -> str:
    if not findings:
        return "No least-privilege findings."
    lines = [f"{len(findings)} finding(s):", ""]
    for item in findings:
        lines.append(f"[{item.severity.upper()}] {item.code}  {item.entity}")
        lines.append(f"  {item.detail}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def default_fixture_dir() -> Path:
    return Path(__file__).resolve().parent / "fixtures"
