"""Load MCP tool manifests from a static file or a live MCP server."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, List

from rag_protection_proxy.tools_gateway.backends.mcp_shim import (
    McpShimError,
    McpStreamableHttpClient,
)

from .models import McpTool


class ManifestError(ValueError):
    """Raised when a manifest file is missing, invalid, or empty."""


def load_manifest(path: str | Path) -> List[McpTool]:
    """Parse a saved ``tools/list`` JSON file."""
    manifest_path = Path(path)
    if not manifest_path.is_file():
        raise ManifestError(f"manifest not found: {manifest_path}")

    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ManifestError(f"invalid JSON in {manifest_path}: {exc}") from exc

    tools = _normalize_tools_payload(raw)
    if not tools:
        raise ManifestError(f"no tools found in {manifest_path}")

    source = str(manifest_path.resolve())
    return [_normalize_tool(item, source=source) for item in tools]


def fetch_live(url: str, *, timeout: float = 30.0) -> List[McpTool]:
    """Fetch ``tools/list`` from a running MCP Streamable HTTP server."""
    endpoint = url.strip()
    if not endpoint:
        raise ManifestError("MCP URL is empty")

    try:
        client = McpStreamableHttpClient(endpoint, timeout=timeout)
        result = client.list_tools()
    except McpShimError as exc:
        raise ManifestError(f"MCP server unreachable or invalid: {exc}") from exc

    tools = _normalize_tools_payload(result)
    if not tools:
        raise ManifestError(f"no tools returned from {endpoint}")

    return [_normalize_tool(item, source=endpoint) for item in tools]


def _normalize_tools_payload(raw: Any) -> List[dict]:
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    if isinstance(raw, dict):
        tools = raw.get("tools")
        if isinstance(tools, list):
            return [item for item in tools if isinstance(item, dict)]
        # Some exports wrap the full JSON-RPC result.
        result = raw.get("result")
        if isinstance(result, dict) and isinstance(result.get("tools"), list):
            return [item for item in result["tools"] if isinstance(item, dict)]
    raise ManifestError("expected a tools/list payload with a 'tools' array")


def _normalize_tool(raw: dict, *, source: str) -> McpTool:
    name = raw.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ManifestError("each tool must have a non-empty 'name'")

    description = raw.get("description", "")
    if description is None:
        description = ""
    if not isinstance(description, str):
        description = str(description)

    schema = raw.get("inputSchema")
    if schema is not None and not isinstance(schema, dict):
        raise ManifestError(f"tool {name!r}: inputSchema must be an object")

    return McpTool(
        name=name.strip(),
        description=description,
        input_schema=schema,
        source=source,
    )
