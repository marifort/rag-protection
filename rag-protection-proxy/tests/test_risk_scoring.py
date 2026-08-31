from rag_protection_proxy.guardrails.risk_scoring import (
    aggregate_risk,
    findings_for_input_block,
)
from rag_protection_proxy.models import Finding


def test_aggregate_risk_rounds_float_noise():
    findings = [
        Finding(scanner="pii", category="ssn", severity=0.7, snippet="**"),
        Finding(scanner="pii", category="phone", severity=0.7, snippet="**"),
    ]
    assert aggregate_risk(findings) == 0.8


def test_findings_for_input_block_drops_pii_keeps_secrets():
    findings = [
        Finding(scanner="pii", category="ssn", severity=0.7, snippet="**"),
        Finding(scanner="pii", category="sin", severity=0.7, snippet="**"),
        Finding(scanner="pii_ner", category="person_name", severity=0.45, snippet="**"),
        Finding(scanner="custom_pattern", category="employee_id", severity=0.6, snippet="**"),
        Finding(scanner="secrets", category="openai_api_key", severity=0.95, snippet="**"),
    ]
    blockable = findings_for_input_block(findings)
    assert {f.scanner for f in blockable} == {"secrets"}
    assert aggregate_risk(blockable) == 0.95
