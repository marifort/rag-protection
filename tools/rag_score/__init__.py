"""rag-score — RAG security posture scorecard (A3, free lead-gen asset).

A thin wrapper over the shipped ``rag-scan`` config scanner that turns its
findings into a shareable **A–F posture grade**: a weighted score, an OWASP LLM
Top 10 coverage summary, and the top remediations to fix first.

The scorecard reuses ``rag_scan``'s checks verbatim (which in turn import the
runtime gateway's config loaders), so a grade reflects the *same* configuration
the gateway would actually load. It is a top-of-funnel lead magnet — indicative,
not a certification — and runs entirely locally: no configuration is uploaded.

See ``tools/rag_score/README.md`` for usage.
"""

from __future__ import annotations

__version__ = "0.1.0"
