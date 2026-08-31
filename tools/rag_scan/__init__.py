"""rag-scan — pre-production RAG config scanner (Lab 2, shift-left).

A thin CLI that imports the *same* policy loaders as the RAG Protection runtime
gateway (``rag_protection_proxy.config``) so that a CI failure provably means the
running gateway would have accepted a dangerous configuration.

See ``tools/rag_scan/README.md`` for usage and the rule catalog.
"""

from __future__ import annotations

__version__ = "0.1.0"
