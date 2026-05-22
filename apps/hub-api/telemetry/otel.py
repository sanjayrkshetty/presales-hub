"""
OpenTelemetry initialisation.

Export strategy (controlled by env vars):
  OTLP_ENDPOINT set  → BatchSpanProcessor → OTLPSpanExporter (HTTP/protobuf)
                        Jaeger, Tempo, or any OTLP-compatible backend
  OTLP_ENDPOINT unset → ConsoleSpanExporter (dev / CI)

Auto-instrumentation:
  FastAPIInstrumentor  — HTTP request spans with method/route/status
  SQLAlchemyInstrumentor — DB query spans (engine-level, vendor-agnostic)

Both instrumentors degrade gracefully if their packages are missing.
"""
import logging
import os

logger = logging.getLogger("telemetry.otel")

SERVICE_NAME = os.getenv("SERVICE_NAME", "hub-api")


def setup_telemetry(app=None, engine=None):
    """Initialise OTel SDK and optionally instrument FastAPI + SQLAlchemy."""
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME as OT_SERVICE
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    except ImportError:
        logger.warning("opentelemetry-sdk not installed — tracing disabled")
        return None

    resource = Resource.create({OT_SERVICE: SERVICE_NAME})
    provider = TracerProvider(resource=resource)

    otlp_endpoint = os.getenv("OTLP_ENDPOINT")
    if otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            exporter = OTLPSpanExporter(endpoint=f"{otlp_endpoint.rstrip('/')}/v1/traces")
            provider.add_span_processor(BatchSpanProcessor(exporter))
            logger.info("OTel: OTLP exporter → %s", otlp_endpoint)
        except ImportError:
            logger.warning("OTel: opentelemetry-exporter-otlp-proto-http not installed")
    else:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        logger.info("OTel: console exporter active (set OTLP_ENDPOINT for remote backend)")

    trace.set_tracer_provider(provider)

    if app is not None:
        try:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
            FastAPIInstrumentor.instrument_app(app)
            logger.info("OTel: FastAPI auto-instrumentation active")
        except ImportError:
            logger.warning("OTel: opentelemetry-instrumentation-fastapi not installed")

    if engine is not None:
        try:
            from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
            SQLAlchemyInstrumentor().instrument(engine=engine)
            logger.info("OTel: SQLAlchemy auto-instrumentation active")
        except ImportError:
            logger.warning("OTel: opentelemetry-instrumentation-sqlalchemy not installed")

    return provider
