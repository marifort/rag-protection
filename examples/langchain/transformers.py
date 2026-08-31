"""LangChain DocumentTransformer adapter for RAG Protection scan API (E7.4)."""

from __future__ import annotations

import uuid
from typing import Sequence

from langchain_core.documents import Document
from langchain_core.documents.transformers import BaseDocumentTransformer

from python.rag_protection_client import RAGProtectionClient, RAGProtectionError


class RAGProtectionScanTransformer(BaseDocumentTransformer):
    """Calls POST /v1/scan per document; drops rejected docs, redacts survivors."""

    def __init__(
        self,
        client: RAGProtectionClient,
        *,
        job_id: str | None = None,
        subject: str = "langchain-ingest",
        verbose: bool = True,
    ) -> None:
        self._client = client
        self._job_id = job_id or uuid.uuid4().hex[:12]
        self._subject = subject
        self._verbose = verbose

    def transform_documents(
        self,
        documents: Sequence[Document],
        **kwargs: object,
    ) -> list[Document]:
        accepted: list[Document] = []
        for i, doc in enumerate(documents):
            doc_id = (doc.metadata or {}).get("document_id", f"doc-{i}")
            try:
                result = self._client.scan(
                    doc.page_content,
                    source=f"rag:scan:langchain:{self._job_id}:{doc_id}",
                    subject=self._subject,
                )
            except RAGProtectionError:
                raise

            disposition = result.get("disposition", "reject")
            if disposition == "reject":
                if self._verbose:
                    print(f"Rejected {doc_id}: {result['verdict']['reason']}")
                continue

            meta = dict(doc.metadata or {})
            meta["rag_protection_disposition"] = disposition
            meta["rag_protection_risk_score"] = result["verdict"]["risk_score"]
            accepted.append(
                Document(
                    page_content=result["sanitized_text"],
                    metadata=meta,
                )
            )
            if self._verbose:
                print(
                    f"Accepted {doc_id} ({disposition}, "
                    f"risk={meta['rag_protection_risk_score']})"
                )
        return accepted
