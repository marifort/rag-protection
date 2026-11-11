"""Stretch exercises for lab11. Skipped unless RAG_OBO_EXERCISES=1.

    RAG_OBO_EXERCISES=1 pytest tests/test_obo_exercises.py -q
"""

from __future__ import annotations

import os

import pytest

from rag_protection_proxy.tools_gateway.obo.exchange import exchange_on_behalf_of
from rag_protection_proxy.tools_gateway.obo.exercises import (
    ExerciseNotImplemented,
    JtiReplayStore,
    authorize_email_recipient,
    bind_session,
)
from rag_protection_proxy.tools_gateway.obo.tokens import (
    SQL_AUD,
    decode_lab_token,
    mint_user_token,
)

pytestmark = pytest.mark.exercise

SECRET = "test-obo-secret-not-for-prod-use"

skip_until_opt_in = pytest.mark.skipif(
    os.getenv("RAG_OBO_EXERCISES") != "1",
    reason="Implement exercises.py, then: RAG_OBO_EXERCISES=1 pytest tests/test_obo_exercises.py",
)


def _user(oid: str, groups: list[str], sid: str):
    return mint_user_token(
        oid=oid,
        groups=groups,
        username=f"{oid}@contoso.com",
        sid=sid,
        secret=SECRET,
    )


@skip_until_opt_in
def test_bind_session_accepts_matching_sid():
    token = _user("alice-oid", ["engineering"], "sid-alice-session")
    exchanged = exchange_on_behalf_of(
        token,
        resource_audience=SQL_AUD,
        allowed_scopes=["SQL.Read"],
        requested_scopes=["SQL.Read"],
        secret=SECRET,
    )
    bind_session(decode_lab_token(token, secret=SECRET), decode_lab_token(exchanged, secret=SECRET))


@skip_until_opt_in
def test_bind_session_rejects_foreign_sid():
    token = _user("alice-oid", ["engineering"], "sid-alice-session")
    other = _user("bob-oid", ["engineering"], "sid-bob-session")
    exchanged_other = exchange_on_behalf_of(
        other,
        resource_audience=SQL_AUD,
        allowed_scopes=["SQL.Read"],
        requested_scopes=["SQL.Read"],
        secret=SECRET,
    )
    with pytest.raises(ValueError):
        bind_session(
            decode_lab_token(token, secret=SECRET),
            decode_lab_token(exchanged_other, secret=SECRET),
        )


@skip_until_opt_in
def test_email_recipient_engineering_company_ok_gmail_denied():
    authorize_email_recipient(["engineering", "all-staff"], "carol.hr@company.com")
    with pytest.raises(ValueError):
        authorize_email_recipient(["engineering"], "alice@gmail.com")


@skip_until_opt_in
def test_email_recipient_hr_benefits_domain():
    authorize_email_recipient(["hr"], "help@contoso-benefits.example")
    with pytest.raises(ValueError):
        authorize_email_recipient(["engineering"], "help@contoso-benefits.example")


@skip_until_opt_in
def test_jti_replay_rejected():
    store = JtiReplayStore()
    store.remember_or_reject("jti-1")
    with pytest.raises(ValueError, match="replay"):
        store.remember_or_reject("jti-1")
    with pytest.raises(ValueError):
        store.remember_or_reject("")
    with pytest.raises(ValueError):
        store.remember_or_reject(None)


@skip_until_opt_in
def test_exercises_are_no_longer_stubs():
    """Fails if you opted in without implementing (NotImplemented still raised)."""
    try:
        authorize_email_recipient(["engineering"], "a@company.com")
    except ExerciseNotImplemented:
        pytest.fail("exercises.py still raises ExerciseNotImplemented — fill in the three functions")
