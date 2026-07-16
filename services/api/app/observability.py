from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from sqlalchemy import Engine

from app.core.config import Settings

_configured = False
ALLOWED_TRACE_ATTRIBUTES = {
    "agent.intent",
    "agent.risk_level",
    "embedding.batch_size",
    "embedding.model",
    "embedding.provider",
    "llm.model",
    "llm.provider",
    "llm.task",
    "mcp.tool_name",
    "policy.hit_count",
    "tool.result_status",
    "workflow.action_plan_id",
    "workflow.mode",
    "workflow.node",
    "workflow.run_id",
}


def configure_telemetry(app: FastAPI, engine: Engine, settings: Settings) -> None:
    global _configured
    if _configured or not settings.otel_enabled:
        return

    provider = TracerProvider(
        resource=Resource.create({"service.name": settings.otel_service_name})
    )
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint))
    )
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider)
    HTTPXClientInstrumentor().instrument(tracer_provider=provider)
    SQLAlchemyInstrumentor().instrument(engine=engine, tracer_provider=provider)
    _configured = True


def get_tracer():
    return trace.get_tracer("commerceflow-agent")


def current_trace_id() -> str | None:
    span_context = trace.get_current_span().get_span_context()
    if not span_context.is_valid:
        return None
    return f"{span_context.trace_id:032x}"


@contextmanager
def workflow_span(name: str, attributes: dict[str, str | int | bool | None]) -> Iterator[None]:
    safe_attributes = safe_trace_attributes(attributes)
    with get_tracer().start_as_current_span(name, attributes=safe_attributes):
        yield


def safe_trace_attributes(
    attributes: dict[str, str | int | bool | None],
) -> dict[str, str | int | bool]:
    return {
        key: value
        for key, value in attributes.items()
        if key in ALLOWED_TRACE_ATTRIBUTES and value is not None
    }
