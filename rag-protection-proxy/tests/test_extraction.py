"""Lab 9 — corpus-extraction (scraping) monitor.

Unit coverage for the sliding-window scorer + registry, plus an end-to-end check
that a scripted scrape trips ``extraction_suspected`` while a normal session does not.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from rag_protection_proxy.app import app
from rag_protection_proxy.config import ExtractionPolicy
from rag_protection_proxy.guardrails import extraction as ext

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
ADMIN_KEY = "test-admin-key"


def _rules(**over):
    base = dict(
        enabled=True,
        window_seconds=3600,
        min_window_queries=5,
        min_corpus_size=5,
        elevated_coverage=0.25,
        severe_coverage=0.50,
        breadth_ratio_threshold=0.8,
        novelty_ratio_threshold=0.9,
        action="alert",
    )
    base.update(over)
    return ExtractionPolicy(**base)


@pytest.fixture(autouse=True)
def _reset_monitor():
    ext.reset_for_tests()
    yield
    ext.reset_for_tests()


def test_normal_session_is_none():
    rules = _rules()
    score = None
    for i in range(3):
        score = ext.observe_query(
            subject="alice",
            tenant_id="default",
            document_ids=[f"doc-{i}"],
            query=f"question {i}",
            corpus_size=100,
            rules=rules,
        )
    assert score.severity == "none"


def test_high_coverage_is_severe():
    # Coverage only applies after min_window_queries (same floor as breadth/novelty).
    rules = _rules(min_window_queries=5, min_corpus_size=5, severe_coverage=0.50)
    score = None
    for i in range(6):
        score = ext.observe_query(
            subject="scraper",
            tenant_id="default",
            document_ids=[f"doc-{i}"],
            query=f"q {i}",
            corpus_size=10,  # 6/10 = 0.6 >= severe_coverage after full window
            rules=rules,
        )
    assert score.corpus_coverage >= 0.5
    assert score.severity == "severe"
    assert "coverage" in score.triggered_by
    assert score.trigger_summary
    assert "coverage" in score.trigger_summary


def test_coverage_ignores_short_sessions():
    """One query over a tiny corpus must not trip severe (demo / Query Lab false positive)."""
    rules = _rules(
        min_window_queries=5,
        min_corpus_size=5,
        elevated_coverage=0.2,
        severe_coverage=0.4,
        action="challenge",
    )
    score = ext.observe_query(
        subject="carol.exec",
        tenant_id="default",
        document_ids=["doc-a", "doc-b", "doc-c", "doc-d"],  # 4/5 = 0.8 if coverage applied early
        query="What is the Q1 payroll total?",
        corpus_size=5,
        rules=rules,
    )
    assert score.window_queries == 1
    assert score.severity == "none"


def test_breadth_drives_severe_after_full_window():
    rules = _rules(min_window_queries=5, min_corpus_size=100000)  # coverage disabled
    score = None
    for i in range(5):
        score = ext.observe_query(
            subject="walker",
            tenant_id="default",
            document_ids=[f"doc-{i}-a", f"doc-{i}-b"],
            query=f"broad {i}",
            corpus_size=100000,
            rules=rules,
        )
    assert score.breadth_ratio >= rules.breadth_ratio_threshold
    assert score.severity == "severe"
    assert score.triggered_by == ("breadth",)
    assert "breadth_ratio" in score.trigger_summary


def test_novelty_drives_elevated_after_full_window():
    rules = _rules(
        min_window_queries=5,
        min_corpus_size=100000,  # coverage disabled
        breadth_ratio_threshold=2.0,  # disable breadth severe
        novelty_ratio_threshold=0.8,
    )
    score = None
    for i in range(5):
        score = ext.observe_query(
            subject="explorer",
            tenant_id="default",
            document_ids=[f"doc-{i}"],
            query=f"novel {i}",
            corpus_size=100000,
            rules=rules,
        )
    assert score.severity == "elevated"
    assert score.triggered_by == ("novelty",)
    assert "novelty_ratio" in score.trigger_summary


def test_small_corpus_disables_coverage():
    rules = _rules(min_corpus_size=50, min_window_queries=100)
    score = None
    for i in range(4):
        score = ext.observe_query(
            subject="alice",
            tenant_id="default",
            document_ids=[f"doc-{i}"],
            query=f"q {i}",
            corpus_size=10,  # below floor → coverage signal off
            rules=rules,
        )
    assert score.corpus_coverage == 0.0
    assert score.severity == "none"


def test_window_ttl_evicts_old_entries():
    rules = _rules(window_seconds=100, min_window_queries=100)
    ext.observe_query(
        subject="alice", tenant_id="default", document_ids=["doc-old"],
        query="old", corpus_size=10, rules=rules, now=1000.0,
    )
    score = ext.observe_query(
        subject="alice", tenant_id="default", document_ids=["doc-new"],
        query="new", corpus_size=10, rules=rules, now=2000.0,  # >100s later
    )
    # Only the recent entry survives the window.
    assert score.window_queries == 1
    assert score.distinct_documents == 1


def test_watch_lists_offenders():
    rules = _rules(min_window_queries=5, severe_coverage=0.50)
    for i in range(6):
        ext.observe_query(
            subject="scraper", tenant_id="default", document_ids=[f"doc-{i}"],
            query=f"q {i}", corpus_size=10, rules=rules,
        )
    offenders = ext.watch(rules=rules, corpus_sizes={"default": 10})
    assert any(o["subject"] == "scraper" and o["severity"] == "severe" for o in offenders)
    scraper = next(o for o in offenders if o["subject"] == "scraper")
    assert "coverage" in scraper["triggered_by"]
    assert scraper["trigger_summary"]


@pytest.fixture
def client(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setenv("RAG_DATA_DIR", str(data_dir))
    monkeypatch.setenv("RAG_POLICY_FILE", str(CONFIG_DIR / "policy.yaml"))
    monkeypatch.setenv("RAG_ACL_FILE", str(CONFIG_DIR / "acl_policy.yaml"))
    monkeypatch.setenv("RAG_SAMPLE_DOCS", str(CONFIG_DIR / "sample_documents.json"))
    monkeypatch.setenv("RAG_ADMIN_API_KEY", ADMIN_KEY)
    with TestClient(app) as test_client:
        # Arm the monitor with low, deterministic thresholds and a blocking action so
        # the trip returns before any LLM call (keeps the test hermetic/offline).
        # min_window_queries=1: coverage may apply on the first request in this test only.
        app.state.policy.extraction = _rules(
            min_window_queries=1, min_corpus_size=1, severe_coverage=0.2, action="throttle"
        )
        yield test_client


def test_scrape_trips_and_is_recorded(client: TestClient):
    resp = client.post(
        "/v1/query",
        headers={"Authorization": "Bearer employee-demo-token"},
        json={"query": "support policy incident deployment billing", "top_k": 5},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["blocked"] is True
    assert body["block_reason"] == "extraction_suspected"
    assert body.get("block_detail")
    assert "coverage" in body["block_detail"] or "breadth" in body["block_detail"]

    events = client.get(
        "/admin/audit/events",
        headers={"Authorization": f"Bearer {ADMIN_KEY}"},
        params={"kind": "extraction_suspected"},
    )
    assert events.status_code == 200
    assert events.json()["total"] >= 1
    event = events.json()["events"][0]
    assert event["findings"]
    finding = event["findings"][0]
    assert finding["scanner"] == "extraction"
    assert any(sig in finding["category"] for sig in ("coverage", "breadth", "novelty"))
    assert finding["detail"]
    assert "triggered_by" in (event.get("detail") or "")

    watch = client.get(
        "/admin/extraction/watch",
        headers={"Authorization": f"Bearer {ADMIN_KEY}"},
    )
    assert watch.status_code == 200
    assert watch.json()["enabled"] is True
    subjects = watch.json().get("subjects") or []
    assert subjects
    assert subjects[0].get("triggered_by")
    assert subjects[0].get("trigger_summary")
