from __future__ import annotations

import os
import contextlib
from typing import Any, Dict, Iterator, Optional


class OTelTracer:
    def __init__(self) -> None:
        self._enabled = False
        self._tracer = None
        endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
        service = os.getenv("OTEL_SERVICE_NAME", "agentic-console")
        if not endpoint:
            return
        try:
            from opentelemetry import trace
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor

            resource = Resource.create({"service.name": service})
            provider = TracerProvider(resource=resource)
            processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
            provider.add_span_processor(processor)
            trace.set_tracer_provider(provider)
            self._tracer = trace.get_tracer(service)
            self._enabled = True
        except Exception:
            self._enabled = False

    @contextlib.contextmanager
    def span(self, name: str, trace_id: str = "", attributes: Optional[Dict[str, Any]] = None) -> Iterator[None]:
        if not self._enabled or self._tracer is None:
            yield None
            return
        try:
            with self._tracer.start_as_current_span(name) as span:
                if trace_id:
                    span.set_attribute("trace_id", trace_id)
                if attributes:
                    for k, v in attributes.items():
                        span.set_attribute(k, v)
                yield None
        except Exception:
            yield None

    def log_event(self, trace_id: str, name: str, payload: Dict[str, Any]) -> None:
        if not self._enabled or self._tracer is None:
            return
        try:
            with self.span(name, trace_id=trace_id, attributes=payload):
                pass
        except Exception:
            return
