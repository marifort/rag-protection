"""Thin HTTP client for RAG Protection Proxy APIs.

Supports shipped endpoints (query, ingest, scan, tool gateway).
See docs/enterprise/e7/ for integration guides.

Usage:
    client = RAGProtectionClient(
        "http://localhost:8090",
        admin_token="rag-admin-demo-key",
        user_token="hr-demo-token",
    )
    result = client.query("What are support hours?")

    # Or rely on RAG_PROTECTION_URL (empty/unset → http://localhost:8090):
    client = RAGProtectionClient(user_token="hr-demo-token")
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

try:
    import httpx
except ImportError:  # pragma: no cover - examples may run without httpx in doc-only contexts
    httpx = None  # type: ignore


class RAGProtectionError(Exception):
    """HTTP or API-level error from the proxy."""


DEFAULT_BASE_URL = "http://localhost:8090"


def resolve_base_url(base_url: Optional[str] = None) -> str:
    """Resolve proxy base URL from arg or env; empty values fall back to default.

    ``export RAG_PROTECTION_URL=$BASE`` with unset ``$BASE`` leaves an empty env
    var; ``os.environ.get`` would otherwise skip the default and break httpx.
    """
    raw = (base_url if base_url is not None else os.environ.get("RAG_PROTECTION_URL")) or ""
    url = raw.strip().rstrip("/") or DEFAULT_BASE_URL
    if not url.startswith(("http://", "https://")):
        raise RAGProtectionError(
            f"RAG_PROTECTION_URL must include http:// or https:// (got {url!r}). "
            f"Example: export RAG_PROTECTION_URL={DEFAULT_BASE_URL}"
        )
    return url


def env_or_default(name: str, default: str) -> str:
    """Read an env var; treat missing/blank as ``default``."""
    value = (os.environ.get(name) or "").strip()
    return value or default


class RAGProtectionClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        *,
        admin_token: Optional[str] = None,
        user_token: Optional[str] = None,
        timeout: float = 60.0,
    ) -> None:
        if httpx is None:
            raise ImportError("httpx is required: pip install httpx")
        self.base_url = resolve_base_url(base_url)
        self.admin_token = admin_token or os.environ.get("RAG_PROTECTION_ADMIN_KEY")
        self.user_token = user_token or os.environ.get("RAG_PROTECTION_USER_TOKEN")
        self.timeout = timeout

    def _headers(self, *, admin: bool = False) -> Dict[str, str]:
        token = self.admin_token if admin else self.user_token
        if not token:
            role = "admin" if admin else "user"
            raise RAGProtectionError(f"Missing {role} token")
        return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    def _request(
        self,
        method: str,
        path: str,
        *,
        admin: bool = False,
        params: Optional[Dict[str, str]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if httpx is None:
            raise ImportError("httpx is required: pip install httpx")
        url = f"{self.base_url}{path}"
        if params:
            url = f"{url}?{urlencode(params)}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.request(method, url, headers=self._headers(admin=admin), json=json)
        except httpx.RequestError as exc:
            raise RAGProtectionError(f"{method} {path} failed for {self.base_url}: {exc}") from exc
        if resp.status_code >= 400:
            raise RAGProtectionError(f"{method} {path} → {resp.status_code}: {resp.text}")
        return resp.json()

    def query(
        self,
        query: str,
        *,
        top_k: int = 4,
        include_audit: bool = False,
        audit_debug: bool = False,
    ) -> Dict[str, Any]:
        """POST /v1/query — full secured RAG pipeline (Pattern A)."""
        return self._request(
            "POST",
            "/v1/query",
            json={
                "query": query,
                "top_k": top_k,
                "include_audit": include_audit,
                "audit_debug": audit_debug,
            },
        )

    def ingest(
        self,
        document_id: str,
        title: str,
        content: str,
        *,
        allowed_groups: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tenant_id: str = "default",
        audit_debug: bool = False,
    ) -> Dict[str, Any]:
        """POST /v1/ingest — scan and store in proxy corpus (Pattern B)."""
        body: Dict[str, Any] = {
            "document_id": document_id,
            "title": title,
            "content": content,
            "allowed_groups": allowed_groups or ["all-staff"],
            "metadata": metadata or {},
            "audit_debug": audit_debug,
        }
        return self._request(
            "POST",
            "/v1/ingest",
            admin=True,
            params={"tenant_id": tenant_id},
            json=body,
        )

    def scan(
        self,
        text: str,
        *,
        source: str = "rag:scan:python-client",
        subject: Optional[str] = None,
        trusted: bool = False,
        tenant_id: str = "default",
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """POST /v1/scan — stateless input guardrail (E7.1)."""
        body: Dict[str, Any] = {
            "text": text,
            "source": source,
            "trusted": trusted,
            "context": context or {},
        }
        if subject:
            body["subject"] = subject
        return self._request(
            "POST",
            "/v1/scan",
            admin=True,
            params={"tenant_id": tenant_id},
            json=body,
        )

    def health(self) -> Dict[str, Any]:
        """GET /health."""
        return self._request("GET", "/health")

    def list_tools(self) -> Dict[str, Any]:
        """GET /v1/tools — list registered tools and caller allow flags."""
        return self._request("GET", "/v1/tools")

    def invoke_tool(self, tool: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """POST /v1/tools/invoke — identity-bound tool gateway (Lab 1).

        Returns the JSON body even when the gateway blocks (403/422) so demos
        can show decision/reason without treating policy blocks as transport errors.
        """
        if httpx is None:
            raise ImportError("httpx is required: pip install httpx")
        url = f"{self.base_url}/v1/tools/invoke"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(
                    url,
                    headers=self._headers(admin=False),
                    json={"tool": tool, "arguments": arguments or {}},
                )
        except httpx.RequestError as exc:
            raise RAGProtectionError(
                f"POST /v1/tools/invoke failed for {self.base_url}: {exc}"
            ) from exc
        try:
            body = resp.json()
        except Exception as exc:
            raise RAGProtectionError(
                f"POST /v1/tools/invoke → {resp.status_code}: {resp.text}"
            ) from exc
        if resp.status_code >= 400:
            if isinstance(body, dict) and "decision" in body:
                return body
            raise RAGProtectionError(
                f"POST /v1/tools/invoke → {resp.status_code}: {resp.text}"
            )
        return body
