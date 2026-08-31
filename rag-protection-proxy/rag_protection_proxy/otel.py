"""Optional OpenTelemetry pipeline tracing (E4.6)."""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Any, Dict, Iterator, Optional

logger = logging.getLogger(__name__)

_ENABLED = False
_TRACER = None


def configure_otel() -> None:
    global _ENABLED, _TRACER
    _ENABLED = os.getenv("RAG_OTEL_ENABLED", "").strip().lower() in {"1", "true", "yes"}
    if not _ENABLED:
        _TRACER = None
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    except ImportError:
        logger.warning("RAG_OTEL_ENABLED=true but opentelemetry-sdk is not installed; tracing disabled")
        _ENABLED = False
        _TRACER = None
        return

    service_name = os.getenv("OTEL_SERVICE_NAME", "rag-protection-proxy")
    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

            provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
        except ImportError:
            logger.warning("OTLP exporter unavailable; falling back to console span exporter")
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    else:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    _TRACER = trace.get_tracer("rag_protection_proxy.pipeline")


def enabled() -> bool:
    return _ENABLED and _TRACER is not None


@contextmanager
def trace_span(name: str, attributes: Optional[Dict[str, Any]] = None) -> Iterator[None]:
    if not enabled():
        yield
        return

    with _TRACER.start_as_current_span(name) as span:
        for key, value in (attributes or {}).items():
            if value is not None:
                span.set_attribute(key, value)
        yield
