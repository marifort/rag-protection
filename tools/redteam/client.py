"""Thin HTTP client for the red-team harness (black-box against any proxy)."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore


class RedTeamClientError(Exception):
    """HTTP or API-level error."""


class RedTeamClient:
    def __init__(
        self,
        base_url: str,
        *,
        admin_token: Optional[str] = None,
        user_token: Optional[str] = None,
        timeout: float = 60.0,
    ) -> None:
        if httpx is None:
            raise ImportError("httpx is required: pip install httpx")
        self.base_url = base_url.rstrip("/")
        self.admin_token = admin_token or os.environ.get("RAG_PROTECTION_ADMIN_KEY")
        self.user_token = user_token
        self.timeout = timeout

    def _headers(
        self,
        *,
        admin: bool = False,
        user_token: Optional[str] = None,
        auth: bool = True,
    ) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if not auth:
            return headers
        token = self.admin_token if admin else (user_token or self.user_token)
        if not token:
            role = "admin" if admin else "user"
            raise RedTeamClientError(f"Missing {role} token")
        headers["Authorization"] = f"Bearer {token}"
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        admin: bool = False,
        user_token: Optional[str] = None,
        auth: bool = True,
        params: Optional[Dict[str, str]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        allow_error_body: bool = False,
    ) -> Any:
        url = f"{self.base_url}{path}"
        if params:
            url = f"{url}?{urlencode(params)}"
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.request(
                    method,
                    url,
                    headers=self._headers(admin=admin, user_token=user_token, auth=auth),
                    json=json_body,
                )
        except httpx.HTTPError as exc:
            raise RedTeamClientError(str(exc)) from exc
        if resp.status_code >= 400 and not allow_error_body:
            raise RedTeamClientError(f"{method} {path} → {resp.status_code}: {resp.text}")
        if resp.headers.get("content-type", "").startswith("application/json"):
            return resp.json()
        return resp.text

    def health(self) -> Dict[str, Any]:
        # /health is public (no bearer token).
        return self._request("GET", "/health", auth=False)

    def ingest(
        self,
        document_id: str,
        title: str,
        content: str,
        *,
        allowed_groups: Optional[List[str]] = None,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        try:
            return self._request(
                "POST",
                "/v1/ingest",
                admin=True,
                params={"tenant_id": tenant_id},
                json_body={
                    "document_id": document_id,
                    "title": title,
                    "content": content,
                    "allowed_groups": allowed_groups or ["all-staff"],
                    "metadata": {},
                },
            )
        except RedTeamClientError as exc:
            text = str(exc)
            if "422" in text:
                marker = ": "
                payload = text.split(marker, 1)[-1]
                try:
                    detail = json.loads(payload)
                except json.JSONDecodeError:
                    detail = {"status": "rejected", "detail": payload}
                if isinstance(detail, dict) and "detail" in detail and isinstance(detail["detail"], dict):
                    return {"status": "rejected", **detail["detail"]}
                if isinstance(detail, dict):
                    return detail
                return {"status": "rejected", "detail": detail}
            raise

    def query(
        self,
        query: str,
        *,
        token: str,
        top_k: int = 4,
        include_audit: bool = False,
    ) -> Dict[str, Any]:
        return self._request(
            "POST",
            "/v1/query",
            user_token=token,
            json_body={
                "query": query,
                "top_k": top_k,
                "include_audit": include_audit,
            },
        )

    def export_audit(self, *, limit: int = 1000, scrub: Optional[bool] = None) -> str:
        params: Dict[str, str] = {"limit": str(limit)}
        if scrub is not None:
            params["scrub"] = "true" if scrub else "false"
        body = self._request("GET", "/admin/audit/export", admin=True, params=params)
        return str(body)
