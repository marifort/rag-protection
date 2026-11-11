"""OBO identity lab — working path (always runs in CE pytest)."""

from __future__ import annotations

import json

import pytest

from rag_protection_proxy.tools_gateway.obo.exchange import (
    AppOnlyDenied,
    DownscopeEmpty,
    OboDenied,
    downscope,
    exchange_on_behalf_of,
)
from rag_protection_proxy.tools_gateway.obo.matrix import default_fixture_dir, scan_access_matrix, scan_files
from rag_protection_proxy.tools_gateway.obo.pipeline import invoke_identity_bound
from rag_protection_proxy.tools_gateway.obo.resource import ResourceDenied, call_mock_sql
from rag_protection_proxy.tools_gateway.obo.tokens import (
    AGENT_CLIENT_ID,
    MAIL_AUD,
    SQL_AUD,
    TokenError,
    decode_lab_token,
    mint_app_only_token,
    mint_lab_token,
    mint_user_token,
    LabClaims,
)

SECRET = "test-obo-secret-not-for-prod-use"


def _alice(**kwargs):
    return mint_user_token(
        oid="alice-oid",
        groups=kwargs.pop("groups", ["engineering", "all-staff"]),
        username="alice.engineer@contoso.com",
        secret=SECRET,
        **kwargs,
    )


def _frank():
    return mint_user_token(
        oid="frank-oid",
        groups=["data-platform", "all-staff"],
        username="frank.dba@contoso.com",
        secret=SECRET,
    )


def _carol():
    return mint_user_token(
        oid="carol-oid",
        groups=["hr", "all-staff"],
        username="carol.hr@contoso.com",
        secret=SECRET,
    )


def test_app_only_exchange_denied():
    bot = mint_app_only_token(secret=SECRET)
    with pytest.raises(AppOnlyDenied):
        exchange_on_behalf_of(
            bot,
            resource_audience=SQL_AUD,
            allowed_scopes=["SQL.Read"],
            requested_scopes=["SQL.Read"],
            secret=SECRET,
        )


def test_downscope_intersection():
    assert downscope(["Files.ReadWrite.All", "SQL.Read"], ["SQL.Read"]) == ["SQL.Read"]
    assert downscope(["Files.ReadWrite.All"], ["SQL.Read"]) == []


def test_exchange_sets_user_oid_actor_and_resource_aud():
    token = exchange_on_behalf_of(
        _frank(),
        resource_audience=SQL_AUD,
        allowed_scopes=["SQL.Read"],
        requested_scopes=["SQL.Read", "Files.ReadWrite.All"],
        secret=SECRET,
    )
    claims = decode_lab_token(token, secret=SECRET, audience=SQL_AUD)
    assert claims.oid == "frank-oid"
    assert claims.grant == "obo"
    assert claims.aud == SQL_AUD
    assert claims.scp == ["SQL.Read"]
    assert claims.act == AGENT_CLIENT_ID
    assert claims.idtyp == "user"


def test_refuse_reexchange():
    first = exchange_on_behalf_of(
        _frank(),
        resource_audience=SQL_AUD,
        allowed_scopes=["SQL.Read"],
        requested_scopes=["SQL.Read"],
        secret=SECRET,
    )
    with pytest.raises(OboDenied, match="re-exchange"):
        exchange_on_behalf_of(
            first,
            resource_audience=SQL_AUD,
            allowed_scopes=["SQL.Read"],
            requested_scopes=["SQL.Read"],
            secret=SECRET,
        )


def test_wrong_azp_denied():
    foreign = mint_lab_token(
        LabClaims(
            oid="alice-oid",
            sub="alice-oid",
            aud="api://agent-gateway",
            azp="other-agent",
            appid="other-agent",
            idtyp="user",
            grant="user_assertion",
            groups=["data-platform"],
        ),
        secret=SECRET,
    )
    with pytest.raises(OboDenied, match="azp"):
        exchange_on_behalf_of(
            foreign,
            resource_audience=SQL_AUD,
            allowed_scopes=["SQL.Read"],
            requested_scopes=["SQL.Read"],
            secret=SECRET,
        )


def test_over_ask_downscope_empty():
    with pytest.raises(DownscopeEmpty):
        exchange_on_behalf_of(
            _frank(),
            resource_audience=SQL_AUD,
            allowed_scopes=["SQL.Read"],
            requested_scopes=["Files.ReadWrite.All"],
            secret=SECRET,
        )


def test_sql_resource_refuses_app_only_and_wrong_audience():
    bot = mint_app_only_token(secret=SECRET)
    with pytest.raises(ResourceDenied, match="app-only"):
        call_mock_sql(bot, query="SELECT 1", secret=SECRET)

    mail_token = exchange_on_behalf_of(
        _carol(),
        resource_audience=MAIL_AUD,
        allowed_scopes=["Mail.Send"],
        requested_scopes=["Mail.Send"],
        secret=SECRET,
    )
    with pytest.raises(ResourceDenied, match="audience"):
        call_mock_sql(mail_token, query="SELECT 1", secret=SECRET)


def test_sql_row_filter_engineering_vs_hr():
    alice_ex = exchange_on_behalf_of(
        _alice(),
        resource_audience=SQL_AUD,
        allowed_scopes=["SQL.Read"],
        requested_scopes=["SQL.Read"],
        secret=SECRET,
    )
    alice_rows = call_mock_sql(alice_ex, query="SELECT * FROM payroll", secret=SECRET)
    assert alice_rows["acted_as_oid"] == "alice-oid"
    assert {r["department"] for r in alice_rows["rows"]} == {"Engineering"}

    carol_ex = exchange_on_behalf_of(
        _carol(),
        resource_audience=SQL_AUD,
        allowed_scopes=["SQL.Read"],
        requested_scopes=["SQL.Read"],
        secret=SECRET,
    )
    carol_rows = call_mock_sql(carol_ex, query="SELECT * FROM payroll", secret=SECRET)
    assert carol_rows["row_count"] == 3


def test_sql_blocks_mutations():
    token = exchange_on_behalf_of(
        _frank(),
        resource_audience=SQL_AUD,
        allowed_scopes=["SQL.Read"],
        requested_scopes=["SQL.Read"],
        secret=SECRET,
    )
    with pytest.raises(ResourceDenied, match="mutation"):
        call_mock_sql(token, query="DROP TABLE payroll", secret=SECRET)


def test_pipeline_alice_blocked_frank_allowed_bot_blocked():
    alice = invoke_identity_bound(
        inbound_token=_alice(),
        tool="run_sql",
        arguments={"query": "SELECT 1"},
        secret=SECRET,
    )
    assert alice.blocked
    assert "not authorized" in alice.reason

    frank = invoke_identity_bound(
        inbound_token=_frank(),
        tool="run_sql",
        arguments={"query": "SELECT employee_id FROM payroll"},
        secret=SECRET,
    )
    assert frank.decision == "allow"
    assert frank.subject == "frank-oid"
    assert frank.actor_app == AGENT_CLIENT_ID
    assert frank.grant == "obo"
    assert frank.result["acted_as_oid"] == "frank-oid"
    assert frank.audit()["kind"] == "tool_invoke_obo"

    bot = invoke_identity_bound(
        inbound_token=mint_app_only_token(secret=SECRET),
        tool="run_sql",
        arguments={"query": "SELECT 1"},
        secret=SECRET,
    )
    assert bot.blocked
    assert "app-only" in bot.reason


def test_pipeline_mail_as_alice():
    result = invoke_identity_bound(
        inbound_token=_alice(),
        tool="send_email",
        arguments={"to": "carol.hr@company.com", "subject": "hi"},
        secret=SECRET,
    )
    assert result.decision == "allow"
    assert result.result["acted_as_oid"] == "alice-oid"


def test_confused_deputy_mail_token_cannot_call_sql_via_pipeline_over_ask():
    """Exchanged Mail.Send token is useless against SQL even if you skip the pipeline."""
    mail = exchange_on_behalf_of(
        _alice(),
        resource_audience=MAIL_AUD,
        allowed_scopes=["Mail.Send"],
        requested_scopes=["Mail.Send"],
        secret=SECRET,
    )
    with pytest.raises(ResourceDenied):
        call_mock_sql(mail, query="SELECT salary FROM payroll", secret=SECRET)


def test_invalid_token_blocked():
    result = invoke_identity_bound(
        inbound_token="not-a-jwt",
        tool="run_sql",
        arguments={"query": "SELECT 1"},
        secret=SECRET,
    )
    assert result.blocked
    assert "invalid inbound" in result.reason


def test_unknown_tool():
    result = invoke_identity_bound(
        inbound_token=_frank(),
        tool="launch_nukes",
        arguments={},
        secret=SECRET,
    )
    assert result.blocked
    assert "Unknown tool" in result.reason


def test_matrix_flags_app_roles_and_unused_scopes():
    entra = json.loads((default_fixture_dir() / "entra_grants.json").read_text(encoding="utf-8"))
    tools = json.loads((default_fixture_dir() / "mcp_tools.json").read_text(encoding="utf-8"))
    findings = scan_access_matrix(entra, tools)
    codes = {f.code for f in findings}
    assert "MATRIX001" in codes
    assert "MATRIX002" in codes
    assert "MATRIX003" in codes
    assert "MATRIX005" in codes
    assert "MATRIX006" in codes
    copilot = [f for f in findings if f.entity == "Internal Copilot Agent"]
    assert any(f.severity == "high" for f in copilot)


def test_matrix_clean_sp_has_no_high_findings_on_itself():
    findings = scan_files(
        default_fixture_dir() / "entra_grants.json",
        default_fixture_dir() / "mcp_tools.json",
    )
    helper_high = [
        f for f in findings if f.entity == "Least-privilege RAG helper" and f.severity == "high"
    ]
    assert helper_high == []


def test_decode_rejects_wrong_secret():
    token = _alice()
    with pytest.raises(TokenError):
        decode_lab_token(token, secret="other-secret-not-for-productionx")


def test_cli_demo_and_matrix(capsys):
    from rag_protection_proxy.tools_gateway.obo.__main__ import main

    assert main(["demo"]) == 0
    out = capsys.readouterr().out
    assert "Alice" in out
    assert "BLOCK" in out or "block" in out.lower() or "not authorized" in out.lower()

    rc = main(["matrix"])
    assert rc == 1
    matrix_out = capsys.readouterr().out
    assert "MATRIX001" in matrix_out
