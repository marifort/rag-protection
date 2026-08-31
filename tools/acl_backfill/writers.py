"""Vector store writers for ACL backfill (metadata-only patches)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol


@dataclass
class DocumentAclState:
    document_id: str
    allowed_groups: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)
    point_count: int = 1


class BackfillWriter(Protocol):
    def list_documents(self) -> Dict[str, DocumentAclState]: ...

    def update_acl(
        self,
        document_id: str,
        allowed_groups: List[str],
        metadata: Dict[str, Any],
    ) -> bool: ...


class MemoryWriter:
    """In-memory / JSON snapshot writer for dry-run demos and unit tests."""

    def __init__(self, docs: Optional[Dict[str, DocumentAclState]] = None) -> None:
        self._docs: Dict[str, DocumentAclState] = dict(docs or {})

    @classmethod
    def from_snapshot(cls, snapshot: Dict[str, Dict[str, Any]]) -> "MemoryWriter":
        docs = {
            doc_id: DocumentAclState(
                document_id=doc_id,
                allowed_groups=list(state.get("allowed_groups") or []),
                metadata=dict(state.get("metadata") or {}),
            )
            for doc_id, state in snapshot.items()
        }
        return cls(docs)

    def list_documents(self) -> Dict[str, DocumentAclState]:
        return {k: DocumentAclState(
            document_id=v.document_id,
            allowed_groups=list(v.allowed_groups),
            metadata=dict(v.metadata),
            point_count=v.point_count,
        ) for k, v in self._docs.items()}

    def update_acl(
        self,
        document_id: str,
        allowed_groups: List[str],
        metadata: Dict[str, Any],
    ) -> bool:
        current = self._docs.get(document_id)
        if current is None:
            return False
        merged = dict(current.metadata)
        merged.update(metadata)
        self._docs[document_id] = DocumentAclState(
            document_id=document_id,
            allowed_groups=list(allowed_groups),
            metadata=merged,
            point_count=current.point_count,
        )
        return True

    def dump_snapshot(self) -> Dict[str, Dict[str, Any]]:
        return {
            doc_id: {
                "allowed_groups": list(state.allowed_groups),
                "metadata": dict(state.metadata),
            }
            for doc_id, state in self._docs.items()
        }

    def write_snapshot(self, path: Path | str) -> None:
        Path(path).write_text(json.dumps(self.dump_snapshot(), indent=2) + "\n", encoding="utf-8")


class QdrantWriter:
    """Patch Qdrant payloads via ``set_payload`` (no re-embed)."""

    def __init__(self, url: str, collection: str, *, api_key: Optional[str] = None) -> None:
        from qdrant_client import QdrantClient

        self.collection = collection
        kwargs: Dict[str, Any] = {"url": url}
        if api_key:
            kwargs["api_key"] = api_key
        self.client = QdrantClient(**kwargs)

    def list_documents(self) -> Dict[str, DocumentAclState]:
        from qdrant_client.models import ScrollRequest  # noqa: F401 — client API

        docs: Dict[str, DocumentAclState] = {}
        offset = None
        while True:
            records, offset = self.client.scroll(
                collection_name=self.collection,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            if not records:
                break
            for record in records:
                payload = dict(record.payload or {})
                doc_id = str(payload.get("document_id") or "").strip()
                if not doc_id:
                    continue
                groups = [str(g) for g in (payload.get("allowed_groups") or [])]
                meta = dict(payload.get("metadata") or {})
                existing = docs.get(doc_id)
                if existing is None:
                    docs[doc_id] = DocumentAclState(
                        document_id=doc_id,
                        allowed_groups=groups,
                        metadata=meta,
                        point_count=1,
                    )
                else:
                    existing.point_count += 1
            if offset is None:
                break
        return docs

    def update_acl(
        self,
        document_id: str,
        allowed_groups: List[str],
        metadata: Dict[str, Any],
    ) -> bool:
        from qdrant_client.models import FieldCondition, Filter, MatchValue

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
                with_vectors=False,
            )
            if not records:
                break
            point_ids = []
            # Merge metadata once from first point, then apply same payload to all.
            first_payload = dict(records[0].payload or {})
            merged_meta = dict(first_payload.get("metadata") or {})
            merged_meta.update(metadata)
            payload = {
                "allowed_groups": list(allowed_groups),
                "metadata": merged_meta,
            }
            for record in records:
                point_ids.append(record.id)
            if point_ids:
                self.client.set_payload(
                    collection_name=self.collection,
                    payload=payload,
                    points=point_ids,
                )
                updated = True
            if offset is None:
                break
        return updated


class PgvectorWriter:
    """Patch pgvector docs + chunks via ``update_document_acl`` (no re-embed)."""

    def __init__(self, connection_url: str, *, table_prefix: str = "rag") -> None:
        from rag_protection_enterprise.pgvector_store import PgVectorDocumentStore

        self.store = PgVectorDocumentStore(
            connection_url=connection_url,
            table_prefix=table_prefix,
        )

    def list_documents(self) -> Dict[str, DocumentAclState]:
        docs: Dict[str, DocumentAclState] = {}
        for row in self.store._document_rows():  # noqa: SLF001 — intentional store peek
            doc_id = str(row["document_id"])
            docs[doc_id] = DocumentAclState(
                document_id=doc_id,
                allowed_groups=list(row.get("allowed_groups") or []),
                metadata=dict(row.get("metadata") or {}),
            )
        return docs

    def update_acl(
        self,
        document_id: str,
        allowed_groups: List[str],
        metadata: Dict[str, Any],
    ) -> bool:
        return bool(self.store.update_document_acl(document_id, allowed_groups, metadata))
