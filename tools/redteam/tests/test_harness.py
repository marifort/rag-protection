"""Scenario loader and assertion unit tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from redteam.assertions import evaluate_query_expect, evaluate_scenario
from redteam.client import RedTeamClient
from redteam.models import AttackSpec, ExpectSpec, Scenario
from redteam.scenario import ScenarioLoadError, load_scenario

SCENARIOS = Path(__file__).resolve().parents[1] / "scenarios"


@pytest.mark.parametrize(
    "name",
    [
        "indirect_injection_ticket",
        "corpus_poison_hr_policy",
        "acl_bypass_attempt",
        "dlp_exfil_ssn_query",
        "dlp_exfil_pii_query",
        "dlp_exfil_employees_query",
        "ungrounded_answer",
    ],
)
def test_bundled_scenarios_load(name: str) -> None:
    scenario = load_scenario(SCENARIOS / f"{name}.yaml")
    assert scenario.id == name
    assert scenario.expect is not None


def test_loader_rejects_non_mapping(tmp_path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("- not a mapping\n", encoding="utf-8")
    with pytest.raises(ScenarioLoadError):
        load_scenario(bad)


def test_empty_retrieval_passes_without_hr_payroll() -> None:
    expect = ExpectSpec(decision="empty_retrieval")
    ok, msgs = evaluate_query_expect(
        expect,
        {"blocked": False, "chunks": [{"document_id": "public-faq"}], "answer": "hours"},
    )
    assert ok
    assert not msgs


def test_empty_retrieval_fails_when_payroll_leaks() -> None:
    expect = ExpectSpec(decision="empty_retrieval")
    ok, msgs = evaluate_query_expect(
        expect,
        {"blocked": False, "chunks": [{"document_id": "hr-payroll"}], "answer": "4.2M"},
    )
    assert not ok
    assert msgs


def test_block_expectation_requires_blocked() -> None:
    scenario = Scenario(
        id="x",
        title="x",
        attack=AttackSpec(token="t", query="q"),
        expect=ExpectSpec(decision="block", control="injection"),
    )
    result = evaluate_scenario(
        scenario,
        ingest_results=[],
        query_result={"blocked": False, "answer": "", "chunks": [], "audit": []},
    )
    assert not result.passed


def test_corpus_poison_passes_when_ingest_rejects() -> None:
    """Poison stopped at ingest: query need not block, only stay clean."""
    scenario = Scenario(
        id="corpus_poison_hr_policy",
        title="corpus poison",
        attack=AttackSpec(token="t", query="Summarize HR policy"),
        expect=ExpectSpec(
            decision="block",
            control="injection",
            not_in_answer=["evil.example", "attacker@"],
        ),
    )
    result = evaluate_scenario(
        scenario,
        ingest_results=[
            {
                "status": "rejected",
                "reason": "blocked: html_comment_injection",
                "findings": [
                    {
                        "scanner": "prompt_injection",
                        "category": "html_comment_injection",
                        "severity": 0.75,
                    }
                ],
            }
        ],
        query_result={
            "blocked": False,
            "answer": "PTO is 20 days per year.",
            "chunks": [],
            "audit": [],
        },
    )
    assert result.passed, result.messages


def test_citation_fail_accepts_hard_gate_block_reason() -> None:
    expect = ExpectSpec(decision="citation_fail", control="citation")
    ok, msgs = evaluate_query_expect(
        expect,
        {
            "blocked": True,
            "block_reason": "citation_hard_gate_failed",
            "answer": "I cannot provide that answer",
            "chunks": [],
            "audit": [],
            "citations": {"passed": False, "hard_gate_failed": True},
        },
    )
    assert ok, msgs


def test_not_in_answer_enforced() -> None:
    expect = ExpectSpec(decision="block", not_in_answer=["evil.example"])
    ok, msgs = evaluate_query_expect(
        expect,
        {"blocked": True, "answer": "visit evil.example now", "chunks": [], "audit": []},
    )
    assert not ok
    assert "evil.example" in msgs[0]


def test_health_does_not_require_token() -> None:
    """GET /health is public; connectivity checks must not demand a user bearer."""
    client = RedTeamClient("http://localhost:8090")
    fake = MagicMock()
    fake.status_code = 200
    fake.headers = {"content-type": "application/json"}
    fake.json.return_value = {"status": "healthy"}
    with patch("redteam.client.httpx.Client") as mock_cls:
        mock_cls.return_value.__enter__.return_value.request.return_value = fake
        payload = client.health()
    assert payload["status"] == "healthy"
    call_kwargs = mock_cls.return_value.__enter__.return_value.request.call_args
    assert "Authorization" not in call_kwargs.kwargs["headers"]
