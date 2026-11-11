"""Mock Entra-shaped tokens for the OBO competency lab.

HS256 + a lab secret. Not a real IdP. Claims follow Entra conventions closely
enough that interview talk tracks stay honest: ``oid``, ``scp`` (space-delimited),
``roles`` (app-only), ``idtyp``, ``azp`` / ``appid``, ``aud``.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import jwt

LAB_SECRET_ENV = "RAG_OBO_LAB_SECRET"
DEFAULT_LAB_SECRET = "obo-lab-secret-not-for-production-use"
LAB_ALG = "HS256"
DEFAULT_TENANT = "contoso-tid"
AGENT_CLIENT_ID = "agent-app-client-id"
GATEWAY_AUD = "api://agent-gateway"
SQL_AUD = "api://mock-sql"
MAIL_AUD = "api://mock-mail"
JIRA_AUD = "api://mock-jira"


class TokenError(ValueError):
    """Inbound or exchanged token failed validation."""


@dataclass
class LabClaims:
    oid: str
    sub: str
    aud: str
    azp: str
    appid: str
    idtyp: str  # user | app
    grant: str  # user_assertion | client_credentials | obo
    tid: str = DEFAULT_TENANT
    groups: List[str] = field(default_factory=list)
    scp: List[str] = field(default_factory=list)
    roles: List[str] = field(default_factory=list)
    act: Optional[str] = None
    sid: Optional[str] = None
    jti: Optional[str] = None
    preferred_username: Optional[str] = None

    @property
    def is_app_only(self) -> bool:
        return self.idtyp == "app" or self.grant == "client_credentials"


def lab_secret() -> str:
    return os.getenv(LAB_SECRET_ENV, DEFAULT_LAB_SECRET)


def mint_lab_token(claims: LabClaims, *, secret: Optional[str] = None) -> str:
    payload: Dict[str, Any] = {
        "oid": claims.oid,
        "sub": claims.sub,
        "aud": claims.aud,
        "azp": claims.azp,
        "appid": claims.appid,
        "idtyp": claims.idtyp,
        "grant": claims.grant,
        "tid": claims.tid,
        "groups": list(claims.groups),
        "jti": claims.jti or str(uuid.uuid4()),
    }
    if claims.scp:
        payload["scp"] = " ".join(claims.scp)
    if claims.roles:
        payload["roles"] = list(claims.roles)
    if claims.act:
        payload["act"] = {"sub": claims.act}
    if claims.sid:
        payload["sid"] = claims.sid
    if claims.preferred_username:
        payload["preferred_username"] = claims.preferred_username
    return jwt.encode(payload, secret or lab_secret(), algorithm=LAB_ALG)


def decode_lab_token(token: str, *, secret: Optional[str] = None, audience: Optional[str] = None) -> LabClaims:
    options = {"verify_aud": audience is not None}
    try:
        payload = jwt.decode(
            token,
            secret or lab_secret(),
            algorithms=[LAB_ALG],
            audience=audience,
            options=options,
        )
    except jwt.PyJWTError as exc:
        raise TokenError(f"invalid lab token: {exc}") from exc
    return claims_from_payload(payload)


def claims_from_payload(payload: Dict[str, Any]) -> LabClaims:
    scp_raw = payload.get("scp") or ""
    if isinstance(scp_raw, list):
        scp = [str(s).strip() for s in scp_raw if str(s).strip()]
    else:
        scp = [p for p in str(scp_raw).split() if p]
    act = payload.get("act")
    act_sub = None
    if isinstance(act, dict):
        act_sub = str(act.get("sub") or "") or None
    elif isinstance(act, str):
        act_sub = act or None
    groups_raw = payload.get("groups") or []
    roles_raw = payload.get("roles") or []
    return LabClaims(
        oid=str(payload.get("oid") or payload.get("sub") or ""),
        sub=str(payload.get("sub") or payload.get("oid") or ""),
        aud=str(payload.get("aud") or ""),
        azp=str(payload.get("azp") or payload.get("appid") or ""),
        appid=str(payload.get("appid") or payload.get("azp") or ""),
        idtyp=str(payload.get("idtyp") or "user"),
        grant=str(payload.get("grant") or "user_assertion"),
        tid=str(payload.get("tid") or DEFAULT_TENANT),
        groups=[str(g) for g in groups_raw] if isinstance(groups_raw, list) else [],
        scp=scp,
        roles=[str(r) for r in roles_raw] if isinstance(roles_raw, list) else [],
        act=act_sub,
        sid=str(payload["sid"]) if payload.get("sid") else None,
        jti=str(payload["jti"]) if payload.get("jti") else None,
        preferred_username=str(payload["preferred_username"]) if payload.get("preferred_username") else None,
    )


def mint_user_token(
    *,
    oid: str,
    groups: List[str],
    username: str,
    scp: Optional[List[str]] = None,
    sid: Optional[str] = None,
    secret: Optional[str] = None,
) -> str:
    return mint_lab_token(
        LabClaims(
            oid=oid,
            sub=oid,
            aud=GATEWAY_AUD,
            azp=AGENT_CLIENT_ID,
            appid=AGENT_CLIENT_ID,
            idtyp="user",
            grant="user_assertion",
            groups=list(groups),
            scp=list(scp or ["User.Read", "Agent.Invoke"]),
            sid=sid or f"sid-{oid}",
            preferred_username=username,
        ),
        secret=secret,
    )


def mint_app_only_token(
    *,
    sp_oid: str = "agent-sp-oid",
    roles: Optional[List[str]] = None,
    aud: str = "https://graph.microsoft.com",
    secret: Optional[str] = None,
) -> str:
    return mint_lab_token(
        LabClaims(
            oid=sp_oid,
            sub=sp_oid,
            aud=aud,
            azp=AGENT_CLIENT_ID,
            appid=AGENT_CLIENT_ID,
            idtyp="app",
            grant="client_credentials",
            roles=list(roles or ["Files.ReadWrite.All", "Mail.Send"]),
        ),
        secret=secret,
    )
