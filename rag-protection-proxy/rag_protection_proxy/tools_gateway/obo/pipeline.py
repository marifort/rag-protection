"""Identity-bound invoke: group allowlist + OBO + resource, one function.

This is the study pipeline. It is **not** wired into POST /v1/tools/invoke.
#7 still stops at 'this group may call this tool' and then hits a mock backend
as nobody-in-particular.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

from rag_protection_proxy.tools_gateway.obo.exchange import (
    AppOnlyDenied,
    DownscopeEmpty,
    OboDenied,
    exchange_on_behalf_of,
)
from rag_protection_proxy.tools_gateway.obo.resource import (
    ResourceDenied,
    call_mock_jira,
    call_mock_mail,
    call_mock_sql,
)
from rag_protection_proxy.tools_gateway.obo.tokens import (
    AGENT_CLIENT_ID,
    JIRA_AUD,
    MAIL_AUD,
    SQL_AUD,
    TokenError,
    decode_lab_token,
)


@dataclass(frozen=True)
class ToolOboPolicy:
    name: str
    allowed_groups: List[str]
    allowed_scopes: List[str]
    resource_audience: str
    required_scope: str


DEFAULT_TOOL_POLICIES: Dict[str, ToolOboPolicy] = {
    "run_sql": ToolOboPolicy(
        name="run_sql",
        allowed_groups=["data-platform"],
        allowed_scopes=["SQL.Read"],
        resource_audience=SQL_AUD,
        required_scope="SQL.Read",
    ),
    "send_email": ToolOboPolicy(
        name="send_email",
        allowed_groups=["hr", "engineering", "all-staff"],
        allowed_scopes=["Mail.Send"],
        resource_audience=MAIL_AUD,
        required_scope="Mail.Send",
    ),
    "jira_get_issue": ToolOboPolicy(
        name="jira_get_issue",
        allowed_groups=["engineering", "all-staff"],
        allowed_scopes=["Jira.Read"],
        resource_audience=JIRA_AUD,
        required_scope="Jira.Read",
    ),
}


@dataclass
class IdentityBoundResult:
    tool: str
    decision: str  # allow | block
    reason: str
    subject: Optional[str] = None
    actor_app: Optional[str] = None
    grant: Optional[str] = None
    exchanged_scp: List[str] = field(default_factory=list)
    result: Optional[Dict[str, Any]] = None

    @property
    def blocked(self) -> bool:
        return self.decision != "allow"

    def audit(self) -> Dict[str, Any]:
        return {
            "kind": "tool_invoke_obo",
            "tool": self.tool,
            "decision": self.decision,
            "reason": self.reason,
            "subject": self.subject,
            "actor_app": self.actor_app,
            "grant": self.grant,
            "exchanged_scp": list(self.exchanged_scp),
        }


_RESOURCE_CALLERS: Dict[str, Callable[..., Dict[str, Any]]] = {
    "run_sql": lambda token, arguments, secret: call_mock_sql(
        token, query=str(arguments.get("query") or ""), secret=secret
    ),
    "send_email": lambda token, arguments, secret: call_mock_mail(
        token,
        to=str(arguments.get("to") or ""),
        subject=str(arguments.get("subject") or ""),
        secret=secret,
    ),
    "jira_get_issue": lambda token, arguments, secret: call_mock_jira(
        token, issue_key=str(arguments.get("issue_key") or ""), secret=secret
    ),
}


def _groups_allowed(caller_groups: Sequence[str], policy: ToolOboPolicy) -> bool:
    return bool(set(caller_groups).intersection(policy.allowed_groups))


def invoke_identity_bound(
    *,
    inbound_token: str,
    tool: str,
    arguments: Dict[str, Any],
    requested_scopes: Optional[Sequence[str]] = None,
    agent_client_id: str = AGENT_CLIENT_ID,
    policies: Optional[Dict[str, ToolOboPolicy]] = None,
    secret: Optional[str] = None,
) -> IdentityBoundResult:
    """Group gate → OBO exchange → resource call.

    ``requested_scopes`` defaults to the tool's allowed scopes (honest agent).
    Pass Graph-admin scopes to see downscope or DownscopeEmpty.
    """
    table = policies or DEFAULT_TOOL_POLICIES
    policy = table.get(tool)
    if policy is None:
        return IdentityBoundResult(tool=tool, decision="block", reason=f"Unknown tool: {tool}")

    try:
        inbound = decode_lab_token(inbound_token, secret=secret)
    except TokenError as exc:
        return IdentityBoundResult(tool=tool, decision="block", reason=f"invalid inbound token: {exc}")

    if inbound.is_app_only:
        return IdentityBoundResult(
            tool=tool,
            decision="block",
            reason="app-only token: agent would call the API as a service account",
            subject=inbound.oid,
            actor_app=inbound.appid or agent_client_id,
            grant=inbound.grant,
        )

    if not _groups_allowed(inbound.groups, policy):
        return IdentityBoundResult(
            tool=tool,
            decision="block",
            reason=f"Caller not authorized for tool {tool}",
            subject=inbound.oid,
            actor_app=inbound.azp or agent_client_id,
            grant=inbound.grant,
        )

    want = list(requested_scopes) if requested_scopes is not None else list(policy.allowed_scopes)
    try:
        exchanged = exchange_on_behalf_of(
            inbound_token,
            resource_audience=policy.resource_audience,
            allowed_scopes=policy.allowed_scopes,
            requested_scopes=want,
            agent_client_id=agent_client_id,
            secret=secret,
        )
    except AppOnlyDenied as exc:
        return IdentityBoundResult(
            tool=tool,
            decision="block",
            reason=str(exc),
            subject=inbound.oid,
            actor_app=agent_client_id,
            grant=inbound.grant,
        )
    except DownscopeEmpty as exc:
        return IdentityBoundResult(
            tool=tool,
            decision="block",
            reason=str(exc),
            subject=inbound.oid,
            actor_app=agent_client_id,
            grant=inbound.grant,
        )
    except OboDenied as exc:
        return IdentityBoundResult(
            tool=tool,
            decision="block",
            reason=str(exc),
            subject=inbound.oid,
            actor_app=agent_client_id,
            grant=inbound.grant,
        )

    exchanged_claims = decode_lab_token(exchanged, secret=secret)
    caller = _RESOURCE_CALLERS.get(tool)
    if caller is None:
        return IdentityBoundResult(tool=tool, decision="block", reason=f"No resource for tool {tool}")

    try:
        result = caller(exchanged, arguments, secret)
    except ResourceDenied as exc:
        return IdentityBoundResult(
            tool=tool,
            decision="block",
            reason=str(exc),
            subject=exchanged_claims.oid,
            actor_app=exchanged_claims.act or agent_client_id,
            grant="obo",
            exchanged_scp=list(exchanged_claims.scp),
        )

    return IdentityBoundResult(
        tool=tool,
        decision="allow",
        reason="Tool invocation allowed with OBO user subject",
        subject=exchanged_claims.oid,
        actor_app=exchanged_claims.act or agent_client_id,
        grant="obo",
        exchanged_scp=list(exchanged_claims.scp),
        result=result,
    )
