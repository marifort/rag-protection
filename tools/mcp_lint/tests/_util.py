"""Shared helpers for the mcp-lint test suite."""

from __future__ import annotations

from pathlib import Path

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
GOOD_MANIFEST = EXAMPLES / "good_tools.json"
BAD_MANIFEST = EXAMPLES / "bad_tools.json"
