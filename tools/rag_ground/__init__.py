"""rag-ground — grounding / hallucination check library (A6, OSS lead-gen asset).

A thin, standalone wrapper over the shipped output guardrail
``rag_protection_proxy.guardrails.citation.verify_citations``. It scores an LLM
answer against the source chunks it was supposed to be grounded in and returns a
**grounded / ungrounded / leak** verdict plus a coverage ratio — the metric an
eval or CI pipeline gates on.

The library owns **no grounding logic** of its own: every verdict comes from the
same ``verify_citations`` the gateway runs on every answer at runtime. A6 just
exposes it *outside* the request pipeline as a batch/CI tool. It is a
top-of-funnel lead magnet — indicative, not a hallucination guarantee — and runs
entirely locally (offline lexical entailment by default): no answer or source
text is uploaded.

See ``tools/rag_ground/README.md`` for usage.
"""

from __future__ import annotations

__version__ = "0.1.0"
