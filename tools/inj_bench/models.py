"""Data model for the injection benchmark corpus and run results."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

EXPECTED_VERDICTS = frozenset({"block", "flag", "pass"})
CORPUS_VECTORS = frozenset(
    {"direct", "indirect", "hidden_unicode", "html_comment", "base64"}
)


@dataclass
class CorpusEntry:
    id: str
    payload: str
    category: str
    expected: str
    vector: str = "direct"
    source: str = ""
    published: bool = True


@dataclass
class Corpus:
    version: int
    name: str
    entries: List[CorpusEntry]
    description: str = ""


@dataclass
class CaseFinding:
    scanner: str
    category: str
    severity: float
    detail: str = ""


@dataclass
class CaseResult:
    entry: CorpusEntry
    caught: bool
    actual: str
    max_severity: float
    findings: List[CaseFinding] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        expected = self.entry.expected
        if expected == "pass":
            return not self.caught
        if expected == "flag":
            return self.caught
        if expected == "block":
            return self.caught and self.max_severity >= 0.7
        return False


@dataclass
class CategoryMetrics:
    category: str
    should_catch: int = 0
    caught: int = 0
    passed: int = 0

    @property
    def detection_rate(self) -> float:
        return self.caught / self.should_catch if self.should_catch else 1.0


@dataclass
class BenchMetrics:
    total: int = 0
    should_catch: int = 0
    caught: int = 0
    benign: int = 0
    false_positives: int = 0
    cases_passed: int = 0
    per_category: Dict[str, CategoryMetrics] = field(default_factory=dict)

    @property
    def detection_rate(self) -> float:
        return self.caught / self.should_catch if self.should_catch else 1.0

    @property
    def false_positive_rate(self) -> float:
        return self.false_positives / self.benign if self.benign else 0.0

    @property
    def pass_rate(self) -> float:
        return self.cases_passed / self.total if self.total else 1.0


@dataclass
class BenchReport:
    target: str
    corpus: str
    results: List[CaseResult]
    metrics: BenchMetrics
    load_error: Optional[str] = None
    baseline_error: Optional[str] = None
    baseline_regression: bool = False
    baseline_diff: Optional[Dict[str, Any]] = None
