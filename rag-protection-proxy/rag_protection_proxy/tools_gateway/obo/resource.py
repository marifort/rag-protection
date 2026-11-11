"""Downstream resource servers that refuse to trust a bot service account.

Skill: even a correct gateway allowlist is useless if Jira/SQL accepts
client-credentials. The resource must enforce:
- ``idtyp=user`` and ``grant=obo``
- ``aud`` equals *this* API (confused deputy)
- required ``scp``
- row/arg checks as the user, not as the app
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from rag_protection_proxy.tools_gateway.obo.tokens import (
    JIRA_AUD,
    MAIL_AUD,
    SQL_AUD,
    LabClaims,
    TokenError,
    decode_lab_token,
)

PAYROLL_ROWS: List[Dict[str, str]] = [
    {"employee_id": "E1001", "department": "Engineering", "salary_band": "IC4", "name": "Alice"},
    {"employee_id": "E1002", "department": "HR", "salary_band": "M1", "name": "Carol"},
    {"employee_id": "E1003", "department": "Finance", "salary_band": "M2", "name": "Dana"},
]


class ResourceDenied(ValueError):
    """Resource server rejected the presented token or arguments."""


def _require_obo(token: str, *, audience: str, scope: str, secret: Optional[str] = None) -> LabClaims:
    try:
        # Validate signature first; check idtyp / grant / aud in IAM order so the
        # error string names the Zero Trust failure (service account vs confused deputy).
        claims = decode_lab_token(token, secret=secret, audience=None)
    except TokenError as exc:
        raise ResourceDenied(str(exc)) from exc
    if claims.is_app_only:
        raise ResourceDenied("resource refuses app-only / client_credentials tokens")
    if claims.grant != "obo":
        raise ResourceDenied("resource requires an OBO-exchanged token, not the gateway user assertion")
    if claims.aud != audience:
        raise ResourceDenied(f"audience mismatch: token aud={claims.aud!r} resource={audience!r}")
    if scope not in claims.scp:
        raise ResourceDenied(f"missing scope {scope!r} on exchanged token")
    if not claims.oid:
        raise ResourceDenied("exchanged token has no user oid")
    return claims


def _rows_for_groups(groups: List[str]) -> List[Dict[str, str]]:
    """Row-level: engineering sees Engineering; HR / data-platform see all."""
    lowered = {g.lower() for g in groups}
    if "hr" in lowered or "data-platform" in lowered:
        return list(PAYROLL_ROWS)
    if "engineering" in lowered:
        return [r for r in PAYROLL_ROWS if r["department"] == "Engineering"]
    return []


def call_mock_sql(
    exchanged_token: str,
    *,
    query: str,
    secret: Optional[str] = None,
) -> Dict[str, Any]:
    claims = _require_obo(exchanged_token, audience=SQL_AUD, scope="SQL.Read", secret=secret)
    q = (query or "").strip().upper()
    if "DROP" in q or "DELETE" in q or "UPDATE" in q:
        raise ResourceDenied("SQL mutation verbs are not in SQL.Read")
    rows = _rows_for_groups(claims.groups)
    return {
        "status": "ok",
        "query": query,
        "acted_as_oid": claims.oid,
        "acted_as_username": claims.preferred_username,
        "actor_app": claims.act or claims.azp,
        "row_count": len(rows),
        "rows": rows,
    }


def call_mock_mail(
    exchanged_token: str,
    *,
    to: str,
    subject: str = "",
    secret: Optional[str] = None,
) -> Dict[str, Any]:
    claims = _require_obo(exchanged_token, audience=MAIL_AUD, scope="Mail.Send", secret=secret)
    return {
        "status": "sent",
        "to": to,
        "subject": subject,
        "acted_as_oid": claims.oid,
        "acted_as_username": claims.preferred_username,
        "actor_app": claims.act or claims.azp,
    }


def call_mock_jira(
    exchanged_token: str,
    *,
    issue_key: str,
    secret: Optional[str] = None,
) -> Dict[str, Any]:
    claims = _require_obo(exchanged_token, audience=JIRA_AUD, scope="Jira.Read", secret=secret)
    return {
        "status": "ok",
        "issue_key": issue_key,
        "acted_as_oid": claims.oid,
        "actor_app": claims.act or claims.azp,
        "summary": f"[mock] {issue_key} visible to {claims.preferred_username or claims.oid}",
    }
