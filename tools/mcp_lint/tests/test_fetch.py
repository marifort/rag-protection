"""Tests for manifest loading and live fetch."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from mcp_lint.fetch import ManifestError, fetch_live, load_manifest
from mcp_lint.tests._util import BAD_MANIFEST, GOOD_MANIFEST


def test_load_good_manifest():
    tools = load_manifest(GOOD_MANIFEST)
    assert len(tools) == 2
    assert tools[0].name == "read_text_file"
    assert "UTF-8" in tools[0].description


def test_load_bad_manifest_has_tools():
    tools = load_manifest(BAD_MANIFEST)
    assert len(tools) == 5


def test_load_accepts_bare_tools_array(tmp_path):
    path = tmp_path / "tools.json"
    path.write_text(json.dumps([{"name": "ping", "description": "Ping"}]), encoding="utf-8")
    tools = load_manifest(path)
    assert tools[0].name == "ping"


def test_load_accepts_jsonrpc_wrapper(tmp_path):
    path = tmp_path / "tools.json"
    path.write_text(
        json.dumps({"result": {"tools": [{"name": "ping", "description": "Ping"}]}}),
        encoding="utf-8",
    )
    tools = load_manifest(path)
    assert tools[0].name == "ping"


def test_missing_manifest_raises():
    with pytest.raises(ManifestError, match="not found"):
        load_manifest("/nonexistent/tools.json")


def test_invalid_json_raises(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ManifestError, match="invalid JSON"):
        load_manifest(path)


def test_empty_tools_raises(tmp_path):
    path = tmp_path / "empty.json"
    path.write_text(json.dumps({"tools": []}), encoding="utf-8")
    with pytest.raises(ManifestError, match="no tools"):
        load_manifest(path)


def _json_response(payload: dict, *, session_id: str | None = None) -> httpx.Response:
    headers = {"content-type": "application/json"}
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    return httpx.Response(200, json=payload, headers=headers, request=httpx.Request("POST", "http://test/mcp"))


def test_fetch_live_success():
    calls: list[dict] = []

    def handler(*args, **kwargs) -> httpx.Response:
        body = kwargs.get("json", {})
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
                        "tools": [{"name": "read_file", "description": "Read a file"}],
                    },
                },
                session_id="sess-1",
            )
        raise AssertionError(f"unexpected method {method!r}")

    with patch("rag_protection_proxy.tools_gateway.backends.mcp_shim.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = False
        mock_client.post.side_effect = handler
        mock_client_cls.return_value = mock_client

        tools = fetch_live("http://mcp:8000/mcp", timeout=5.0)

    assert tools[0].name == "read_file"
    assert calls[2]["method"] == "tools/list"


def test_fetch_live_transport_error():
    with patch("rag_protection_proxy.tools_gateway.backends.mcp_shim.httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = False
        mock_client.post.side_effect = httpx.ConnectTimeout("timed out")
        mock_client_cls.return_value = mock_client

        with pytest.raises(ManifestError, match="unreachable"):
            fetch_live("http://mcp:8000/mcp")
