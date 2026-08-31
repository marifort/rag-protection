"""Golden tests for rag-scan checks against bad/good fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from rag_scan.checks import run_all
from rag_scan.cli import main
from rag_scan.context import ConfigLoadError, build_context
from rag_scan.models import Severity

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _rule_ids(findings) -> set[str]:
    return {f.rule_id for f in findings}


def test_bad_config_fires_expected_rules():
    ctx = build_context(
        env="prod",
        policy_path=str(FIXTURES / "bad_policy.yaml"),
        acl_path=str(FIXTURES / "bad_acl.yaml"),
        sample_docs_path=str(FIXTURES / "bad_sample_documents.json"),
    )
    fired = _rule_ids(run_all(ctx))
    # Critical rules that must trigger on the deliberately bad fixtures.
    for rule_id in ("ACL001", "ACL002", "POL002", "SEC001"):
        assert rule_id in fired, f"expected {rule_id} to fire; got {sorted(fired)}"
    # Warnings on the same fixtures.
    for rule_id in ("ACL003", "POL001", "POL003"):
        assert rule_id in fired


def test_good_config_is_clean():
    ctx = build_context(
        env="prod",
        policy_path=str(FIXTURES / "good_policy.yaml"),
        acl_path=str(FIXTURES / "good_acl.yaml"),
        sample_docs_path=None,
    )
    findings = run_all(ctx)
    criticals = [f for f in findings if f.severity is Severity.CRITICAL]
    assert criticals == [], f"expected no criticals; got {[f.rule_id for f in criticals]}"


def test_demo_tokens_only_flagged_in_prod():
    common = dict(
        policy_path=str(FIXTURES / "good_policy.yaml"),
        acl_path=str(FIXTURES / "bad_acl.yaml"),
    )
    dev = _rule_ids(run_all(build_context(env="dev", **common)))
    prod = _rule_ids(run_all(build_context(env="prod", **common)))
    assert "ACL001" not in dev
    assert "ACL001" in prod


def test_pol003_fires_only_when_injection_coverage_reduced():
    # good_policy.yaml leaves injection defaults intact -> POL003 must stay silent.
    clean = build_context(policy_path=str(FIXTURES / "good_policy.yaml"))
    assert "POL003" not in _rule_ids(run_all(clean))
    # bad_policy.yaml disables the ML classifier + two categories -> POL003 fires.
    reduced = build_context(policy_path=str(FIXTURES / "bad_policy.yaml"))
    assert "POL003" in _rule_ids(run_all(reduced))


def test_invalid_policy_raises_config_load_error():
    with pytest.raises(ConfigLoadError):
        build_context(policy_path=str(FIXTURES / "invalid_policy.yaml"))


def test_cli_check_exit_code_on_bad_config():
    code = main(
        [
            "check",
            "--env",
            "prod",
            "--policy",
            str(FIXTURES / "bad_policy.yaml"),
            "--acl",
            str(FIXTURES / "bad_acl.yaml"),
            "--sample-docs",
            str(FIXTURES / "bad_sample_documents.json"),
        ]
    )
    assert code == 1


def test_cli_check_exit_zero_on_good_config():
    code = main(
        [
            "check",
            "--env",
            "prod",
            "--policy",
            str(FIXTURES / "good_policy.yaml"),
            "--acl",
            str(FIXTURES / "good_acl.yaml"),
        ]
    )
    assert code == 0


def test_cli_validate_exit_two_on_invalid():
    code = main(["validate", "--policy", str(FIXTURES / "invalid_policy.yaml")])
    assert code == 2


def test_baseline_round_trip_suppresses_findings(tmp_path):
    bad = [
        "check", "--env", "prod",
        "--policy", str(FIXTURES / "bad_policy.yaml"),
        "--acl", str(FIXTURES / "bad_acl.yaml"),
        "--sample-docs", str(FIXTURES / "bad_sample_documents.json"),
    ]
    # Without a baseline the bad config fails the gate.
    assert main(bad) == 1

    # Snapshot the current findings, then re-run gating against that baseline.
    baseline_file = tmp_path / "rag-scan-baseline.json"
    assert main(bad + ["--write-baseline", str(baseline_file)]) == 0
    assert baseline_file.exists()
    assert main(bad + ["--baseline", str(baseline_file)]) == 0


def test_baseline_does_not_suppress_new_findings(tmp_path):
    from rag_scan import baseline as baseline_mod
    from rag_scan.models import Finding, ScanReport, Severity

    known = Finding("ACL003", Severity.WARNING, "t", "known message", "acl.yaml")
    new = Finding("ACL003", Severity.WARNING, "t", "different message", "acl.yaml")
    report = ScanReport(findings=[known, new])
    baseline_mod.apply(report, {known.fingerprint})
    assert [f.message for f in report.findings] == ["different message"]
    assert report.suppressed == 1


def test_baseline_missing_file_exits_two():
    code = main(
        [
            "check", "--env", "prod",
            "--policy", str(FIXTURES / "good_policy.yaml"),
            "--acl", str(FIXTURES / "good_acl.yaml"),
            "--baseline", "/nonexistent/baseline.json",
        ]
    )
    assert code == 2


def test_junit_and_sarif_render():
    from rag_scan.reporters import render

    ctx = build_context(
        env="prod",
        policy_path=str(FIXTURES / "bad_policy.yaml"),
        acl_path=str(FIXTURES / "bad_acl.yaml"),
    )
    from rag_scan.models import ScanReport

    report = ScanReport()
    report.extend(run_all(ctx))
    junit = render(report, "junit")
    assert "<testsuite" in junit and 'failures="' in junit
    sarif = render(report, "sarif")
    assert '"version": "2.1.0"' in sarif
