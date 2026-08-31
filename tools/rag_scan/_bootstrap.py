"""Locate the ``rag_protection_proxy`` package so checks reuse runtime loaders.

The scanner deliberately imports the *same* config loaders the gateway uses at
runtime. When run from a checkout (not pip-installed), the proxy package lives in
the sibling ``rag-protection-proxy/`` directory; add it to ``sys.path`` if it is
not already importable.
"""

from __future__ import annotations

import sys
from pathlib import Path


def ensure_proxy_importable() -> None:
    try:
        import rag_protection_proxy  # noqa: F401

        return
    except ImportError:
        pass

    # tools/rag_scan/_bootstrap.py -> repo root is two parents up.
    repo_root = Path(__file__).resolve().parents[2]
    proxy_dir = repo_root / "rag-protection-proxy"
    if proxy_dir.is_dir():
        sys.path.insert(0, str(proxy_dir))

    # Best-effort second import; the caller surfaces a clean error if it fails.
    import rag_protection_proxy  # noqa: F401
