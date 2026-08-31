"""mcp-lint — MCP manifest / tool-description linter (A2, OSS lead-gen).

Statically lint MCP ``tools/list`` manifests for tool-description injection and
over-broad scopes *before* an agent connects. Reuses the shipped
``PromptInjectionScanner`` and ``McpStreamableHttpClient`` from the RAG
Protection proxy.

See ``tools/mcp_lint/README.md`` for usage and the rule catalog.
"""

from __future__ import annotations

from ._bootstrap import ensure_proxy_importable

ensure_proxy_importable()

__version__ = "0.1.0"
