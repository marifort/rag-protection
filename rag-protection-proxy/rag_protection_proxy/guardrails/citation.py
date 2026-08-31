"""Post-generation citation and alignment verification.

Detects system-prompt leaks via regex and ungrounded answers via per-sentence
grounding against retrieved chunks. E3.4 adds per-claim citations; E3.5 adds
optional entailment scoring for paraphrased answers.

Docs: docs/guardrails/GUARDRAIL_4_CITATION.md
      docs/product/NEXT_STEPS.md § E3.4–E3.5
"""

from __future__ import annotations

import math
import re
from typing import Iterable, List, Optional, Sequence, Set, Tuple

from rag_protection_proxy.config import OutputPolicy
from rag_protection_proxy.embeddings import Embedder, get_embedder
from rag_protection_proxy.models import CitationCheck, CitationClaim

_SYSTEM_PROMPT_LEAK_PATTERNS = [
    re.compile(r"\bas an ai (assistant|language model)\b", re.I),
    re.compile(r"\bmy (core )?(programming|instructions|system prompt)\b", re.I),
    re.compile(r"\bi (was|am) (trained|designed|programmed) (by|to)\b", re.I),
    re.compile(r"<\s*retrieved_untrusted_context\b", re.I),
]

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")

SourceChunk = Tuple[str, str]


def verify_citations(
    answer: str,
    source_chunks: Iterable[SourceChunk] | Iterable[str],
    policy: OutputPolicy,
    embedder: Optional[Embedder] = None,
) -> CitationCheck:
    answer = (answer or "").strip()
    if not answer:
        return CitationCheck(passed=False, coverage_ratio=0.0, detail="empty answer")

    system_prompt_leak = any(p.search(answer) for p in _SYSTEM_PROMPT_LEAK_PATTERNS)
    if policy.block_system_prompt_leak and system_prompt_leak:
        return CitationCheck(
            passed=False,
            coverage_ratio=0.0,
            system_prompt_leak=True,
            detail="response contains system-prompt-like phrasing",
        )

    chunks = _normalize_source_chunks(source_chunks)
    if not chunks:
        return CitationCheck(passed=True, coverage_ratio=1.0, detail="no source chunks to verify")

    sentences = _split_sentences(answer)
    if not sentences:
        sentences = [(answer, 0, len(answer))]

    use_entailment = policy.entailment_check
    embed = embedder or (get_embedder() if use_entailment else None)
    use_lexical_entailment = embed is not None and embed.__class__.__name__ == "HashEmbedder"
    chunk_vectors: Optional[List[List[float]]] = None
    if use_entailment and embed is not None and not use_lexical_entailment:
        chunk_vectors = embed.embed([text for _, text in chunks])

    claims: List[CitationClaim] = []
    supported = 0
    for sentence, offset_start, offset_end in sentences:
        chunk_id, entailment_score = _ground_sentence(
            sentence,
            chunks,
            embed=embed,
            chunk_vectors=chunk_vectors,
            entailment_threshold=policy.entailment_threshold,
            use_entailment=use_entailment,
            use_lexical_entailment=use_lexical_entailment,
        )
        is_supported = chunk_id is not None
        if is_supported:
            supported += 1
        if policy.per_claim_citations:
            claims.append(CitationClaim(
                sentence=sentence,
                chunk_id=chunk_id,
                offset_start=offset_start,
                offset_end=offset_end,
                supported=is_supported,
                entailment_score=entailment_score,
            ))

    coverage = supported / len(sentences)
    substantive_claims = [
        c for c in claims if _is_substantive(c.sentence, policy.substantive_min_tokens)
    ] if policy.per_claim_citations else []
    unsupported = [c for c in substantive_claims if not c.supported]
    hard_gate_failed = bool(
        policy.hard_citation_gate and policy.per_claim_citations and unsupported
    )
    coverage_pass = coverage >= policy.min_citation_coverage
    passed = coverage_pass and not hard_gate_failed
    detail_parts = [f"{supported}/{len(sentences)} sentences aligned with retrieved context"]
    if hard_gate_failed:
        detail_parts.append(f"{len(unsupported)} unsupported substantive claim(s)")
    detail = "; ".join(detail_parts)
    return CitationCheck(
        passed=passed,
        coverage_ratio=round(coverage, 3),
        detail=detail,
        claims=claims,
        hard_gate_failed=hard_gate_failed,
        unsupported_count=len(unsupported),
    )


def _normalize_source_chunks(source_chunks: Iterable[SourceChunk] | Iterable[str]) -> List[SourceChunk]:
    normalized: List[SourceChunk] = []
    for item in source_chunks:
        if isinstance(item, tuple):
            normalized.append((str(item[0]), str(item[1])))
        else:
            normalized.append(("", str(item)))
    return normalized


def _split_sentences(answer: str) -> List[Tuple[str, int, int]]:
    sentences: List[Tuple[str, int, int]] = []
    cursor = 0
    for part in _SENTENCE_SPLIT.split(answer):
        part = part.strip()
        if not part:
            continue
        start = answer.find(part, cursor)
        if start < 0:
            start = cursor
        end = start + len(part)
        sentences.append((part, start, end))
        cursor = end
    return sentences


def _ground_sentence(
    sentence: str,
    chunks: Sequence[SourceChunk],
    embed: Optional[Embedder],
    chunk_vectors: Optional[Sequence[Sequence[float]]],
    entailment_threshold: float,
    use_entailment: bool,
    use_lexical_entailment: bool,
) -> Tuple[Optional[str], Optional[float]]:
    sent_tokens = _tokenize(sentence)
    if len(sent_tokens) < 3:
        return (chunks[0][0] if chunks else None, None)

    sources_joined = " ".join(text.lower() for _, text in chunks)
    overlap = len(sent_tokens & _tokenize(sources_joined)) / max(len(sent_tokens), 1)
    if overlap >= 0.25 or _substring_match(sentence, sources_joined):
        best_chunk = _best_overlap_chunk(sentence, chunks)
        return (best_chunk, overlap if overlap >= 0.25 else 1.0)

    if not use_entailment or embed is None:
        return (None, None)

    if use_lexical_entailment:
        best_id, best_score = _lexical_entailment(sentence, chunks)
        if best_score >= entailment_threshold:
            return (best_id, round(best_score, 3))
        return (None, round(best_score, 3) if best_score > 0 else None)

    sentence_vec = embed.embed([sentence])[0]
    best_id: Optional[str] = None
    best_score = 0.0
    for idx, (chunk_id, _) in enumerate(chunks):
        vec = chunk_vectors[idx] if chunk_vectors else embed.embed([chunks[idx][1]])[0]
        score = _cosine(sentence_vec, vec)
        if score > best_score:
            best_score = score
            best_id = chunk_id
    if best_score >= entailment_threshold:
        return (best_id, round(best_score, 3))
    return (None, round(best_score, 3) if best_score > 0 else None)


def _best_overlap_chunk(sentence: str, chunks: Sequence[SourceChunk]) -> Optional[str]:
    sent_tokens = _tokenize(sentence)
    best_id: Optional[str] = None
    best_overlap = -1.0
    for chunk_id, text in chunks:
        overlap = len(sent_tokens & _tokenize(text)) / max(len(sent_tokens), 1)
        if overlap > best_overlap:
            best_overlap = overlap
            best_id = chunk_id
    return best_id or (chunks[0][0] if chunks else None)


def _lexical_entailment(sentence: str, chunks: Sequence[SourceChunk]) -> Tuple[Optional[str], float]:
    sent_tokens = _tokenize(sentence)
    best_id: Optional[str] = None
    best_score = 0.0
    for chunk_id, text in chunks:
        chunk_tokens = _tokenize(text)
        if not chunk_tokens:
            continue
        score = len(sent_tokens & chunk_tokens) / max(len(sent_tokens), 1)
        if score > best_score:
            best_score = score
            best_id = chunk_id
    return best_id, best_score


def _tokenize(text: str) -> Set[str]:
    return {t for t in re.findall(r"[a-z0-9]{4,}", text.lower())}


def _substring_match(sentence: str, sources: str) -> bool:
    words = [w for w in re.findall(r"[a-z0-9]{5,}", sentence.lower()) if w not in _STOPWORDS]
    if len(words) < 2:
        return False
    phrase = " ".join(words[:6])
    return phrase in sources


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity in [-1, 1] — not mean square error.

    See docs/product/HOW_RAG_WORKS.md § "What cosine means here".
    """
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a)) or 1.0
    norm_b = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (norm_a * norm_b)


_STOPWORDS = {
    "about", "after", "based", "could", "document", "following", "information",
    "please", "should", "their", "there", "these", "those", "which", "would",
}


def _is_substantive(sentence: str, min_tokens: int) -> bool:
    tokens = _tokenize(sentence)
    return len(tokens) >= max(1, min_tokens)
