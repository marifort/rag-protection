"""Unit tests for MCP backend shim (Layer 2 — L1-101)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from rag_protection_proxy.tools_gateway.backends.mcp_shim import (
    McpShimError,
    McpStreamableHttpClient,
    invoke_mcp_backend,
    normalize_mcp_arguments,
    reset_clients_for_tests,
)
from rag_protection_proxy.tools_gateway.policy import ToolPolicyEntry


@pytest.fixture(autouse=True)
def clean_mcp_clients():
    reset_clients_for_tests()
    yield
    reset_clients_for_tests()


def _json_response(payload: dict, *, session_id: str | None = None) -> httpx.Response:
    headers = {"content-type": "application/json"}
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    return httpx.Response(200, json=payload, headers=headers, request=httpx.Request("POST", "http://test/mcp"))


def _init_mcp_handler(calls: list[dict]):
    """Mock MCP Streamable HTTP handler for initialize / initialized / tools/*."""

    def handler(*args, **kwargs) -> httpx.Response:
        request = args[0] if args else kwargs.get("url")
        if isinstance(request, str):
            body = kwargs.get("json", {})
        else:
            body = json.loads(request.content.decode()) if hasattr(request, "content") else kwargs.get("json", {})
        calls.append(body)
        method = body.get("method")
        if method == "initialize":
            return _json_response(
                {"jsonrpc": "2.0", "id": body["id"], "result": {"protocolVersion": "2024-11-05", "capabilities": {}}},
                session_id="sess-1",
            )
        if method == "notifications/initialized":
            return httpx.Response(202, headers={}, request=httpx.Request("POST", "http://test/mcp"))
        if method == "tools/list":
            return _json_response(
                {
                    "jsonrpc": "2.0",
                    "id": body["id"],
                    "result": {
                        "tools": [
                            {
                                "name": "read_text_file",
                                "description": "Read a text file from disk",
                                "inputSchema": {
                                    "type": "object",
                                    "properties": {"path": {"type": "string"}},
                                    "required": ["path"],
                                },
                            }
                        ]
                    },
                },
                session_id="sess-1",
            )
        if method == "tools/call":
            return _json_response(
                {
                    "jsonrpc": "2.0",
                    "id": body["id"],
                    "result": {
                        "content": [{"type": "text", "text": "hello from mcp"}],
                        "isError": False,
                    },
                },
                session_id="sess-1",
            )
        raise AssertionError(f"unexpected method {method!r}")

    return handler


def test_mcp_client_tools_list():
    client = McpStreamableHttpClient("http://mcp-filesystem:8000/mcp", timeout=5.0)
    calls: list[dict] = []

    with patch("rag_protection_proxy.tools_gateway.backends.mcp_shim.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = False
        mock_client.post.side_effect = _init_mcp_handler(calls)
        mock_client_cls.return_value = mock_client

        result = client.list_tools()

    assert calls[0]["method"] == "initialize"
    assert calls[1]["method"] == "notifications/initialized"
    assert calls[2]["method"] == "tools/list"
    assert calls[2]["params"] == {}
    assert result["tools"][0]["name"] == "read_text_file"


def test_mcp_client_tools_call():
    client = McpStreamableHttpClient("http://mcp-filesystem:8000/mcp", timeout=5.0)
    calls: list[dict] = []

    with patch("rag_protection_proxy.tools_gateway.backends.mcp_shim.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = False
        mock_client.post.side_effect = _init_mcp_handler(calls)
        mock_client_cls.return_value = mock_client

        result = client.call_tool("read_text_file", {"path": "/workspace/docs/runbook.md"})

    assert result["isError"] is False
    assert calls[0]["method"] == "initialize"
    assert calls[1]["method"] == "notifications/initialized"
    assert calls[2]["method"] == "tools/call"
    assert calls[2]["params"]["name"] == "read_text_file"
    assert calls[2]["params"]["arguments"] == {"path": "/workspace/docs/runbook.md"}


def test_mcp_client_raises_on_tool_error():
    client = McpStreamableHttpClient("http://mcp-filesystem:8000/mcp", timeout=5.0)

    def handler(*args, **kwargs) -> httpx.Response:
        request = args[0] if args else kwargs.get("url")
        if isinstance(request, str):
            body = kwargs.get("json", {})
        else:
            body = json.loads(request.content.decode()) if hasattr(request, "content") else kwargs.get("json", {})
        if body.get("method") == "initialize":
            return _json_response(
                {"jsonrpc": "2.0", "id": body["id"], "result": {"protocolVersion": "2024-11-05", "capabilities": {}}},
            )
        if body.get("method") == "notifications/initialized":
            return httpx.Response(202, headers={}, request=httpx.Request("POST", "http://test/mcp"))
        if body.get("method") == "tools/call":
            return _json_response(
                {
                    "jsonrpc": "2.0",
                    "id": body["id"],
                    "result": {
                        "content": [{"type": "text", "text": "access denied"}],
                        "isError": True,
                    },
                },
            )
        raise AssertionError(f"unexpected method {body.get('method')}")

    with patch("rag_protection_proxy.tools_gateway.backends.mcp_shim.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = False
        mock_client.post.side_effect = handler
        mock_client_cls.return_value = mock_client

        with pytest.raises(McpShimError, match="access denied"):
            client.call_tool("read_text_file", {"path": "/etc/passwd"})


def test_mcp_client_raises_on_transport_failure():
    client = McpStreamableHttpClient("http://mcp-filesystem:8000/mcp", timeout=5.0)

    with patch("rag_protection_proxy.tools_gateway.backends.mcp_shim.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = False
        mock_client.post.side_effect = httpx.ConnectTimeout("timed out")
        mock_client_cls.return_value = mock_client

        with pytest.raises(McpShimError, match="MCP transport failed"):
            client.call_tool("read_text_file", {"path": "/workspace/docs/runbook.md"})


def test_normalize_mcp_arguments_maps_relative_path():
    entry = ToolPolicyEntry(
        name="read_file",
        description="Read file",
        backend="mcp_filesystem",
        mcp_tool="read_text_file",
    )
    assert normalize_mcp_arguments({"path": "docs/runbook.md"}, entry) == {
        "path": "/workspace/docs/runbook.md",
    }
    assert normalize_mcp_arguments({"path": "/workspace/docs/runbook.md"}, entry) == {
        "path": "/workspace/docs/runbook.md",
    }


def test_invoke_mcp_backend_requires_env(monkeypatch):
    monkeypatch.delenv("MCP_FILESYSTEM_URL", raising=False)
    entry = ToolPolicyEntry(
        name="read_file",
        description="Read file",
        backend="mcp_filesystem",
        mcp_tool="read_text_file",
    )
    with pytest.raises(McpShimError, match="MCP_FILESYSTEM_URL"):
        invoke_mcp_backend({"path": "docs/runbook.md"}, entry)


def test_invoke_mcp_backend_normalizes_result(monkeypatch):
    monkeypatch.setenv("MCP_FILESYSTEM_URL", "http://mcp-filesystem:8000/mcp")
    entry = ToolPolicyEntry(
        name="read_file",
        description="Read file",
        backend="mcp_filesystem",
        mcp_tool="read_text_file",
    )

    with patch.object(
        McpStreamableHttpClient,
        "call_tool",
        return_value={"content": [{"type": "text", "text": "runbook body"}], "isError": False},
    ):
        result = invoke_mcp_backend({"path": "docs/runbook.md"}, entry)

    assert result["status"] == "ok"
    assert result["source"] == "mcp"
    assert result["path"] == "docs/runbook.md"
    assert result["content"] == "runbook body"
    assert result["mcp_tool"] == "read_text_file"
