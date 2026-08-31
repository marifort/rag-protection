"""Qdrant-backed vector document store with ACL metadata filters."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
    PointStruct,
    VectorParams,
)

from rag_protection_proxy.acl import user_can_access_document
from rag_protection_proxy.embeddings import VECTOR_SIZE, Embedder, get_embedder
from rag_protection_proxy.store import (
    StoredChunk,
    _assemble_document_content,
    _chunk_detail_rows,
    _document_status_fields,
    _split_chunks,
    _document_status,
    _is_challenge_quarantine,
    _is_quarantined,
    _quarantine_list_fields,
)

logger = logging.getLogger(__name__)


def build_acl_filter(user_groups: List[str]) -> Filter:
    """Metadata filter applied inside the vector query (production ACL pattern)."""
    match_values = sorted(set(user_groups or []) | {"public", "all-staff"})
    return Filter(
        must_not=[
            FieldCondition(key="status", match=MatchValue(value="quarantined")),
        ],
        should=[
            FieldCondition(key="allowed_groups", match=MatchAny(any=match_values)),
        ],
    )


class VectorDocumentStore:
    def __init__(
        self,
        qdrant_url: str = "http://localhost:6333",
        collection: str = "rag_chunks",
        data_dir: Optional[Path] = None,
        client: Optional[QdrantClient] = None,
        embedder: Optional[Embedder] = None,
    ) -> None:
        self.collection = collection
        if client is not None:
            self.client = client
        elif qdrant_url == ":memory:":
            self.client = QdrantClient(":memory:")
        else:
            self.client = QdrantClient(url=qdrant_url)
        self.embedder = get_embedder(data_dir, embedder=embedder)
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        if self.client.collection_exists(self.collection):
            return
        # COSINE = cosine similarity on embedding directions (not MSE).
        # See docs/product/HOW_RAG_WORKS.md § "What cosine means here".
        self.client.create_collection(
            collection_name=self.collection,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
        self.client.create_payload_index(
            collection_name=self.collection,
            field_name="allowed_groups",
            field_schema="keyword",
        )
        self.client.create_payload_index(
            collection_name=self.collection,
            field_name="document_id",
            field_schema="keyword",
        )
        self.client.create_payload_index(
            collection_name=self.collection,
            field_name="status",
            field_schema="keyword",
        )
        logger.info("Created Qdrant collection %s", self.collection)

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
        self.client.delete(
            collection_name=self.collection,
            points_selector=Filter(
                must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
            ),
        )
        chunks = _split_chunks(content, chunk_size=chunk_size)
        if not chunks:
            return 0

        vectors = self.embedder.embed(chunks)
        points: List[PointStruct] = []
        doc_status = _document_status(metadata)
        for idx, (chunk_text, vector) in enumerate(zip(chunks, vectors)):
            chunk_id = f"{document_id}::{idx}"
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))
            points.append(
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "chunk_id": chunk_id,
                        "document_id": document_id,
                        "chunk_index": idx,
                        "title": title,
                        "text": chunk_text,
                        "allowed_groups": allowed_groups,
                        "metadata": metadata,
                        "status": doc_status,
                    },
                )
            )
        self.client.upsert(collection_name=self.collection, points=points)
        return len(points)

    def _hit_to_chunk(self, hit: Any) -> StoredChunk:
        payload = hit.payload or {}
        return StoredChunk(
            chunk_id=str(payload.get("chunk_id", hit.id)),
            document_id=str(payload.get("document_id", "")),
            title=str(payload.get("title", "")),
            text=str(payload.get("text", "")),
            allowed_groups=list(payload.get("allowed_groups") or []),
            score=float(hit.score or 0.0),
            metadata=dict(payload.get("metadata") or {}),
        )

    def search(self, query: str, user_groups: List[str], top_k: int = 4) -> List[StoredChunk]:
        query = (query or "").strip()
        if not query:
            return []

        query_vector = self.embedder.embed([query])[0]
        hits = self.client.query_points(
            collection_name=self.collection,
            query=query_vector,
            query_filter=build_acl_filter(user_groups),
            limit=top_k,
            with_payload=True,
        ).points
        return [self._hit_to_chunk(hit) for hit in hits]

    def search_with_trace(
        self,
        query: str,
        user_groups: List[str],
        top_k: int = 4,
        *,
        max_trace_candidates: int = 100,
    ) -> Tuple[List[StoredChunk], List["RetrievalDecision"]]:
        """Unfiltered candidate query + ACL/quarantine classification (explainability)."""
        from rag_protection_proxy.models import RetrievalDecision

        query = (query or "").strip()
        if not query:
            return [], []

        selected = self.search(query, user_groups, top_k=top_k)
        selected_ids = {c.chunk_id for c in selected}

        query_vector = self.embedder.embed([query])[0]
        # No ACL/quarantine filter — candidates must include drops for the trace.
        limit = max(top_k, max_trace_candidates, len(selected))
        hits = self.client.query_points(
            collection_name=self.collection,
            query=query_vector,
            query_filter=None,
            limit=limit,
            with_payload=True,
        ).points

        trace: List[RetrievalDecision] = []
        seen: set[str] = set()
        for hit in hits:
            chunk = self._hit_to_chunk(hit)
            seen.add(chunk.chunk_id)
            if _is_quarantined(chunk.metadata):
                trace.append(
                    RetrievalDecision(
                        chunk_id=chunk.chunk_id,
                        document_id=chunk.document_id,
                        title=chunk.title,
                        score=chunk.score,
                        outcome="excluded_quarantine",
                        detail="metadata.status=quarantined",
                    )
                )
                continue
            if not user_can_access_document(user_groups, chunk.allowed_groups):
                trace.append(
                    RetrievalDecision(
                        chunk_id=chunk.chunk_id,
                        document_id=chunk.document_id,
                        title=chunk.title,
                        score=chunk.score,
                        outcome="excluded_acl",
                        detail=f"required groups {chunk.allowed_groups}",
                    )
                )
                continue
            if chunk.chunk_id in selected_ids:
                trace.append(
                    RetrievalDecision(
                        chunk_id=chunk.chunk_id,
                        document_id=chunk.document_id,
                        title=chunk.title,
                        score=chunk.score,
                        outcome="selected",
                        detail=f"top_{top_k} by vector score",
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

        # Ensure every returned survivor appears even if outside the candidate window.
        for chunk in selected:
            if chunk.chunk_id in seen:
                continue
            trace.append(
                RetrievalDecision(
                    chunk_id=chunk.chunk_id,
                    document_id=chunk.document_id,
                    title=chunk.title,
                    score=chunk.score,
                    outcome="selected",
                    detail=f"top_{top_k} by vector score",
                )
            )

        cap = max(1, max_trace_candidates)
        if len(trace) > cap:
            selected_trace = [t for t in trace if t.outcome == "selected"]
            other = [t for t in trace if t.outcome != "selected"]
            other.sort(key=lambda t: t.score, reverse=True)
            trace = selected_trace + other[: max(0, cap - len(selected_trace))]

        return selected, trace

    def count_documents(self) -> int:
        return len(self.list_documents())

    def list_documents(self) -> List[Dict[str, Any]]:
        doc_map: Dict[str, Dict[str, Any]] = {}
        offset = None
        while True:
            records, offset = self.client.scroll(
                collection_name=self.collection,
                limit=128,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for record in records:
                payload = record.payload or {}
                document_id = payload.get("document_id")
                if not document_id:
                    continue
                if document_id not in doc_map:
                    doc_map[str(document_id)] = {
                        "document_id": str(document_id),
                        "title": str(payload.get("title", "")),
                        "allowed_groups": list(payload.get("allowed_groups") or []),
                        "metadata": dict(payload.get("metadata") or {}),
                        "created_at": 0,
                        "chunk_count": 0,
                    }
                doc_map[str(document_id)]["chunk_count"] += 1
            if offset is None:
                break
        return sorted(
            [doc for doc in doc_map.values() if not _is_quarantined(doc.get("metadata") or {})],
            key=lambda doc: doc["title"].lower(),
        )

    def list_quarantined_documents(self) -> List[Dict[str, Any]]:
        doc_map: Dict[str, Dict[str, Any]] = {}
        offset = None
        while True:
            records, offset = self.client.scroll(
                collection_name=self.collection,
                limit=128,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for record in records:
                payload = record.payload or {}
                document_id = payload.get("document_id")
                if not document_id:
                    continue
                metadata = dict(payload.get("metadata") or {})
                if not _is_quarantined(metadata):
                    continue
                if document_id not in doc_map:
                    doc_map[str(document_id)] = {
                        "document_id": str(document_id),
                        "title": str(payload.get("title", "")),
                        "allowed_groups": list(payload.get("allowed_groups") or []),
                        "metadata": metadata,
                        "created_at": 0,
                        "chunk_count": 0,
                        **_quarantine_list_fields(metadata),
                    }
                doc_map[str(document_id)]["chunk_count"] += 1
            if offset is None:
                break
        return sorted(doc_map.values(), key=lambda doc: doc["title"].lower())

    def list_challenge_documents(self) -> List[Dict[str, Any]]:
        return [
            doc
            for doc in self.list_quarantined_documents()
            if _is_challenge_quarantine(doc.get("metadata") or {})
        ]

    def set_document_status(self, document_id: str, status: str) -> bool:
        offset = None
        updated = False
        while True:
            records, offset = self.client.scroll(
                collection_name=self.collection,
                scroll_filter=Filter(
                    must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
                ),
                limit=128,
                offset=offset,
                with_payload=True,
                with_vectors=True,
            )
            if not records:
                break
            points: List[PointStruct] = []
            for record in records:
                payload = dict(record.payload or {})
                metadata = dict(payload.get("metadata") or {})
                if status == "active":
                    metadata.pop("status", None)
                    metadata.pop("quarantine_decision", None)
                    metadata.pop("quarantine_reason", None)
                    metadata.pop("quarantine_risk_score", None)
                    metadata.pop("quarantine_scanners", None)
                    metadata.pop("quarantine_categories", None)
                    payload["status"] = "active"
                else:
                    metadata["status"] = status
                    payload["status"] = status
                payload["metadata"] = metadata
                points.append(
                    PointStruct(
                        id=record.id,
                        vector=record.vector or [],
                        payload=payload,
                    )
                )
                updated = True
            if points:
                self.client.upsert(collection_name=self.collection, points=points)
            if offset is None:
                break
        return updated

    def update_document_acl(
        self,
        document_id: str,
        allowed_groups: List[str],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        offset = None
        updated = False
        while True:
            records, offset = self.client.scroll(
                collection_name=self.collection,
                scroll_filter=Filter(
                    must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
                ),
                limit=128,
                offset=offset,
                with_payload=True,
                with_vectors=True,
            )
            if not records:
                break
            points: List[PointStruct] = []
            for record in records:
                payload = dict(record.payload or {})
                payload["allowed_groups"] = list(allowed_groups)
                if metadata:
                    merged = dict(payload.get("metadata") or {})
                    merged.update(metadata)
                    payload["metadata"] = merged
                points.append(
                    PointStruct(
                        id=record.id,
                        vector=record.vector or [],
                        payload=payload,
                    )
                )
                updated = True
            if points:
                self.client.upsert(collection_name=self.collection, points=points)
            if offset is None:
                break
        return updated

    def get_document_detail(self, document_id: str) -> Optional[Dict[str, Any]]:
        title = ""
        allowed_groups: List[str] = []
        metadata: Dict[str, Any] = {}
        chunk_rows: List[Dict[str, Any]] = []
        offset = None
        found = False
        while True:
            records, offset = self.client.scroll(
                collection_name=self.collection,
                scroll_filter=Filter(
                    must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
                ),
                limit=128,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            if not records:
                break
            found = True
            for record in records:
                payload = record.payload or {}
                title = str(payload.get("title") or title)
                allowed_groups = list(payload.get("allowed_groups") or allowed_groups)
                metadata = dict(payload.get("metadata") or metadata)
                chunk_rows.append(
                    {
                        "chunk_id": str(payload.get("chunk_id", record.id)),
                        "chunk_index": int(payload.get("chunk_index", 0)),
                        "text": str(payload.get("text", "")),
                    }
                )
            if offset is None:
                break
        if not found:
            return None
        chunks = _chunk_detail_rows(chunk_rows)
        detail: Dict[str, Any] = {
            "document_id": document_id,
            "title": title,
            "allowed_groups": allowed_groups,
            "metadata": metadata,
            "created_at": 0,
            "chunks": chunks,
            "chunk_count": len(chunks),
            "content": _assemble_document_content(chunks),
        }
        detail.update(_document_status_fields(metadata))
        return detail

    def delete_document(self, document_id: str) -> bool:
        from qdrant_client.models import PointIdsList

        offset = None
        deleted_any = False
        while True:
            records, offset = self.client.scroll(
                collection_name=self.collection,
                scroll_filter=Filter(
                    must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
                ),
                limit=128,
                offset=offset,
                with_payload=False,
                with_vectors=False,
            )
            if not records:
                break
            point_ids = [record.id for record in records]
            self.client.delete(
                collection_name=self.collection,
                points_selector=PointIdsList(points=point_ids),
            )
            deleted_any = True
            if offset is None:
                break
        return deleted_any
