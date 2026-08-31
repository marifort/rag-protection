"""Ensure examples/python and rag_protection_proxy are importable from a checkout."""

from __future__ import annotations

import sys
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def ensure_import_paths() -> None:
    root = repo_root()
    for candidate in (
        root / "examples" / "python",
        root / "rag-protection-proxy",
    ):
        path = str(candidate)
        if candidate.is_dir() and path not in sys.path:
            sys.path.insert(0, path)
