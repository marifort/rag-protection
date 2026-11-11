"""On-behalf-of exchange (mock of Entra OBO / RFC 8693 token exchange).

Skill: the agent is a confidential client. It must swap the **user** assertion
for a downscoped token whose ``aud`` is the *resource*, not Graph-as-app.
Client-credentials (app-only) tokens are a Zero Trust fail — there is no user.
"""

from __future__ import annotations

from typing import Iterable, List, Optional, Sequence

from rag_protection_proxy.tools_gateway.obo.tokens import (
    AGENT_CLIENT_ID,
    LabClaims,
    decode_lab_token,
    mint_lab_token,
)


class OboDenied(ValueError):
    """OBO exchange refused."""


class AppOnlyDenied(OboDenied):
    """Agent presented a service-account / client-credentials token."""


class DownscopeEmpty(OboDenied):
    """Requested scopes ∩ policy scopes is empty — tool would run with no rights, or over-ask."""


def downscope(requested: Sequence[str], allowed: Sequence[str]) -> List[str]:
    """Least privilege on the exchanged token: intersection, preserve allowed order."""
    want = {s.strip() for s in requested if s and str(s).strip()}
    return [s for s in allowed if s in want]


def exchange_on_behalf_of(
    user_token: str,
    *,
    resource_audience: str,
    allowed_scopes: Iterable[str],
    requested_scopes: Iterable[str],
    agent_client_id: str = AGENT_CLIENT_ID,
    secret: Optional[str] = None,
) -> str:
    """Mint an exchanged token the **resource** will accept.

    Rules:
    - User assertion only (``idtyp=user``). App-only is denied.
    - Do not re-exchange an already-OBO token (no chaining).
    - ``azp`` must be this agent (confused-deputy at the *gateway*).
    - ``scp`` on the result is requested ∩ allowed (downscope).
    - ``aud`` on the result is the resource, not the gateway.
    - ``act.sub`` records the agent so audit can name both identities.
    """
    inbound = decode_lab_token(user_token, secret=secret)
    if inbound.is_app_only:
        raise AppOnlyDenied(
            "client_credentials / app-only token: downstream would run as the bot service principal"
        )
    if inbound.grant == "obo":
        raise OboDenied("refusing to re-exchange an already-OBO token")
    if inbound.azp and inbound.azp != agent_client_id:
        raise OboDenied(f"token azp {inbound.azp!r} is not this agent {agent_client_id!r}")
    if inbound.idtyp != "user" or not inbound.oid:
        raise OboDenied("OBO requires a user subject (oid)")

    scoped = downscope(list(requested_scopes), list(allowed_scopes))
    if not scoped:
        raise DownscopeEmpty(
            "downscope empty: agent requested scopes the tool policy does not allow"
        )

    exchanged = LabClaims(
        oid=inbound.oid,
        sub=inbound.oid,
        aud=resource_audience,
        azp=agent_client_id,
        appid=agent_client_id,
        idtyp="user",
        grant="obo",
        tid=inbound.tid,
        groups=list(inbound.groups),
        scp=scoped,
        act=agent_client_id,
        sid=inbound.sid,
        preferred_username=inbound.preferred_username,
    )
    return mint_lab_token(exchanged, secret=secret)
