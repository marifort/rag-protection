"""Text embedding helpers for vector retrieval and similarity scoring.

Produces fixed-size (VECTOR_SIZE=384) vectors used by:

- ``vector_store.VectorDocumentStore`` — ingest/query against Qdrant
  (``Distance.COSINE``)
- ``scanners.injection_ml.MLInjectionScanner`` — cosine to jailbreak prototypes
- ``guardrails.citation`` — optional entailment via cosine to source chunks

**Cosine** here means cosine *similarity* (dot product of unit/L2-scaled
vectors), not mean square error / mean square deviation. Sentence-transformer
encodings use ``normalize_embeddings=True``; ``HashEmbedder`` also returns
unit vectors. Conceptual primer:
``docs/product/HOW_RAG_WORKS.md`` § "What cosine means here".
"""

from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path
from typing import List, Optional, Protocol

VECTOR_SIZE = 384


class Embedder(Protocol):
    def embed(self, texts: List[str]) -> List[List[float]]: ...


class SentenceTransformerEmbedder:
    def __init__(self, model_name: str, cache_dir: Optional[Path] = None) -> None:
        from sentence_transformers import SentenceTransformer

        kwargs = {}
        if cache_dir is not None:
            cache_dir.mkdir(parents=True, exist_ok=True)
            kwargs["cache_folder"] = str(cache_dir)
        self._model = SentenceTransformer(model_name, **kwargs)

    def embed(self, texts: List[str]) -> List[List[float]]:
        vectors = self._model.encode(texts, normalize_embeddings=True)
        return [vector.tolist() for vector in vectors]


class HashEmbedder:
    """Deterministic lightweight embedder for unit tests (no ML deps)."""

    def embed(self, texts: List[str]) -> List[List[float]]:
        return [_hash_to_vector(text) for text in texts]


def _hash_to_vector(text: str) -> List[float]:
    digest = hashlib.sha256((text or "").encode("utf-8")).digest()
    values: List[float] = []
    while len(values) < VECTOR_SIZE:
        for idx in range(0, len(digest), 4):
            chunk = digest[idx : idx + 4]
            if len(chunk) < 4:
                chunk = chunk.ljust(4, b"\0")
            values.append(int.from_bytes(chunk, "big") / 2**32)
            if len(values) >= VECTOR_SIZE:
                break
        digest = hashlib.sha256(digest).digest()
    norm = math.sqrt(sum(value * value for value in values)) or 1.0
    return [value / norm for value in values]


def get_embedder(data_dir: Optional[Path] = None, embedder: Optional[Embedder] = None) -> Embedder:
    if embedder is not None:
        return embedder
    backend = os.getenv("RAG_EMBEDDING_BACKEND", "sentence_transformer").strip().lower()
    if backend == "hash":
        return HashEmbedder()
    model_name = os.getenv("RAG_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    cache_dir = data_dir / "models" if data_dir is not None else None
    return SentenceTransformerEmbedder(model_name, cache_dir)
