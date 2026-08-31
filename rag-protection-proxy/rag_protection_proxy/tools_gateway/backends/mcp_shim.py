"""MCP Streamable HTTP client — Layer 2 backend shim (L1-101)."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

import httpx

from rag_protection_proxy.tools_gateway.policy import ToolPolicyEntry

PROTOCOL_VERSION = "2024-11-05"
DEFAULT_TIMEOUT_SECONDS = float(os.getenv("MCP_BACKEND_TIMEOUT_SECONDS", "30"))

# backend key -> env var holding Streamable HTTP MCP endpoint (e.g. http://mcp-filesystem:8000/mcp)
MCP_BACKEND_URL_ENV: Dict[str, str] = {
    "mcp_filesystem": "MCP_FILESYSTEM_URL",
}

# MCP filesystem server only allows absolute paths under this root (compose mount).
MCP_FILESYSTEM_WORKSPACE_ROOT = os.getenv("MCP_FILESYSTEM_WORKSPACE_ROOT", "/workspace").rstrip("/")


class McpShimError(RuntimeError):
    """Raised when MCP JSON-RPC or transport fails."""


class McpStreamableHttpClient:
    """Minimal MCP client for Streamable HTTP (POST /mcp)."""

    def __init__(self, endpoint_url: str, *, timeout: float = DEFAULT_TIMEOUT_SECONDS):
        self.endpoint_url = endpoint_url.rstrip("/")
        self.timeout = timeout
        self._session_id: Optional[str] = None
        self._request_id = 0
        self._initialized = False

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _headers(self, *, include_session: bool) -> Dict[str, str]:
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        if include_session and self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
            headers["MCP-Protocol-Version"] = PROTOCOL_VERSION
        return headers

    def _post(self, payload: Dict[str, Any], *, include_session: bool = True) -> Dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            try:
                resp = client.post(
                    self.endpoint_url,
                    json=payload,
                    headers=self._headers(include_session=include_session),
                )
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                raise McpShimError(f"MCP transport failed: {exc}") from exc

        session = resp.headers.get("Mcp-Session-Id")
        if session:
            self._session_id = session

        if not resp.content:
            # notifications/initialized returns 202 Accepted with an empty body
            if "id" not in payload:
                return {}
            raise McpShimError("Empty MCP response body")

        content_type = resp.headers.get("content-type", "")
        if "application/json" in content_type:
            body = resp.json()
            if not isinstance(body, dict):
                raise McpShimError("MCP response was not a JSON object")
            if body.get("error"):
                err = body["error"]
                message = err.get("message") if isinstance(err, dict) else str(err)
                raise McpShimError(message or "MCP JSON-RPC error")
            result = body.get("result")
            return result if isinstance(result, dict) else {"value": result}

        if "text/event-stream" in content_type:
            return self._parse_sse_json(resp.text)

        raise McpShimError(f"Unexpected MCP content type: {content_type or 'unknown'}")

    @staticmethod
    def _parse_sse_json(text: str) -> Dict[str, Any]:
        for line in text.splitlines():
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if not data:
                continue
            msg = json.loads(data)
            if not isinstance(msg, dict):
                continue
            if msg.get("error"):
                err = msg["error"]
                message = err.get("message") if isinstance(err, dict) else str(err)
                raise McpShimError(message or "MCP JSON-RPC error")
            result = msg.get("result")
            return result if isinstance(result, dict) else {"value": result}
        raise McpShimError("No JSON payload in MCP SSE response")

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        self._post(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "rag-protection-proxy", "version": "0.1.0"},
                },
            },
            include_session=False,
        )
        self._post(
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            },
        )
        self._initialized = True

    def list_tools(self) -> Dict[str, Any]:
        self._ensure_initialized()
        return self._post(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "tools/list",
                "params": {},
            },
        )

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        self._ensure_initialized()
        result = self._post(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
            },
        )
        if result.get("isError"):
            texts = [
                item.get("text", "")
                for item in result.get("content", [])
                if isinstance(item, dict) and item.get("type") == "text"
            ]
            raise McpShimError("; ".join(t for t in texts if t) or "MCP tool returned error")
        return result


_clients: Dict[str, McpStreamableHttpClient] = {}


def _client_for_url(url: str) -> McpStreamableHttpClient:
    if url not in _clients:
        _clients[url] = McpStreamableHttpClient(url)
    return _clients[url]


def reset_clients_for_tests() -> None:
    _clients.clear()


def mcp_url_for_backend(backend: str) -> str:
    env_name = MCP_BACKEND_URL_ENV.get(backend)
    if not env_name:
        raise McpShimError(f"No MCP URL env mapping for backend {backend!r}")
    url = os.getenv(env_name, "").strip()
    if not url:
        raise McpShimError(f"{env_name} is not set")
    return url


def resolve_mcp_tool_name(entry: ToolPolicyEntry) -> str:
    if entry.mcp_tool:
        return entry.mcp_tool
    return entry.name


def normalize_mcp_result(
    mcp_result: Dict[str, Any],
    *,
    tool_name: str,
    arguments: Dict[str, Any],
) -> Dict[str, Any]:
    texts = [
        item.get("text", "")
        for item in mcp_result.get("content", [])
        if isinstance(item, dict) and item.get("type") == "text"
    ]
    text = "\n".join(t for t in texts if t)
    normalized: Dict[str, Any] = {
        "status": "ok",
        "source": "mcp",
        "mcp_tool": tool_name,
        "content": text,
        "bytes": len(text.encode("utf-8")),
        "raw_content": mcp_result.get("content", []),
    }
    path = arguments.get("path")
    if isinstance(path, str) and path:
        normalized["path"] = path
    return normalized


def normalize_mcp_arguments(
    arguments: Dict[str, Any],
    entry: ToolPolicyEntry,
) -> Dict[str, Any]:
    args = dict(arguments)
    if entry.backend != "mcp_filesystem":
        return args
    path = args.get("path")
    if not isinstance(path, str) or not path:
        return args
    root = MCP_FILESYSTEM_WORKSPACE_ROOT
    if path.startswith(f"{root}/") or path == root:
        return args
    relative = path.lstrip("/")
    args["path"] = f"{root}/{relative}"
    return args


def invoke_mcp_backend(
    arguments: Dict[str, Any],
    entry: ToolPolicyEntry,
) -> Dict[str, Any]:
    url = mcp_url_for_backend(entry.backend)
    tool_name = resolve_mcp_tool_name(entry)
    mcp_args = normalize_mcp_arguments(arguments, entry)
    client = _client_for_url(url)
    mcp_result = client.call_tool(tool_name, mcp_args)
    return normalize_mcp_result(mcp_result, tool_name=tool_name, arguments=arguments)
