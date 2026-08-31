"""LLM egress routing by classification (T0.6 / #18 / D6)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import yaml
from fastapi.testclient import TestClient

from rag_protection_proxy.app import app
from rag_protection_proxy.audit import recent, reset_for_tests
from rag_protection_proxy.config import (
    LLMEndpointProfile,
    LLMPolicy,
    LLMRouteRule,
    LLMRoutingPolicy,
    Policy,
    load_policy,
)
from rag_protection_proxy.llm_routing import (
    highest_classification,
    resolve_llm_route,
)

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
ADMIN_KEY = "test-admin-key"


@pytest.fixture(autouse=True)
def _clean():
    reset_for_tests()
    yield
    reset_for_tests()


def _routing_policy(**overrides) -> LLMRoutingPolicy:
    base = LLMRoutingPolicy(
        enabled=True,
        fail_closed=True,
        default_endpoint_id="default",
        classification_rank=[
            "highly-confidential",
            "confidential-hr",
            "confidential",
            "public",
        ],
        endpoints={
            "default": LLMEndpointProfile(),
            "eu-onprem": LLMEndpointProfile(
                base_url="http://llm-eu.internal.example/v1",
                model="hr-onprem",
            ),
            "us-saas": LLMEndpointProfile(
                base_url="http://llm-us.saas.example/v1",
                model="public-faq",
            ),
        },
        routes=[
            LLMRouteRule(match="highly-confidential", endpoint_id="eu-onprem"),
            LLMRouteRule(match="confidential", endpoint_id="eu-onprem"),
            LLMRouteRule(match="public", endpoint_id="us-saas"),
        ],
    )
    for key, value in overrides.items():
        setattr(base, key, value)
    return base


def test_highest_classification_prefers_sensitive_label():
    rank = ["highly-confidential", "confidential", "public"]
    assert highest_classification(["public", "confidential-hr"], rank) == "confidential-hr"
    assert highest_classification(["public"], rank) == "public"


def test_resolve_routes_confidential_to_eu_and_public_to_us():
    policy = Policy(
        llm=LLMPolicy(base_url="http://default.example/v1", model="default-model"),
        llm_routing=_routing_policy(),
    )
    eu = resolve_llm_route(policy, [{"classification": "confidential-hr"}])
    assert not eu.blocked
    assert eu.endpoint_id == "eu-onprem"
    assert eu.llm.base_url == "http://llm-eu.internal.example/v1"
    assert eu.llm.model == "hr-onprem"

    us = resolve_llm_route(policy, [{"classification": "public"}])
    assert not us.blocked
    assert us.endpoint_id == "us-saas"
    assert us.llm.model == "public-faq"


def test_resolve_fail_closed_unmapped_classification():
    policy = Policy(
        llm=LLMPolicy(),
        llm_routing=_routing_policy(),
    )
    decision = resolve_llm_route(policy, [{"classification": "secret-board"}])
    assert decision.blocked
    assert decision.block_reason == "llm_routing_unmapped_classification"


def test_resolve_disabled_uses_default_llm():
    policy = Policy(
        llm=LLMPolicy(base_url="http://only.example/v1", model="only"),
        llm_routing=_routing_policy(enabled=False),
    )
    decision = resolve_llm_route(policy, [{"classification": "confidential-hr"}])
    assert decision.endpoint_id == "default"
    assert decision.llm.model == "only"
    assert decision.reason == "llm_routing_disabled"


def test_load_policy_parses_llm_routing(tmp_path):
    path = tmp_path / "policy.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "llm": {"base_url": "http://default/v1", "model": "base"},
                "llm_routing": {
                    "enabled": True,
                    "fail_closed": True,
                    "default_endpoint_id": "default",
                    "classification_rank": ["confidential", "public"],
                    "endpoints": {
                        "eu-onprem": {
                            "base_url": "http://eu/v1",
                            "model": "eu-model",
                        }
                    },
                    "routes": [{"match": "confidential", "endpoint_id": "eu-onprem"}],
                },
            }
        ),
        encoding="utf-8",
    )
    loaded = load_policy(str(path))
    assert loaded.llm_routing.enabled is True
    assert loaded.llm_routing.endpoints["eu-onprem"].model == "eu-model"
    assert loaded.llm_routing.routes[0].endpoint_id == "eu-onprem"


def _client_env(tmp_path, monkeypatch, *, enable_routing: bool = True):
    data_dir = tmp_path / "data"
    policy_src = (CONFIG_DIR / "policy.yaml").read_text(encoding="utf-8")
    raw = yaml.safe_load(policy_src) or {}
    raw.setdefault("llm_routing", {})
    raw["llm_routing"]["enabled"] = enable_routing
    raw["llm_routing"]["fail_closed"] = True
    raw["llm_routing"]["default_endpoint_id"] = "default"
    raw["llm_routing"]["classification_rank"] = [
        "highly-confidential",
        "confidential-hr",
        "confidential",
        "public",
    ]
    raw["llm_routing"]["endpoints"] = {
        "default": {},
        "eu-onprem": {
            "base_url": "http://llm-eu.internal.example/v1",
            "model": "hr-onprem",
            "api_key": "not-needed",
        },
        "us-saas": {
            "base_url": "http://llm-us.saas.example/v1",
            "model": "public-faq",
            "api_key": "not-needed",
        },
    }
    raw["llm_routing"]["routes"] = [
        {"match": "highly-confidential", "endpoint_id": "eu-onprem"},
        {"match": "confidential", "endpoint_id": "eu-onprem"},
        {"match": "public", "endpoint_id": "us-saas"},
    ]
    # Soften output gates so mocked answers pass
    raw.setdefault("output", {})
    raw["output"]["hard_citation_gate"] = False
    raw["output"]["entailment_check"] = False
    raw["output"]["min_citation_coverage"] = 0.0
    raw.setdefault("extraction", {})
    raw["extraction"]["enabled"] = False
    raw.setdefault("canary", {})
    raw["canary"]["enabled"] = False
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text(yaml.safe_dump(raw), encoding="utf-8")

    monkeypatch.setenv("RAG_DATA_DIR", str(data_dir))
    monkeypatch.setenv("RAG_POLICY_FILE", str(policy_path))
    monkeypatch.setenv("RAG_ACL_FILE", str(CONFIG_DIR / "acl_policy.yaml"))
    monkeypatch.setenv("RAG_SAMPLE_DOCS", str(CONFIG_DIR / "sample_documents.json"))
    monkeypatch.setenv("RAG_ADMIN_API_KEY", ADMIN_KEY)
    return policy_path


def test_query_routes_two_classifications_to_different_endpoints(tmp_path, monkeypatch):
    _client_env(tmp_path, monkeypatch, enable_routing=True)
    captured: list[str] = []

    from rag_protection_proxy.llm import LLMClient

    class TrackingClient(LLMClient):
        def __init__(self, policy):
            captured.append(policy.base_url)
            super().__init__(policy)

    answer = "Support is available Monday through Friday, 9am to 6pm Eastern."

    with TestClient(app) as client:
        with patch("rag_protection_proxy.pipeline.LLMClient", TrackingClient):
            with patch.object(TrackingClient, "chat", new=AsyncMock(return_value=answer)):
                # Public FAQ → us-saas
                pub = client.post(
                    "/v1/query",
                    headers={"Authorization": "Bearer employee-demo-token"},
                    json={"query": "What are support hours?"},
                )
                assert pub.status_code == 200
                pub_body = pub.json()
                assert pub_body.get("blocked") is not True
                assert pub_body["llm_route"]["endpoint_id"] == "us-saas"
                assert pub_body["llm_route"]["model"] == "public-faq"

                # HR payroll (hr token) → eu-onprem
                hr = client.post(
                    "/v1/query",
                    headers={"Authorization": "Bearer hr-demo-token"},
                    json={"query": "What is the Q1 payroll total disbursement?"},
                )
                assert hr.status_code == 200
                hr_body = hr.json()
                assert hr_body.get("blocked") is not True
                assert hr_body["llm_route"]["endpoint_id"] == "eu-onprem"
                assert hr_body["llm_route"]["model"] == "hr-onprem"

    assert "http://llm-us.saas.example/v1" in captured
    assert "http://llm-eu.internal.example/v1" in captured

    events = [e for e in recent(50) if e.kind == "llm_routed"]
    assert len(events) >= 2
    endpoint_ids = {json.loads(e.detail)["endpoint_id"] for e in events}
    assert "us-saas" in endpoint_ids
    assert "eu-onprem" in endpoint_ids


def test_query_fail_closed_blocks_unmapped(tmp_path, monkeypatch):
    _client_env(tmp_path, monkeypatch, enable_routing=True)

    with TestClient(app) as client:
        ingest = client.post(
            "/v1/ingest",
            headers={"Authorization": f"Bearer {ADMIN_KEY}"},
            json={
                "document_id": "board-secret",
                "title": "Board Secret",
                "content": "Unmapped classification residency fixture about alpha project zeta.",
                "allowed_groups": ["all-staff", "engineering"],
                "metadata": {"classification": "secret-board"},
            },
        )
        assert ingest.status_code == 200

        with patch(
            "rag_protection_proxy.pipeline.LLMClient.chat",
            new=AsyncMock(return_value="should not be called"),
        ) as mocked:
            resp = client.post(
                "/v1/query",
                headers={"Authorization": "Bearer employee-demo-token"},
                json={"query": "alpha project zeta residency fixture"},
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["blocked"] is True
            assert body["block_reason"] == "llm_routing_unmapped_classification"
            assert mocked.await_count == 0

    assert any(e.kind == "llm_routed" and e.decision.value == "block" for e in recent(20))
