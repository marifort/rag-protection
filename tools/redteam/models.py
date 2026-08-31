"""Scenario and result models for the red-team harness."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class IngestSpec:
    document_id: str
    title: str
    content: str
    allowed_groups: List[str] = field(default_factory=lambda: ["all-staff"])


@dataclass
class AttackSpec:
    token: str
    query: str


@dataclass
class ExpectSpec:
    decision: str
    control: Optional[str] = None
    not_in_answer: List[str] = field(default_factory=list)


@dataclass
class Scenario:
    id: str
    title: str
    owasp: Optional[str] = None
    setup_ingest: List[IngestSpec] = field(default_factory=list)
    attack: Optional[AttackSpec] = None
    expect: Optional[ExpectSpec] = None
    uses_sample_corpus: bool = False
    exploitability: float = 0.7
    sensitivity: float = 0.7


@dataclass
class ScenarioResult:
    scenario_id: str
    title: str
    passed: bool
    messages: List[str] = field(default_factory=list)
    ingest_results: List[Dict[str, Any]] = field(default_factory=list)
    query_result: Optional[Dict[str, Any]] = None
    risk_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "title": self.title,
            "passed": self.passed,
            "messages": self.messages,
            "ingest_results": self.ingest_results,
            "query_result": self.query_result,
            "risk_score": round(self.risk_score, 3),
        }
