"""Core grounding check: load inputs, call the shipped guardrail, aggregate.

Wraps ``rag_protection_proxy.guardrails.citation.verify_citations`` — the same
per-sentence grounding + system-prompt-leak check the gateway runs on every
answer. Nothing here re-implements scoring; it only marshals inputs, builds an
:class:`~rag_protection_proxy.config.OutputPolicy` from the CLI flags, and rolls
single/batch results up into an aggregate pass rate.

Entailment (``--entailment``) uses an offline lexical embedder (``HashEmbedder``)
so the tool never downloads a model or makes a network call — it stays a
local-only lead magnet.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional, Tuple

from . import _bootstrap

_bootstrap.ensure_proxy_importable()

# Imported after bootstrap so the runtime guardrail is guaranteed importable.
from rag_protection_proxy.config import OutputPolicy  # noqa: E402
from rag_protection_proxy.embeddings import HashEmbedder  # noqa: E402
from rag_protection_proxy.guardrails.citation import verify_citations  # noqa: E402
from rag_protection_proxy.models import CitationCheck, CitationClaim  # noqa: E402

SourceChunk = Tuple[str, str]

DEFAULT_THRESHOLD = 0.75
DEFAULT_ENTAILMENT_THRESHOLD = 0.55
DEFAULT_MIN_PASS_RATE = 1.0


class GroundingInputError(Exception):
    """Raised when an answer / sources / jsonl input cannot be parsed (exit code 2)."""


@dataclass
class GroundingResult:
    """Verdict for a single answer, wrapping the shipped ``CitationCheck``."""

    check: CitationCheck
    threshold: float
    id: Optional[str] = None
    index: Optional[int] = None

    @property
    def passed(self) -> bool:
        return self.check.passed

    @property
    def coverage_ratio(self) -> float:
        return self.check.coverage_ratio

    @property
    def system_prompt_leak(self) -> bool:
        return self.check.system_prompt_leak

    @property
    def detail(self) -> str:
        return self.check.detail

    @property
    def claims(self) -> List[CitationClaim]:
        return list(self.check.claims)

    @property
    def ungrounded_claims(self) -> List[CitationClaim]:
        return [c for c in self.check.claims if not c.supported]

    @property
    def verdict(self) -> str:
        if self.check.system_prompt_leak:
            return "leak"
        return "grounded" if self.check.passed else "ungrounded"


@dataclass
class BatchResult:
    """Aggregate over many :class:`GroundingResult` items (one per jsonl line)."""

    results: List[GroundingResult]
    threshold: float
    min_pass_rate: float

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed_count(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def leak_count(self) -> int:
        return sum(1 for r in self.results if r.system_prompt_leak)

    @property
    def pass_rate(self) -> float:
        return self.passed_count / self.total if self.total else 0.0

    @property
    def gate_passed(self) -> bool:
        return self.pass_rate >= self.min_pass_rate


def build_policy(
    *,
    threshold: float = DEFAULT_THRESHOLD,
    entailment: bool = False,
    entailment_threshold: float = DEFAULT_ENTAILMENT_THRESHOLD,
) -> OutputPolicy:
    """Translate CLI flags into the runtime ``OutputPolicy`` the guardrail consumes."""
    return OutputPolicy(
        min_citation_coverage=threshold,
        block_system_prompt_leak=True,
        per_claim_citations=True,  # always on so we can list ungrounded sentences
        entailment_check=entailment,
        entailment_threshold=entailment_threshold,
    )


def check_answer(
    answer: str,
    sources: List[SourceChunk],
    *,
    threshold: float = DEFAULT_THRESHOLD,
    entailment: bool = False,
    entailment_threshold: float = DEFAULT_ENTAILMENT_THRESHOLD,
    id: Optional[str] = None,
    index: Optional[int] = None,
) -> GroundingResult:
    """Score one ``answer`` against its ``sources`` using the shipped guardrail."""
    policy = build_policy(
        threshold=threshold,
        entailment=entailment,
        entailment_threshold=entailment_threshold,
    )
    # Offline lexical entailment only — never downloads a model / hits the network.
    embedder = HashEmbedder() if entailment else None
    check = verify_citations(answer, sources, policy, embedder=embedder)
    return GroundingResult(check=check, threshold=threshold, id=id, index=index)


def check_jsonl(
    lines: List[dict],
    *,
    threshold: float = DEFAULT_THRESHOLD,
    entailment: bool = False,
    entailment_threshold: float = DEFAULT_ENTAILMENT_THRESHOLD,
    min_pass_rate: float = DEFAULT_MIN_PASS_RATE,
) -> BatchResult:
    """Score a batch of ``{answer, sources, [id]}`` records into an aggregate."""
    results: List[GroundingResult] = []
    for i, record in enumerate(lines):
        answer, sources, rec_id = _parse_record(record, line_no=i + 1)
        results.append(
            check_answer(
                answer,
                sources,
                threshold=threshold,
                entailment=entailment,
                entailment_threshold=entailment_threshold,
                id=rec_id,
                index=i + 1,
            )
        )
    return BatchResult(results=results, threshold=threshold, min_pass_rate=min_pass_rate)


# --------------------------------------------------------------------------- #
# Input loading / normalization
# --------------------------------------------------------------------------- #


def load_answer(path: str) -> str:
    """Read an answer text file; raise on a missing or empty answer."""
    p = Path(path)
    if not p.exists():
        raise GroundingInputError(f"answer file not found: {path}")
    text = p.read_text(encoding="utf-8").strip()
    if not text:
        raise GroundingInputError(f"answer file is empty: {path}")
    return text


def load_sources(path: str) -> List[SourceChunk]:
    """Read + normalize a sources JSON file into ``[(id, text)]`` (>= 1 chunk)."""
    p = Path(path)
    if not p.exists():
        raise GroundingInputError(f"sources file not found: {path}")
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GroundingInputError(f"invalid sources JSON ({path}): {exc}") from exc
    return normalize_sources(raw, where="sources")


def load_jsonl(path: str) -> List[dict]:
    """Read a batch eval set; one JSON object per non-blank line."""
    p = Path(path)
    if not p.exists():
        raise GroundingInputError(f"jsonl file not found: {path}")
    records: List[dict] = []
    for line_no, line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise GroundingInputError(f"invalid JSON on line {line_no}: {exc}") from exc
        if not isinstance(record, dict):
            raise GroundingInputError(f"line {line_no} is not a JSON object")
        records.append(record)
    if not records:
        raise GroundingInputError(f"no records found in {path}")
    return records


def normalize_sources(raw: Any, *, where: str = "sources") -> List[SourceChunk]:
    """Accept several source shapes and return a non-empty ``[(id, text)]`` list.

    Accepted: ``[{"id","text"}]`` (also ``chunk_id`` / ``content``), a bare list
    of strings, or a ``{"chunks": [...]}`` / ``{"sources": [...]}`` wrapper.
    """
    if isinstance(raw, dict):
        if "chunks" in raw:
            raw = raw["chunks"]
        elif "sources" in raw:
            raw = raw["sources"]
    if not isinstance(raw, list):
        raise GroundingInputError(
            f"{where} must be a JSON array of chunks (or a {{'chunks': [...]}} object)"
        )

    chunks: List[SourceChunk] = []
    for i, item in enumerate(raw):
        if isinstance(item, str):
            text = item.strip()
            cid = str(i)
        elif isinstance(item, dict):
            text_val = item.get("text", item.get("content"))
            if not isinstance(text_val, str) or not text_val.strip():
                raise GroundingInputError(f"{where}[{i}] is missing a non-empty 'text'")
            text = text_val
            cid = str(item.get("id", item.get("chunk_id", i)))
        else:
            raise GroundingInputError(f"{where}[{i}] must be a string or an object")
        if not text:
            raise GroundingInputError(f"{where}[{i}] has empty text")
        chunks.append((cid, text))

    if not chunks:
        raise GroundingInputError(f"{where} is empty — at least one source chunk is required")
    return chunks


def _parse_record(record: dict, *, line_no: int) -> Tuple[str, List[SourceChunk], Optional[str]]:
    answer = record.get("answer")
    if not isinstance(answer, str):
        raise GroundingInputError(f"line {line_no}: 'answer' must be a string")
    if "sources" not in record:
        raise GroundingInputError(f"line {line_no}: missing 'sources'")
    sources = normalize_sources(record["sources"], where=f"line {line_no} sources")
    rec_id = record.get("id")
    return answer, sources, (str(rec_id) if rec_id is not None else None)
