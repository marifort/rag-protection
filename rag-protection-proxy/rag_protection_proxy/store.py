"""SQLite-backed document store with ACL metadata and lexical retrieval."""

from __future__ import annotations

import json
import math
import os
import re
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Tuple

from rag_protection_proxy.acl import user_can_access_document


def _document_status(metadata: Dict[str, Any]) -> str:
    return str(metadata.get("status") or "active")


def _is_quarantined(metadata: Dict[str, Any]) -> bool:
    return _document_status(metadata) == "quarantined"


def _is_challenge_quarantine(metadata: Dict[str, Any]) -> bool:
    if not _is_quarantined(metadata):
        return False
    decision = metadata.get("quarantine_decision")
    if decision is None:
        return True
    return str(decision).lower() == "challenge"


def _document_status_fields(metadata: Dict[str, Any]) -> Dict[str, Any]:
    status = _document_status(metadata)
    fields: Dict[str, Any] = {"status": status}
    if _is_quarantined(metadata):
        fields["quarantine_decision"] = metadata.get("quarantine_decision") or "challenge"
        fields["quarantine_reason"] = metadata.get("quarantine_reason")
        fields["quarantine_risk_score"] = metadata.get("quarantine_risk_score")
        fields["quarantine_scanners"] = list(metadata.get("quarantine_scanners") or [])
        fields["quarantine_categories"] = list(metadata.get("quarantine_categories") or [])
    return fields


def _quarantine_list_fields(metadata: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "status": "quarantined",
        "quarantine_decision": metadata.get("quarantine_decision") or "challenge",
        "quarantine_reason": metadata.get("quarantine_reason"),
        "quarantine_risk_score": metadata.get("quarantine_risk_score"),
        "quarantine_scanners": list(metadata.get("quarantine_scanners") or []),
        "quarantine_categories": list(metadata.get("quarantine_categories") or []),
    }


def _assemble_document_content(chunks: List[Dict[str, Any]]) -> str:
    ordered = sorted(chunks, key=lambda chunk: int(chunk["chunk_index"]))
    return "\n\n".join(str(chunk["text"]) for chunk in ordered)


def _chunk_detail_rows(rows: List[Any]) -> List[Dict[str, Any]]:
    chunks: List[Dict[str, Any]] = []
    for row in rows:
        text = str(row["text"] if hasattr(row, "keys") else row[2])
        chunk_index = int(row["chunk_index"] if hasattr(row, "keys") else row[1])
        chunk_id = str(row["chunk_id"] if hasattr(row, "keys") else row[0])
        chunks.append(
            {
                "chunk_id": chunk_id,
                "chunk_index": chunk_index,
                "text": text,
                "char_count": len(text),
            }
        )
    return chunks


class DocumentStoreBackend(Protocol):
    def ingest(
        self,
        document_id: str,
        title: str,
        content: str,
        allowed_groups: List[str],
        metadata: Optional[Dict[str, Any]] = None,
        chunk_size: int = 600,
    ) -> int: ...

    def search(self, query: str, user_groups: List[str], top_k: int = 4) -> List["StoredChunk"]: ...

    def count_documents(self) -> int: ...

    def list_documents(self) -> List[Dict[str, Any]]: ...

    def list_quarantined_documents(self) -> List[Dict[str, Any]]: ...

    def list_challenge_documents(self) -> List[Dict[str, Any]]: ...

    def set_document_status(self, document_id: str, status: str) -> bool: ...

    def delete_document(self, document_id: str) -> bool: ...

    def get_document_detail(self, document_id: str) -> Optional[Dict[str, Any]]: ...


@dataclass
class StoredChunk:
    chunk_id: str
    document_id: str
    title: str
    text: str
    allowed_groups: List[str]
    score: float
    metadata: Dict[str, Any]


class DocumentStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    document_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    allowed_groups TEXT NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    created_at REAL NOT NULL DEFAULT (strftime('%s','now'))
                );
                CREATE TABLE IF NOT EXISTS chunks (
                    chunk_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    FOREIGN KEY(document_id) REFERENCES documents(document_id)
                );
                CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id);
                """
            )

    def ingest(
        self,
        document_id: str,
        title: str,
        content: str,
        allowed_groups: List[str],
        metadata: Optional[Dict[str, Any]] = None,
        chunk_size: int = 600,
    ) -> int:
        metadata = metadata or {}
        chunks = _split_chunks(content, chunk_size=chunk_size)
        with self._connect() as conn:
            conn.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
            conn.execute("DELETE FROM documents WHERE document_id = ?", (document_id,))
            conn.execute(
                "INSERT INTO documents (document_id, title, allowed_groups, metadata) VALUES (?, ?, ?, ?)",
                (document_id, title, json.dumps(allowed_groups), json.dumps(metadata)),
            )
            for idx, chunk_text in enumerate(chunks):
                conn.execute(
                    "INSERT INTO chunks (chunk_id, document_id, chunk_index, text) VALUES (?, ?, ?, ?)",
                    (f"{document_id}::{idx}", document_id, idx, chunk_text),
                )
            conn.commit()
        return len(chunks)

    def search(self, query: str, user_groups: List[str], top_k: int = 4) -> List[StoredChunk]:
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT c.chunk_id, c.document_id, c.text, d.title, d.allowed_groups, d.metadata
                FROM chunks c
                JOIN documents d ON d.document_id = c.document_id
                """
            ).fetchall()

        scored: List[StoredChunk] = []
        for row in rows:
            allowed_groups = json.loads(row["allowed_groups"])
            metadata = json.loads(row["metadata"] or "{}")
            if _is_quarantined(metadata):
                continue
            if not user_can_access_document(user_groups, allowed_groups):
                continue
            text = row["text"]
            score = _score_overlap(query_tokens, _tokenize(text))
            if score <= 0:
                continue
            scored.append(
                StoredChunk(
                    chunk_id=row["chunk_id"],
                    document_id=row["document_id"],
                    title=row["title"],
                    text=text,
                    allowed_groups=allowed_groups,
                    score=score,
                    metadata=metadata,
                )
            )

        scored.sort(key=lambda c: c.score, reverse=True)
        return scored[:top_k]

    def search_with_trace(
        self,
        query: str,
        user_groups: List[str],
        top_k: int = 4,
        *,
        max_trace_candidates: int = 100,
    ) -> Tuple[List[StoredChunk], List["RetrievalDecision"]]:
        from rag_protection_proxy.models import RetrievalDecision

        query_tokens = _tokenize(query)
        if not query_tokens:
            return [], []

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT c.chunk_id, c.document_id, c.text, d.title, d.allowed_groups, d.metadata
                FROM chunks c
                JOIN documents d ON d.document_id = c.document_id
                """
            ).fetchall()

        scored: List[StoredChunk] = []
        trace: List[RetrievalDecision] = []
        for row in rows:
            allowed_groups = json.loads(row["allowed_groups"])
            metadata = json.loads(row["metadata"] or "{}")
            chunk_id = row["chunk_id"]
            document_id = row["document_id"]
            title = row["title"]
            if _is_quarantined(metadata):
                trace.append(
                    RetrievalDecision(
                        chunk_id=chunk_id,
                        document_id=document_id,
                        title=title,
                        score=0.0,
                        outcome="excluded_quarantine",
                        detail="metadata.status=quarantined",
                    )
                )
                continue
            if not user_can_access_document(user_groups, allowed_groups):
                trace.append(
                    RetrievalDecision(
                        chunk_id=chunk_id,
                        document_id=document_id,
                        title=title,
                        score=0.0,
                        outcome="excluded_acl",
                        detail=f"required groups {allowed_groups}",
                    )
                )
                continue
            text = row["text"]
            score = _score_overlap(query_tokens, _tokenize(text))
            if score <= 0:
                trace.append(
                    RetrievalDecision(
                        chunk_id=chunk_id,
                        document_id=document_id,
                        title=title,
                        score=0.0,
                        outcome="excluded_low_score",
                        detail="no token overlap with query",
                    )
                )
                continue
            scored.append(
                StoredChunk(
                    chunk_id=chunk_id,
                    document_id=document_id,
                    title=title,
                    text=text,
                    allowed_groups=allowed_groups,
                    score=score,
                    metadata=metadata,
                )
            )

        scored.sort(key=lambda c: c.score, reverse=True)
        selected = scored[:top_k]
        selected_ids = {c.chunk_id for c in selected}
        for chunk in scored:
            if chunk.chunk_id in selected_ids:
                trace.append(
                    RetrievalDecision(
                        chunk_id=chunk.chunk_id,
                        document_id=chunk.document_id,
                        title=chunk.title,
                        score=chunk.score,
                        outcome="selected",
                        detail=f"top_{top_k} by score",
                    )
                )
            else:
                trace.append(
                    RetrievalDecision(
                        chunk_id=chunk.chunk_id,
                        document_id=chunk.document_id,
                        title=chunk.title,
                        score=chunk.score,
                        outcome="not_in_top_k",
                        detail=f"ranked below top_{top_k}",
                    )
                )

        cap = max(1, max_trace_candidates)
        if len(trace) > cap:
            # Keep all selected + highest-scoring excluded rows.
            selected_trace = [t for t in trace if t.outcome == "selected"]
            other = [t for t in trace if t.outcome != "selected"]
            other.sort(key=lambda t: t.score, reverse=True)
            trace = selected_trace + other[: max(0, cap - len(selected_trace))]

        return selected, trace

    def count_documents(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS n FROM documents").fetchone()
            return int(row["n"] if row else 0)

    def _document_rows(self) -> List[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(
                """
                SELECT d.document_id, d.title, d.allowed_groups, d.metadata, d.created_at,
                       COUNT(c.chunk_id) AS chunk_count
                FROM documents d
                LEFT JOIN chunks c ON c.document_id = d.document_id
                GROUP BY d.document_id, d.title, d.allowed_groups, d.metadata, d.created_at
                ORDER BY d.title COLLATE NOCASE
                """
            ).fetchall()

    def _row_to_document(self, row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "document_id": row["document_id"],
            "title": row["title"],
            "allowed_groups": json.loads(row["allowed_groups"] or "[]"),
            "metadata": json.loads(row["metadata"] or "{}"),
            "created_at": row["created_at"],
            "chunk_count": int(row["chunk_count"] or 0),
        }

    def list_documents(self) -> List[Dict[str, Any]]:
        docs: List[Dict[str, Any]] = []
        for row in self._document_rows():
            doc = self._row_to_document(row)
            if not _is_quarantined(doc["metadata"]):
                docs.append(doc)
        return docs

    def list_quarantined_documents(self) -> List[Dict[str, Any]]:
        docs: List[Dict[str, Any]] = []
        for row in self._document_rows():
            doc = self._row_to_document(row)
            metadata = doc["metadata"]
            if not _is_quarantined(metadata):
                continue
            doc.update(_quarantine_list_fields(metadata))
            docs.append(doc)
        return docs

    def list_challenge_documents(self) -> List[Dict[str, Any]]:
        return [
            doc
            for doc in self.list_quarantined_documents()
            if _is_challenge_quarantine(doc.get("metadata") or {})
        ]

    def set_document_status(self, document_id: str, status: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT metadata FROM documents WHERE document_id = ?",
                (document_id,),
            ).fetchone()
            if not row:
                return False
            metadata = json.loads(row["metadata"] or "{}")
            if status == "active":
                metadata.pop("status", None)
                metadata.pop("quarantine_decision", None)
                metadata.pop("quarantine_reason", None)
                metadata.pop("quarantine_risk_score", None)
                metadata.pop("quarantine_scanners", None)
                metadata.pop("quarantine_categories", None)
            else:
                metadata["status"] = status
            conn.execute(
                "UPDATE documents SET metadata = ? WHERE document_id = ?",
                (json.dumps(metadata), document_id),
            )
            conn.commit()
        return True

    def update_document_acl(
        self,
        document_id: str,
        allowed_groups: List[str],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Update ACL metadata without re-chunking (ACL sync v2)."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT metadata FROM documents WHERE document_id = ?",
                (document_id,),
            ).fetchone()
            if not row:
                return False
            current = json.loads(row["metadata"] or "{}")
            if metadata:
                current.update(metadata)
            conn.execute(
                "UPDATE documents SET allowed_groups = ?, metadata = ? WHERE document_id = ?",
                (json.dumps(allowed_groups), json.dumps(current), document_id),
            )
            conn.commit()
        return True

    def delete_document(self, document_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM documents WHERE document_id = ?",
                (document_id,),
            ).fetchone()
            if not row:
                return False
            conn.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
            conn.execute("DELETE FROM documents WHERE document_id = ?", (document_id,))
            conn.commit()
        return True

    def get_document_detail(self, document_id: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            doc_row = conn.execute(
                """
                SELECT document_id, title, allowed_groups, metadata, created_at
                FROM documents
                WHERE document_id = ?
                """,
                (document_id,),
            ).fetchone()
            if not doc_row:
                return None
            chunk_rows = conn.execute(
                """
                SELECT chunk_id, chunk_index, text
                FROM chunks
                WHERE document_id = ?
                ORDER BY chunk_index
                """,
                (document_id,),
            ).fetchall()
        metadata = json.loads(doc_row["metadata"] or "{}")
        chunks = _chunk_detail_rows(chunk_rows)
        detail: Dict[str, Any] = {
            "document_id": doc_row["document_id"],
            "title": doc_row["title"],
            "allowed_groups": json.loads(doc_row["allowed_groups"] or "[]"),
            "metadata": metadata,
            "created_at": doc_row["created_at"],
            "chunks": chunks,
            "chunk_count": len(chunks),
            "content": _assemble_document_content(chunks),
        }
        detail.update(_document_status_fields(metadata))
        return detail


def _split_chunks(text: str, chunk_size: int = 600) -> List[str]:
    text = (text or "").strip()
    if not text:
        return []
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: List[str] = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) + 2 <= chunk_size:
            current = f"{current}\n\n{para}".strip()
        else:
            if current:
                chunks.append(current)
            if len(para) <= chunk_size:
                current = para
            else:
                for i in range(0, len(para), chunk_size):
                    chunks.append(para[i : i + chunk_size])
                current = ""
    if current:
        chunks.append(current)
    return chunks or [text[:chunk_size]]


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]{3,}", (text or "").lower())


def _score_overlap(query_tokens: List[str], doc_tokens: List[str]) -> float:
    if not query_tokens or not doc_tokens:
        return 0.0
    q = set(query_tokens)
    d = set(doc_tokens)
    overlap = len(q & d)
    if overlap == 0:
        return 0.0
    idf_boost = sum(1.0 + math.log1p(doc_tokens.count(t)) for t in q & d)
    return overlap / len(q) + 0.01 * idf_boost


def new_document_id(prefix: str = "doc") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def create_document_store(data_dir: Path, tenant_id: str = "default") -> DocumentStoreBackend:
    backend = os.getenv("RAG_STORE_BACKEND", "sqlite").strip().lower()
    if backend == "vector":
        from rag_protection_proxy.vector_store import VectorDocumentStore

        base_collection = os.getenv("RAG_QDRANT_COLLECTION", "rag_chunks")
        collection = base_collection if tenant_id == "default" else f"{base_collection}_{tenant_id}"
        return VectorDocumentStore(
            qdrant_url=os.getenv("RAG_QDRANT_URL", "http://localhost:6333"),
            collection=collection,
            data_dir=data_dir,
        )
    if backend == "hybrid":
        from rag_protection_proxy.vector_store import VectorDocumentStore

        base_collection = os.getenv("RAG_QDRANT_COLLECTION", "rag_chunks")
        collection = base_collection if tenant_id == "default" else f"{base_collection}_{tenant_id}"
        lexical = DocumentStore(data_dir / "documents.db")
        vector = VectorDocumentStore(
            qdrant_url=os.getenv("RAG_QDRANT_URL", "http://localhost:6333"),
            collection=collection,
            data_dir=data_dir,
        )
        return HybridDocumentStore(lexical=lexical, vector=vector)
    if backend == "pgvector":
        try:
            from rag_protection_enterprise.store_backends import create_pgvector_store
        except ImportError as exc:
            raise ImportError(
                "pgvector backend requires rag-protection-enterprise. "
                "Install the Enterprise wheel or use RAG_STORE_BACKEND=sqlite|vector|hybrid."
            ) from exc
        return create_pgvector_store(data_dir, tenant_id)
    return DocumentStore(data_dir / "documents.db")


class HybridDocumentStore:
    """Lexical + vector retrieval with reciprocal-rank fusion (E3.6)."""

    def __init__(
        self,
        lexical: DocumentStore,
        vector: "VectorDocumentStore",
        rrf_k: int = 60,
    ) -> None:
        self._lexical = lexical
        self._vector = vector
        self._rrf_k = rrf_k

    def ingest(
        self,
        document_id: str,
        title: str,
        content: str,
        allowed_groups: List[str],
        metadata: Optional[Dict[str, Any]] = None,
        chunk_size: int = 600,
    ) -> int:
        lexical_count = self._lexical.ingest(
            document_id, title, content, allowed_groups, metadata, chunk_size=chunk_size
        )
        vector_count = self._vector.ingest(
            document_id, title, content, allowed_groups, metadata, chunk_size=chunk_size
        )
        return max(lexical_count, vector_count)

    def search(self, query: str, user_groups: List[str], top_k: int = 4) -> List[StoredChunk]:
        fetch_k = max(top_k * 3, top_k)
        lexical_hits = self._lexical.search(query, user_groups, top_k=fetch_k)
        vector_hits = self._vector.search(query, user_groups, top_k=fetch_k)
        return _fuse_chunks(lexical_hits, vector_hits, top_k=top_k, rrf_k=self._rrf_k)

    def search_with_trace(
        self,
        query: str,
        user_groups: List[str],
        top_k: int = 4,
        *,
        max_trace_candidates: int = 100,
    ) -> Tuple[List[StoredChunk], List["RetrievalDecision"]]:
        """Lexical explainability trace; fused ranking still used for selected chunks."""
        from rag_protection_proxy.models import RetrievalDecision

        fetch_k = max(top_k * 3, top_k)
        lexical_hits = self._lexical.search(query, user_groups, top_k=fetch_k)
        vector_hits = self._vector.search(query, user_groups, top_k=fetch_k)
        selected = _fuse_chunks(lexical_hits, vector_hits, top_k=top_k, rrf_k=self._rrf_k)
        _, trace = self._lexical.search_with_trace(
            query, user_groups, top_k=top_k, max_trace_candidates=max_trace_candidates
        )
        selected_ids = {c.chunk_id for c in selected}
        for decision in trace:
            if decision.chunk_id in selected_ids and decision.outcome != "selected":
                decision.outcome = "selected"
                decision.detail = f"top_{top_k} by hybrid fusion"
        return selected, trace

    def count_documents(self) -> int:
        return self._lexical.count_documents()

    def list_documents(self) -> List[Dict[str, Any]]:
        return self._lexical.list_documents()

    def list_quarantined_documents(self) -> List[Dict[str, Any]]:
        return self._lexical.list_quarantined_documents()

    def list_challenge_documents(self) -> List[Dict[str, Any]]:
        return self._lexical.list_challenge_documents()

    def set_document_status(self, document_id: str, status: str) -> bool:
        lexical_ok = self._lexical.set_document_status(document_id, status)
        vector_ok = self._vector.set_document_status(document_id, status)
        return lexical_ok or vector_ok

    def update_document_acl(
        self,
        document_id: str,
        allowed_groups: List[str],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        lexical_ok = self._lexical.update_document_acl(document_id, allowed_groups, metadata)
        vector_ok = self._vector.update_document_acl(document_id, allowed_groups, metadata)
        return lexical_ok or vector_ok

    def delete_document(self, document_id: str) -> bool:
        lexical_ok = self._lexical.delete_document(document_id)
        vector_ok = self._vector.delete_document(document_id)
        return lexical_ok or vector_ok

    def get_document_detail(self, document_id: str) -> Optional[Dict[str, Any]]:
        return self._lexical.get_document_detail(document_id)


def _fuse_chunks(
    lexical_hits: List[StoredChunk],
    vector_hits: List[StoredChunk],
    top_k: int,
    rrf_k: int,
) -> List[StoredChunk]:
    scores: Dict[str, float] = {}
    chunks: Dict[str, StoredChunk] = {}

    for rank, chunk in enumerate(lexical_hits):
        scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + 1.0 / (rrf_k + rank + 1)
        chunks[chunk.chunk_id] = chunk

    for rank, chunk in enumerate(vector_hits):
        scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + 1.0 / (rrf_k + rank + 1)
        if chunk.chunk_id not in chunks:
            chunks[chunk.chunk_id] = chunk

    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    fused: List[StoredChunk] = []
    for chunk_id, fused_score in ranked[:top_k]:
        base = chunks[chunk_id]
        fused.append(
            StoredChunk(
                chunk_id=base.chunk_id,
                document_id=base.document_id,
                title=base.title,
                text=base.text,
                allowed_groups=base.allowed_groups,
                score=round(fused_score, 4),
                metadata=base.metadata,
            )
        )
    return fused
