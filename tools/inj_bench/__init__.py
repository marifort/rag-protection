"""rag-injbench — prompt-injection benchmark / regression pack (A7, OSS lead-gen asset).

A thin, standalone wrapper over the shipped ``PromptInjectionScanner`` and
``MLInjectionScanner``. It scores a versioned corpus of labeled injection
payloads against any filter (builtin scanners or an HTTP endpoint) and reports
detection rate, false-positive rate, and per-category coverage — the metrics a
CI pipeline gates on.

The library owns **no injection logic** of its own: every verdict comes from the
same scanners the gateway runs at runtime. A7 packages a corpus + scoring harness
around them. It is a top-of-funnel regression yardstick — indicative, not a
guarantee of injection safety — and runs entirely locally.

See ``tools/inj_bench/README.md`` for usage.
"""

from __future__ import annotations

__version__ = "0.1.0"
