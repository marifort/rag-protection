"""Lab 3 — SIEM pack sample validation.

Ensures deploy/siem/samples/audit_sample.jsonl lines match the field contract and
include kinds required for shipped detections (including Lab 9/10).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE = REPO_ROOT / "deploy" / "siem" / "samples" / "audit_sample.jsonl"
DETECTIONS = REPO_ROOT / "deploy" / "siem" / "splunk" / "detections.spl"

REQUIRED_FIELDS = {"timestamp", "kind", "decision", "risk_score"}
REQUIRED_KINDS = {
    "scan_input",
    "acl_mapping_failed",
    "tool_invoke",
    "extraction_suspected",
    "canary_triggered",
    "permission_drift",
}

CRITICAL_DETECTIONS = (
    "RAG-Corpus-Extraction",
    "RAG-Canary-Triggered",
    "RAG-Exfil-HighConfidence",
    "RAG-Permission-Drift",
    "RAG-ACL-Mapping-Fail",
)


def _load_samples():
    lines = SAMPLE.read_text(encoding="utf-8").strip().splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def test_sample_file_exists():
    assert SAMPLE.is_file()


def test_detections_file_exists():
    assert DETECTIONS.is_file()
    text = DETECTIONS.read_text(encoding="utf-8")
    assert "RAG-Corpus-Extraction" in text
    assert "RAG-Canary-Triggered" in text
    assert "RAG-Exfil-HighConfidence" in text


@pytest.mark.parametrize("event", _load_samples(), ids=lambda e: e["kind"])
def test_sample_event_schema(event):
    assert REQUIRED_FIELDS <= set(event.keys())
    assert event["decision"] in ("allow", "challenge", "block")
    assert 0.0 <= float(event["risk_score"]) <= 1.0


def test_required_kinds_present():
    kinds = {e["kind"] for e in _load_samples()}
    missing = REQUIRED_KINDS - kinds
    assert not missing, f"missing sample kinds: {missing}"


@pytest.mark.parametrize("rule_name", CRITICAL_DETECTIONS)
def test_critical_detection_documented(rule_name):
    text = DETECTIONS.read_text(encoding="utf-8")
    assert rule_name in text


def test_onboard_script_exists():
    onboard = REPO_ROOT / "tools" / "siem_onboard.sh"
    assert onboard.is_file()
    content = onboard.read_text(encoding="utf-8")
    assert "audit_sample.jsonl" in content
