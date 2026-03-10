from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from autolab.core.settings import Settings
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def setup_tracing(settings: Settings) -> None:
    provider = TracerProvider(
        resource=Resource.create({"service.name": settings.otel.service_name})
    )
    processor = BatchSpanProcessor(
        OTLPSpanExporter(endpoint=settings.otel.exporter_otlp_endpoint, insecure=True)
    )
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)


@contextmanager
def start_span(name: str) -> Iterator[None]:
    tracer = trace.get_tracer("autolab")
    with tracer.start_as_current_span(name):
        yield
