"""Optional checks beside the on-behalf-of demo.

Tests stay skipped until opted in:

    RAG_OBO_EXERCISES=1 pytest tests/test_obo_exercises.py -q

The demo command does not call these functions. Each function's docstring is the rule.
"""

from __future__ import annotations

from typing import Iterable, Optional, Set

from rag_protection_proxy.tools_gateway.obo.tokens import LabClaims


class ExerciseNotImplemented(NotImplementedError):
    """Raised when an optional exercise has no implementation."""


def bind_session(user_claims: LabClaims, exchanged_claims: LabClaims) -> None:
    """Exercise 1 — session binding.

    Deny if ``sid`` on the exchanged token does not match the user assertion.
    A stolen OBO token from another login must not ride this agent session.
    Raise ``ValueError`` with a clear reason. Return None when the bind holds.
    """
    if not user_claims.sid or not exchanged_claims.sid or user_claims.sid != exchanged_claims.sid:
        raise ValueError("sid mismatch: exchanged token is not bound to this session")
    #raise ExerciseNotImplemented("Exercise 1: bind_session")


def authorize_email_recipient(user_groups: Iterable[str], to_address: str) -> None:
    """Exercise 2 — argument ABAC as the user.

    Engineering may only send to ``@company.com``. HR may also send to
    ``@contoso-benefits.example``. Marketing may send to ``@contoso-marketing.example``. Personal domains (gmail, etc.) always deny.
    Raise ``ValueError`` when the recipient is not allowed for these groups.
    """
    if "@" not in to_address:
        raise ValueError("recipient address is missing @")
    domain = to_address.rsplit("@", 1)[-1].lower()
    if domain in {"gmail.com", "yahoo.com", "outlook.com"}:
        raise ValueError(f"personal domain denied: {domain}")
    groups = {group.lower() for group in user_groups}
    allowed = {"company.com", "contoso-marketing.example"} if "marketing" in groups else {"company.com", "contoso-benefits.example"} if "hr" in groups else {"company.com"}
    if domain not in allowed:
        raise ValueError(f"recipient domain not allowed for these groups: {domain}")
    #raise ExerciseNotImplemented("Exercise 2: authorize_email_recipient")   


class JtiReplayStore:
    """Tiny in-memory replay cache. Implement ``remember_or_reject``."""

    def __init__(self) -> None:
        self._seen: Set[str] = set()

    def remember_or_reject(self, jti: Optional[str]) -> None:
        """Exercise 3 — reject replayed exchanged tokens.

        Missing/empty jti → ValueError.
        First time a jti is seen → store it.
        Second time → ValueError('replayed jti').
        """
        if not jti:
            raise ValueError("missing jti")
        if jti in self._seen:
            raise ValueError("replayed jti")
        self._seen.add(jti)
        #raise ExerciseNotImplemented("Exercise 3: JtiReplayStore.remember_or_reject")
