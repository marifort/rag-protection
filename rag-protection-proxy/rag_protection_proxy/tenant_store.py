"""Per-tenant document store namespace (E2.5)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional

from rag_protection_proxy.config import load_sample_documents
from rag_protection_proxy.store import DocumentStoreBackend, create_document_store

DEFAULT_TENANT = "default"


class TenantDocumentStore:
    """Routes ingest/search to an isolated store per tenant_id."""

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir
        self._stores: Dict[str, DocumentStoreBackend] = {}
        self._seeded: set[str] = set()

    def for_tenant(self, tenant_id: str) -> DocumentStoreBackend:
        tid = tenant_id or DEFAULT_TENANT
        if tid not in self._stores:
            tenant_dir = self._data_dir / "tenants" / tid
            tenant_dir.mkdir(parents=True, exist_ok=True)
            self._stores[tid] = create_document_store(tenant_dir, tenant_id=tid)
            self._sync_sample_corpus(tid)
        return self._stores[tid]

    def _sync_sample_corpus(self, tenant_id: str) -> None:
        if tenant_id in self._seeded:
            return
        store = self._stores[tenant_id]
        sample_path = os.getenv("RAG_SAMPLE_DOCS", "./config/sample_documents.json")
        for doc in load_sample_documents(sample_path):
            store.ingest(
                document_id=str(doc["document_id"]),
                title=str(doc["title"]),
                content=str(doc["content"]),
                allowed_groups=list(doc.get("allowed_groups", ["all-staff"])),
                metadata=dict(doc.get("metadata", {})),
            )
        self._seeded.add(tenant_id)

    def count_documents(self, tenant_id: str = DEFAULT_TENANT) -> int:
        return self.for_tenant(tenant_id).count_documents()

    def count_challenge_documents(self, tenant_id: str = DEFAULT_TENANT) -> int:
        return len(self.for_tenant(tenant_id).list_challenge_documents())

    def tenant_ids(self) -> List[str]:
        base = self._data_dir / "tenants"
        if not base.exists():
            return list(self._stores.keys()) or [DEFAULT_TENANT]
        discovered = sorted(p.name for p in base.iterdir() if p.is_dir())
        return sorted(set(discovered) | set(self._stores.keys()))
