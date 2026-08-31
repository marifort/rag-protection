"""Locate EE + proxy packages so the tool reuses shipped ACL mapping + stores."""

from __future__ import annotations

import sys
from pathlib import Path


def ensure_imports() -> None:
    """Make ``rag_protection_enterprise`` and ``rag_protection_proxy`` importable."""
    repo_root = Path(__file__).resolve().parents[2]

    try:
        import rag_protection_proxy  # noqa: F401
    except ImportError:
        proxy_dir = repo_root / "rag-protection-proxy"
        if proxy_dir.is_dir():
            sys.path.insert(0, str(proxy_dir))
        import rag_protection_proxy  # noqa: F401

    try:
        import rag_protection_enterprise  # noqa: F401
    except ImportError:
        ee_dir = repo_root / "rag-protection-enterprise"
        if ee_dir.is_dir():
            sys.path.insert(0, str(ee_dir))
        import rag_protection_enterprise  # noqa: F401
